import json
import re
import os
from pathlib import Path
from dotenv import load_dotenv

try:
    from agents.groq_utils import chamar_groq
except ImportError:
    from groq_utils import chamar_groq


def parse_groq_response(text: str) -> dict:
    """Parse seguro de JSON retornado pelo Groq — trata escapes inválidos."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', text)
        try:
            return json.loads(cleaned)
        except Exception:
            return {"content": text}

load_dotenv()

SKILL_PATH = Path(__file__).parent.parent / ".claude" / "skills" / "critic.md"


def _carregar_skill() -> str:
    """Lê a skill do Professor Crítico e retorna o conteúdo."""
    try:
        return SKILL_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _montar_contexto_pesquisa(resultado_pesquisa: dict) -> str:
    """Serializa o output do Pesquisador em texto estruturado para o prompt."""
    tema = resultado_pesquisa.get("tema", "")
    tipo = resultado_pesquisa.get("tipo_busca", "")
    resumo = resultado_pesquisa.get("resumo", "")

    secoes = [
        f"TEMA: {tema}",
        f"TIPO DE BUSCA: {tipo}",
        f"RESUMO GERAL: {resumo}",
    ]

    didatico = resultado_pesquisa.get("conteudo_didatico", [])
    if didatico:
        secoes.append("\nCONTEÚDO DIDÁTICO:")
        for i, f in enumerate(didatico, 1):
            secoes.append(f"  [{i}] {f['titulo']}\n      {f['conteudo'][:300]}")

    noticias = resultado_pesquisa.get("noticias_relevantes", [])
    if noticias:
        secoes.append("\nNOTÍCIAS RECENTES:")
        for i, f in enumerate(noticias, 1):
            secoes.append(f"  [{i}] {f['titulo']}\n      {f['conteudo'][:300]}")

    academico = resultado_pesquisa.get("referencias_academicas", [])
    if academico:
        secoes.append("\nREFERÊNCIAS ACADÊMICAS:")
        for i, f in enumerate(academico, 1):
            secoes.append(f"  [{i}] {f['titulo']}\n      {f['conteudo'][:300]}")

    termos = resultado_pesquisa.get("termos_relacionados", [])
    if termos:
        secoes.append(f"\nTERMOS RELACIONADOS: {', '.join(termos)}")

    return "\n".join(secoes)


def _montar_prompt(contexto: str) -> str:
    return f"""Você recebeu o seguinte conteúdo pesquisado sobre um tema do ENEM:

{contexto}

Com base nesse conteúdo, produza uma análise crítica e estratégica estruturada em JSON válido.
Retorne APENAS o JSON, sem texto antes ou depois, no seguinte formato:

{{
  "frequencia_enem": {{
    "descricao": "string — com que frequência e em quais áreas do conhecimento esse tema aparece",
    "areas": ["lista de áreas: Ciências Humanas, Natureza, Linguagens, Matemática"],
    "tipo": "recorrente ou emergente",
    "profundidade": "superficial, intermediário ou aprofundado"
  }},
  "erros_comuns": [
    {{
      "erro": "descrição do erro conceitual",
      "explicacao": "por que esse erro acontece",
      "como_evitar": "dica prática para não cometer"
    }}
  ],
  "conexoes_interdisciplinares": [
    {{
      "disciplina": "nome da disciplina",
      "conexao": "como se conecta com o tema",
      "exemplo_enem": "como o ENEM já explorou essa conexão"
    }}
  ],
  "pontos_criticos": [
    {{
      "conceito": "nome do conceito",
      "importancia": "essencial ou complementar",
      "ancora": true,
      "descricao": "o que o estudante precisa saber sobre esse conceito"
    }}
  ],
  "contexto_atual": {{
    "eventos_recentes": "string — eventos ou debates atuais relacionados",
    "dados_estatisticos": "string — dados ou estatísticas recentes relevantes",
    "debate_atual": "string — se há debate científico, político ou social ativo"
  }},
  "nivel_prioridade": "alta, média ou baixa",
  "justificativa_prioridade": "string — por que essa prioridade foi atribuída"
}}"""


def analisar(resultado_pesquisa: dict) -> dict:
    """
    Recebe o output do Agente Pesquisador e produz uma análise crítica
    estratégica conforme a skill do Professor Crítico ENEM.

    Retorna um dicionário estruturado com os campos definidos na skill.
    """
    if resultado_pesquisa.get("tipo_busca") == "erro":
        return _resultado_erro(
            resultado_pesquisa.get("tema", ""),
            f"Pesquisa anterior falhou: {resultado_pesquisa.get('erro', 'erro desconhecido')}",
        )

    skill = _carregar_skill()
    contexto = _montar_contexto_pesquisa(resultado_pesquisa)
    prompt = _montar_prompt(contexto)

    r = chamar_groq(
        messages=[
            {"role": "system", "content": skill},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2000,
    )
    if r["erro"]:
        return _resultado_erro(resultado_pesquisa.get("tema", ""), r["erro"])

    texto = r["texto"].strip()

    # Remove blocos de código markdown se presentes
    if texto.startswith("```"):
        linhas = texto.splitlines()
        texto = "\n".join(linhas[1:-1] if linhas[-1] == "```" else linhas[1:])

    try:
        analise = parse_groq_response(texto)
    except Exception as e:
        return _resultado_erro(
            resultado_pesquisa.get("tema", ""),
            f"Resposta do Groq não é JSON válido: {e}",
        )

    tokens = r["tokens_usados"]
    return {
        "tema": resultado_pesquisa.get("tema", ""),
        "frequencia_enem": analise.get("frequencia_enem", {}),
        "erros_comuns": analise.get("erros_comuns", []),
        "conexoes_interdisciplinares": analise.get("conexoes_interdisciplinares", []),
        "pontos_criticos": analise.get("pontos_criticos", []),
        "contexto_atual": analise.get("contexto_atual", {}),
        "nivel_prioridade": analise.get("nivel_prioridade", ""),
        "justificativa_prioridade": analise.get("justificativa_prioridade", ""),
        "tokens_usados": tokens,
        "skill_utilizada": str(SKILL_PATH),
    }


def _resultado_erro(tema: str, mensagem: str) -> dict:
    """Retorna um dicionário de erro padronizado sem quebrar o pipeline."""
    return {
        "tema": tema,
        "frequencia_enem": {},
        "erros_comuns": [],
        "conexoes_interdisciplinares": [],
        "pontos_criticos": [],
        "contexto_atual": {},
        "nivel_prioridade": "",
        "justificativa_prioridade": "",
        "tokens_usados": 0,
        "erro": mensagem,
        "skill_utilizada": str(SKILL_PATH),
    }


if __name__ == "__main__":
    resultado_pesquisa_exemplo = {
        "tema": "fordismo",
        "tipo_busca": "palavra_chave",
        "resumo": (
            "Fordismo é um modelo de produção industrial criado por Henry Ford no início do "
            "século XX, baseado na linha de montagem, padronização e produção em massa. "
            "Transformou o trabalho industrial e a sociedade de consumo."
        ),
        "conteudo_didatico": [
            {
                "titulo": "Fordismo — Brasil Escola",
                "url": "https://brasilescola.uol.com.br/geografia/fordismo.htm",
                "conteudo": (
                    "O fordismo surgiu com Henry Ford em 1913 na fábrica de automóveis Ford. "
                    "Características: linha de montagem, salário fixo, produção em série, "
                    "consumo de massa. Influenciou a organização do trabalho no século XX."
                ),
            }
        ],
        "noticias_relevantes": [
            {
                "titulo": "Automação substitui funções fordistas nas fábricas brasileiras",
                "url": "https://g1.globo.com/economia/noticia/2024/automacao.html",
                "conteudo": "Indústrias brasileiras substituem linhas de montagem tradicionais por robôs.",
            }
        ],
        "referencias_academicas": [],
        "termos_relacionados": ["taylorismo", "toyotismo", "produção em massa", "alienação do trabalho"],
        "lacunas_e_aprofundamento": [],
    }

    resultado = analisar(resultado_pesquisa_exemplo)

    print(f"Tema: {resultado['tema']}")
    print(f"Prioridade: {resultado['nivel_prioridade']}")
    print(f"Tokens usados: {resultado.get('tokens_usados', 0)}")

    if resultado.get("erro"):
        print(f"ERRO: {resultado['erro']}")
    else:
        print(f"\nÁreas ENEM: {resultado['frequencia_enem'].get('areas', [])}")
        print(f"Erros comuns: {len(resultado['erros_comuns'])}")
        print(f"Conexões: {len(resultado['conexoes_interdisciplinares'])}")
        print(f"Pontos críticos: {len(resultado['pontos_criticos'])}")
