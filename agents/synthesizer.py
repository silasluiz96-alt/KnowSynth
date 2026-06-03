import json
import re
import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq


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
    return f"""Você recebeu os outputs de todos os agentes do pipeline KnowSynth sobre o tema "{tema}".

--- OUTPUT DO PESQUISADOR ---
{pesquisa}

--- OUTPUT DO PROFESSOR CRÍTICO ---
{critica}

--- CONTEXTO DO ANALISTA DE DESEMPENHO ---
{desempenho}

Com base nesses inputs, gere o material de estudo completo no formato JSON abaixo.
Retorne APENAS o JSON válido, sem texto antes ou depois.

{{
  "introducao": "string — explicação acessível em até 3 parágrafos, com analogias e contexto atual",

  "pontos_essenciais": [
    {{
      "conceito": "nome do conceito",
      "definicao": "definição clara e simples",
      "exemplo": "exemplo prático do cotidiano",
      "cobrado_enem": true
    }}
  ],

  "conexoes_interdisciplinares": [
    {{
      "disciplina": "nome da disciplina",
      "como_se_conecta": "explicação da conexão",
      "exemplo_enem": "como o ENEM já explorou isso"
    }}
  ],

  "questao_enem": {{
    "texto_apoio": "texto motivador (notícia, dado, trecho — obrigatório)",
    "enunciado": "enunciado com comando explícito",
    "alternativas": {{
      "A": "texto da alternativa A",
      "B": "texto da alternativa B",
      "C": "texto da alternativa C",
      "D": "texto da alternativa D",
      "E": "texto da alternativa E"
    }},
    "gabarito_interno": "letra da alternativa correta (A, B, C, D ou E)",
    "nota_sobre_alternativas": {{
      "claramente_errada": "letra e motivo",
      "com_pegadinha": ["letra1 — motivo", "letra2 — motivo"],
      "quase_correta": "letra e motivo",
      "correta": "letra e motivo completo"
    }}
  }},

  "analise_palavras_chave": {{
    "no_enunciado": {{
      "conectivos": ["lista de conectivos presentes e seu efeito"],
      "delimitadores": ["lista de delimitadores e o que restringem"],
      "comando": "o comando da questão e o que ele exige do estudante"
    }},
    "nas_alternativas": {{
      "absolutismo_armadilha": ["alternativas com palavras absolutas e por que eliminam"],
      "pegadinhas_vocabulario": ["termos parecidos com o correto mas diferentes"],
      "marcadores_correto": "o que torna a alternativa correta reconhecível"
    }}
  }},

  "dicas_de_prova": [
    "dica específica para não errar questões desse tema"
  ],

  "leituras_recomendadas": {{
    "indicacoes": [
      {{"tipo": "artigo/vídeo/capítulo", "titulo": "título sugerido", "onde_encontrar": "onde buscar"}}
    ],
    "palavras_chave_scholar": ["palavra1", "palavra2", "palavra3"],
    "exemplo_busca": "exemplo de como formular a busca no Google Scholar"
  }}
}}

IMPORTANTE: O campo "gabarito_interno" existe apenas para uso técnico interno.
O material entregue ao estudante NÃO deve conter o gabarito — ele só é liberado
pelo Estrategista após as 3 dicas progressivas."""


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

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        resposta = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=4000,
            messages=[
                {"role": "system", "content": skill},
                {"role": "user", "content": prompt},
            ],
        )

        texto = resposta.choices[0].message.content.strip()
        if texto.startswith("```"):
            linhas = texto.splitlines()
            texto = "\n".join(linhas[1:-1] if linhas[-1].strip() == "```" else linhas[1:])

        material = parse_groq_response(texto)

        # Se o parse retornou fallback {"content": ...}, extrai o texto bruto
        # e tenta encontrar JSON embutido no meio da resposta
        if "content" in material and "introducao" not in material:
            import re as _re
            texto_bruto = material["content"]
            # Tenta encontrar bloco JSON dentro de texto livre
            match = _re.search(r'\{[\s\S]*\}', texto_bruto)
            if match:
                try:
                    material = parse_groq_response(match.group(0))
                except Exception:
                    pass
            # Se ainda não tem os campos, mantém o texto bruto em "content"
            # para que o app.py possa exibí-lo como fallback legível

    except json.JSONDecodeError as e:
        return _resultado_erro(tema, f"Resposta do Groq não é JSON válido: {e}")
    except Exception as e:
        return _resultado_erro(tema, f"Erro ao chamar a API do Groq: {e}")

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
        "tokens_usados": resposta.usage.total_tokens if resposta.usage else 0,
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

