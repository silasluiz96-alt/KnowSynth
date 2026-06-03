import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

try:
    from utils.llm_client import chamar_llm, parse_resposta_json
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from utils.llm_client import chamar_llm, parse_resposta_json

load_dotenv()

SKILL_PATH = Path(__file__).parent.parent / ".claude" / "skills" / "synthesizer.md"


def _carregar_skill() -> str:
    try:
        return SKILL_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _serializar_pesquisa(r: dict) -> str:
    """Extrai o essencial do output do Pesquisador."""
    partes = [
        f"TEMA: {r.get('tema', '')}",
        f"TIPO DE BUSCA: {r.get('tipo_busca', '')}",
        f"RESUMO: {r.get('resumo', '')}",
    ]

    for fonte in r.get("conteudo_didatico", [])[:3]:
        partes.append(f"[Didático] {fonte['titulo']}: {fonte['conteudo'][:250]}")

    for fonte in r.get("noticias_relevantes", [])[:2]:
        partes.append(f"[Notícia] {fonte['titulo']}: {fonte['conteudo'][:200]}")

    for fonte in r.get("referencias_academicas", [])[:2]:
        partes.append(f"[Acadêmico] {fonte['titulo']}: {fonte['conteudo'][:200]}")

    termos = r.get("termos_relacionados", [])
    if termos:
        partes.append(f"TERMOS RELACIONADOS: {', '.join(str(t) for t in termos)}")

    return "\n".join(partes)


def _serializar_critica(r: dict) -> str:
    """Extrai o essencial do output do Crítico."""
    partes = [f"PRIORIDADE: {r.get('nivel_prioridade', '')}"]

    freq = r.get("frequencia_enem", {})
    if freq:
        areas = ", ".join(freq.get("areas", []))
        partes.append(
            f"FREQUÊNCIA NO ENEM: {freq.get('descricao', '')} | Áreas: {areas} | "
            f"Profundidade: {freq.get('profundidade', '')}"
        )

    erros = r.get("erros_comuns", [])
    if erros:
        partes.append("ERROS COMUNS DOS ESTUDANTES:")
        for e in erros[:3]:
            partes.append(f"  - {e.get('erro', '')}: {e.get('como_evitar', '')}")

    conexoes = r.get("conexoes_interdisciplinares", [])
    if conexoes:
        partes.append("CONEXÕES INTERDISCIPLINARES:")
        for c in conexoes[:4]:
            partes.append(
                f"  - {c.get('disciplina', '')}: {c.get('conexao', '')} "
                f"(ENEM: {c.get('exemplo_enem', '')})"
            )

    criticos = r.get("pontos_criticos", [])
    if criticos:
        partes.append("PONTOS CRÍTICOS OBRIGATÓRIOS:")
        for p in criticos:
            ancora = " [ÂNCORA]" if p.get("ancora") else ""
            partes.append(f"  - {p.get('conceito', '')}{ancora}: {p.get('descricao', '')}")

    ctx = r.get("contexto_atual", {})
    if ctx:
        partes.append(f"CONTEXTO ATUAL: {ctx.get('eventos_recentes', '')} | {ctx.get('debate_atual', '')}")

    return "\n".join(partes)


def _serializar_desempenho(r: dict) -> str:
    """Extrai contexto de dificuldade do Analista de Desempenho (opcional)."""
    if not r:
        return "Sem dados de desempenho disponíveis para esta sessão."

    temas = r.get("temas_estudados", [])
    dificuldades = r.get("dificuldade_por_tema", {})
    duracao = r.get("duracao_min", 0)

    partes = [
        f"Temas estudados na sessão: {', '.join(temas) if temas else 'nenhum ainda'}",
        f"Duração da sessão: {duracao:.1f} min",
    ]
    if dificuldades:
        partes.append("Dificuldade por tema: " + ", ".join(f"{t}={d}" for t, d in dificuldades.items()))

    return "\n".join(partes)


def _montar_prompt(tema: str, pesquisa: str, critica: str, desempenho: str) -> str:
    return f"""Gere material de estudo sobre "{tema}" com base nos inputs abaixo. Retorne APENAS JSON válido.

PESQUISADOR: {pesquisa}
CRÍTICO: {critica}

JSON esperado (seja conciso — respeite os limites indicados):

{{
  "introducao": "2 parágrafos curtos: definição clara + contexto atual com analogia",

  "pontos_essenciais": [
    {{"conceito": "nome", "definicao": "1 frase", "exemplo": "1 frase cotidiana", "cobrado_enem": true}}
  ],

  "conexoes_interdisciplinares": [
    {{"disciplina": "nome", "como_se_conecta": "1 frase", "exemplo_enem": "1 frase"}}
  ],

  "questao_enem": {{
    "texto_apoio": "texto de apoio curto (2-4 linhas)",
    "enunciado": "enunciado com comando explícito",
    "alternativas": {{
      "A": "alternativa A",
      "B": "alternativa B",
      "C": "alternativa C",
      "D": "alternativa D",
      "E": "alternativa E"
    }},
    "gabarito_interno": "letra correta (A-E)"
  }},

  "analise_palavras_chave": {{
    "no_enunciado": {{"comando": "o que a questão pede"}},
    "nas_alternativas": {{"marcadores_correto": "o que marca a correta"}}
  }},

  "dicas_de_prova": ["dica 1", "dica 2"],

  "leituras_recomendadas": {{
    "indicacoes": [{{"tipo": "tipo", "titulo": "título", "onde_encontrar": "onde"}}],
    "palavras_chave_scholar": ["termo1", "termo2"]
  }}
}}

LIMITES: introducao=2 parágrafos, pontos_essenciais=3 itens, conexoes=2 itens, dicas=2 itens, leituras=2 itens.
gabarito_interno é uso interno — não exibir ao estudante."""


def sintetizar(
    resultado_pesquisa: dict,
    resultado_critica: dict,
    snapshot_desempenho: dict = None,
) -> dict:
    """
    Recebe os outputs do Pesquisador, Crítico e Analista de Desempenho
    e gera o material de estudo completo conforme a skill do Sintetizador.

    O gabarito da questão fica em 'questao_enem.gabarito_interno' mas
    NÃO é incluído no campo 'questao_enem_sem_gabarito' — que é o que
    deve ser exibido ao estudante.

    Retorna dict com cada seção separada.
    """
    if resultado_pesquisa.get("tipo_busca") == "erro":
        return _resultado_erro(
            resultado_pesquisa.get("tema", ""),
            f"Pesquisa anterior falhou: {resultado_pesquisa.get('erro', '')}",
        )

    if resultado_critica.get("erro"):
        return _resultado_erro(
            resultado_pesquisa.get("tema", ""),
            f"Análise crítica falhou: {resultado_critica.get('erro', '')}",
        )

    tema = resultado_pesquisa.get("tema", "")
    skill = _carregar_skill()

    pesquisa_txt = _serializar_pesquisa(resultado_pesquisa)
    critica_txt = _serializar_critica(resultado_critica)
    desempenho_txt = _serializar_desempenho(snapshot_desempenho or {})

    prompt = _montar_prompt(tema, pesquisa_txt, critica_txt, desempenho_txt)

    r = chamar_llm(prompt=prompt, system_prompt=skill, max_tokens=1500)
    if r["erro"]:
        return _resultado_erro(tema, r["erro"])

    material = parse_resposta_json(r["texto"])

    # Separa a questão completa (com gabarito interno) da versão para o estudante
    questao_completa = material.get("questao_enem", {})
    questao_sem_gabarito = {
        k: v for k, v in questao_completa.items()
        if k not in ("gabarito_interno", "nota_sobre_alternativas")
    }

    return {
        "tema": tema,
        "introducao": material.get("introducao", ""),
        "pontos_essenciais": material.get("pontos_essenciais", []),
        "conexoes_interdisciplinares": material.get("conexoes_interdisciplinares", []),
        "questao_enem": questao_sem_gabarito,
        "questao_completa": questao_completa,
        "analise_palavras_chave": material.get("analise_palavras_chave", {}),
        "dicas_de_prova": material.get("dicas_de_prova", []),
        "leituras_recomendadas": material.get("leituras_recomendadas", {}),
        "tokens_usados": r["tokens_usados"],
        "modelo_usado": r["modelo_usado"],
        "skill_utilizada": str(SKILL_PATH),
        "erro": None,
    }


def _resultado_erro(tema: str, mensagem: str) -> dict:
    return {
        "tema": tema,
        "introducao": "",
        "pontos_essenciais": [],
        "conexoes_interdisciplinares": [],
        "questao_enem": {},
        "questao_completa": {},
        "analise_palavras_chave": {},
        "dicas_de_prova": [],
        "leituras_recomendadas": {},
        "tokens_usados": 0,
        "skill_utilizada": str(SKILL_PATH),
        "erro": mensagem,
    }


if __name__ == "__main__":
    resultado_pesquisa_exemplo = {
        "tema": "fordismo",
        "tipo_busca": "palavra_chave",
        "resumo": (
            "Fordismo é o modelo de produção criado por Henry Ford em 1913, baseado "
            "em linha de montagem, padronização e produção em massa. Transformou as "
            "relações de trabalho e impulsionou o consumo em escala industrial."
        ),
        "conteudo_didatico": [
            {
                "titulo": "Fordismo — Brasil Escola",
                "url": "https://brasilescola.uol.com.br/geografia/fordismo.htm",
                "conteudo": (
                    "Características: linha de montagem, especialização de tarefas, "
                    "salário fixo, produção em série e consumo de massa."
                ),
            }
        ],
        "noticias_relevantes": [
            {
                "titulo": "Automação substitui linha de montagem no Brasil",
                "url": "https://g1.globo.com",
                "conteudo": "Indústrias substituem funções repetitivas por robôs.",
            }
        ],
        "referencias_academicas": [],
        "termos_relacionados": ["taylorismo", "toyotismo", "produção em massa"],
        "lacunas_e_aprofundamento": [],
    }

    resultado_critica_exemplo = {
        "tema": "fordismo",
        "nivel_prioridade": "alta",
        "frequencia_enem": {
            "descricao": "Aparece frequentemente em Ciências Humanas",
            "areas": ["Ciências Humanas"],
            "tipo": "recorrente",
            "profundidade": "intermediário",
        },
        "erros_comuns": [
            {
                "erro": "Confundir fordismo com taylorismo",
                "explicacao": "Os dois são modelos de produção em série mas com focos diferentes",
                "como_evitar": "Lembrar: Ford = carro e linha de montagem; Taylor = cronômetro e tempo",
            }
        ],
        "conexoes_interdisciplinares": [
            {
                "disciplina": "Sociologia",
                "conexao": "Alienação do trabalho e desqualificação do operário",
                "exemplo_enem": "Questões sobre Karl Marx e trabalho industrial",
            }
        ],
        "pontos_criticos": [
            {
                "conceito": "Linha de montagem",
                "importancia": "essencial",
                "ancora": True,
                "descricao": "Divisão do processo produtivo em etapas fixas e repetitivas",
            }
        ],
        "contexto_atual": {
            "eventos_recentes": "Automação e fim de empregos repetitivos",
            "debate_atual": "Impacto da IA no mercado de trabalho",
        },
        "erro": None,
    }

    resultado = sintetizar(resultado_pesquisa_exemplo, resultado_critica_exemplo)

    if resultado.get("erro"):
        print(f"ERRO: {resultado['erro']}")
    else:
        print(f"Tema: {resultado['tema']}")
        print(f"Tokens usados: {resultado['tokens_usados']}\n")
        print("--- INTRODUÇÃO ---")
        print(resultado["introducao"])
        print(f"\n--- PONTOS ESSENCIAIS ({len(resultado['pontos_essenciais'])}) ---")
        for p in resultado["pontos_essenciais"]:
            print(f"  • {p.get('conceito')}: {p.get('definicao')}")
        print("\n--- QUESTÃO (SEM GABARITO) ---")
        q = resultado["questao_enem"]
        print(q.get("enunciado", ""))
        for letra, texto in q.get("alternativas", {}).items():
            print(f"  {letra}) {texto}")
        print(f"\nGabarito interno (uso técnico): {resultado['questao_completa'].get('gabarito_interno', '')}")

