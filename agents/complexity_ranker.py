"""
Sub-agente classificador de complexidade de questões do ENEM.

Recebe uma lista de questões (formato enem_api.py) e usa o Groq LLM
para analisar cada uma e retornar um Top 3 ordenado:
fácil → médio → difícil, com justificativa pedagógica.
"""

import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

SYSTEM_PROMPT = """Você é um especialista em avaliação pedagógica de questões do ENEM.
Sua função é analisar questões e classificar sua complexidade de forma precisa e justificada,
com foco no perfil do estudante do ensino médio brasileiro."""

# Critérios por nível
CRITERIOS = {
    "fácil": (
        "enunciado curto (até 3 linhas), vocabulário simples e cotidiano, "
        "1 conceito central, resposta direta sem inferência complexa"
    ),
    "médio": (
        "enunciado médio (4-8 linhas), algum vocabulário técnico, "
        "2 conceitos relacionados, requer análise moderada"
    ),
    "difícil": (
        "enunciado longo (8+ linhas) ou texto de apoio denso, "
        "vocabulário técnico/acadêmico, múltiplos conceitos encadeados, "
        "raciocínio em etapas ou alta abstração"
    ),
}


def _extrair_texto_questao(q: dict) -> str:
    """Serializa os campos relevantes de uma questão para o prompt."""
    contexto = q.get("contexto", "") or ""
    enunciado = q.get("enunciado", "") or ""
    alternativas = q.get("alternativas", {})

    partes = []
    texto_base = contexto if len(contexto) > len(enunciado) else enunciado
    partes.append(f"ENUNCIADO:\n{texto_base[:1000]}")

    if alternativas:
        partes.append("ALTERNATIVAS:")
        for letra in ["A", "B", "C", "D", "E"]:
            if letra in alternativas:
                partes.append(f"  {letra}) {alternativas[letra][:200]}")

    partes.append(f"ANO: {q.get('ano', '?')} | DISCIPLINA: {q.get('disciplina', '?')}")
    return "\n".join(partes)


def _classificar_uma(client: Groq, questao: dict) -> dict:
    """
    Classifica uma única questão via Groq.
    Retorna a questão enriquecida com dificuldade e justificativa.
    """
    texto = _extrair_texto_questao(questao)

    prompt = f"""Analise esta questão do ENEM e classifique sua complexidade.

{texto}

CRITÉRIOS:
- Fácil: {CRITERIOS['fácil']}
- Médio: {CRITERIOS['médio']}
- Difícil: {CRITERIOS['difícil']}

Responda APENAS com JSON válido, sem texto antes ou depois:
{{
  "dificuldade": "fácil" | "médio" | "difícil",
  "justificativa": "explicação pedagógica em 1-2 frases"
}}"""

    try:
        resposta = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=120,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        texto_resp = resposta.choices[0].message.content.strip()

        # Remove markdown code block se presente
        if texto_resp.startswith("```"):
            linhas = texto_resp.splitlines()
            texto_resp = "\n".join(linhas[1:-1] if linhas[-1].strip() == "```" else linhas[1:])

        dados = json.loads(texto_resp)
        dificuldade = dados.get("dificuldade", "médio").lower()
        if dificuldade not in ("fácil", "médio", "difícil"):
            dificuldade = "médio"
        justificativa = dados.get("justificativa", "")

    except Exception:
        dificuldade = "médio"
        justificativa = "Classificação automática — análise indisponível."

    resultado = dict(questao)
    resultado["dificuldade"] = dificuldade
    resultado["justificativa_dificuldade"] = justificativa
    return resultado


def classificar_top3(questoes: list[dict]) -> dict:
    """
    Recebe uma lista de questões e retorna um Top 3 ordenado:
    fácil → médio → difícil, com justificativa pedagógica de cada uma.

    Parâmetros:
        questoes: lista de dicts no formato padrão EduSynth/enem_api

    Retorna dict com:
        - facil:   questão classificada como fácil (dict com dificuldade e justificativa)
        - medio:   questão classificada como médio
        - dificil: questão classificada como difícil
        - total_analisadas: int
        - todas_classificadas: lista completa com classificações
        - erro: None ou mensagem de erro
    """
    if not questoes:
        return {
            "facil": None, "medio": None, "dificil": None,
            "total_analisadas": 0,
            "todas_classificadas": [],
            "erro": "Nenhuma questão fornecida para classificação.",
        }

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "facil": None, "medio": None, "dificil": None,
            "total_analisadas": 0,
            "todas_classificadas": [],
            "erro": "GROQ_API_KEY não encontrada no arquivo .env",
        }

    client = Groq(api_key=api_key)
    classificadas = []

    for q in questoes:
        classificada = _classificar_uma(client, q)
        classificadas.append(classificada)

    # Agrupa por nível
    por_nivel: dict[str, list] = {"fácil": [], "médio": [], "difícil": []}
    for q in classificadas:
        nivel = q.get("dificuldade", "médio")
        if nivel in por_nivel:
            por_nivel[nivel].append(q)

    def _pegar_melhor(nivel: str) -> dict | None:
        """Retorna a primeira questão do nível, com fallback para níveis adjacentes."""
        if por_nivel[nivel]:
            return por_nivel[nivel][0]
        # Fallback: tenta níveis adjacentes
        fallbacks = {
            "fácil":   ["médio", "difícil"],
            "médio":   ["fácil", "difícil"],
            "difícil": ["médio", "fácil"],
        }
        for fb in fallbacks.get(nivel, []):
            if por_nivel[fb]:
                q = dict(por_nivel[fb].pop(0))
                q["dificuldade"] = nivel
                q["justificativa_dificuldade"] += f" (reclassificado de '{fb}' por ausência de questões neste nível)"
                return q
        return None

    return {
        "facil":   _pegar_melhor("fácil"),
        "medio":   _pegar_melhor("médio"),
        "dificil": _pegar_melhor("difícil"),
        "total_analisadas": len(classificadas),
        "todas_classificadas": classificadas,
        "erro": None,
    }


if __name__ == "__main__":
    # Teste com questões simuladas
    questoes_exemplo = [
        {
            "titulo": "Questão 1 — ENEM 2022",
            "ano": 2022,
            "disciplina": "Ciências Humanas",
            "enunciado": "Assinale a alternativa que define corretamente o conceito de fordismo.",
            "contexto": "Assinale a alternativa que define corretamente o conceito de fordismo.",
            "alternativas": {
                "A": "Sistema de produção baseado na linha de montagem e produção em massa.",
                "B": "Modelo de gestão focado na flexibilização da produção.",
                "C": "Sistema financeiro criado por Henry Ford para bancar trabalhadores.",
                "D": "Movimento sindical surgido nas fábricas americanas.",
                "E": "Técnica de administração do tempo desenvolvida por Taylor.",
            },
            "gabarito": "A",
            "is_ai_generated": False,
        },
        {
            "titulo": "Questão 2 — ENEM 2019",
            "ano": 2019,
            "disciplina": "Ciências Humanas",
            "enunciado": "Analise o trecho a seguir e responda.",
            "contexto": (
                "A Revolução Industrial britânica do século XVIII introduziu transformações profundas "
                "nas relações de produção, deslocando o trabalho artesanal para o fabril e gerando "
                "a consolidação do proletariado urbano. Esse processo acelerou a urbanização e "
                "intensificou as contradições sociais que Marx e Engels analisariam posteriormente "
                "no Manifesto Comunista (1848), relacionando modo de produção capitalista, "
                "alienação do trabalho e luta de classes. Considerando esse contexto histórico "
                "e suas repercussões estruturais, analise as transformações nas relações de trabalho."
            ),
            "alternativas": {
                "A": "A mecanização eliminou completamente o trabalho humano nas fábricas.",
                "B": "O proletariado consolidou-se como classe social a partir da separação entre trabalhador e meios de produção.",
                "C": "A burguesia industrial sempre apoiou os movimentos operários por reconhecer a importância do trabalho.",
                "D": "O socialismo utópico foi a única resposta teórica às contradições do capitalismo industrial.",
                "E": "A urbanização ocorreu de forma planejada e ordenada em toda a Europa.",
            },
            "gabarito": "B",
            "is_ai_generated": False,
        },
        {
            "titulo": "Questão 3 — ENEM 2021",
            "ano": 2021,
            "disciplina": "Ciências Humanas",
            "enunciado": "O toyotismo surgiu no Japão após a Segunda Guerra Mundial. Assinale a característica que o diferencia do fordismo.",
            "contexto": "O toyotismo surgiu no Japão após a Segunda Guerra Mundial. Assinale a característica que o diferencia do fordismo.",
            "alternativas": {
                "A": "Produção em massa e padronização total dos produtos.",
                "B": "Linha de montagem contínua com alta especialização do operário.",
                "C": "Produção flexível e just-in-time com foco na demanda real do mercado.",
                "D": "Controle cronometrado das tarefas conforme o método de Taylor.",
                "E": "Salários altos para estimular o consumo dos próprios trabalhadores.",
            },
            "gabarito": "C",
            "is_ai_generated": False,
        },
    ]

    print("Classificando questões...\n")
    resultado = classificar_top3(questoes_exemplo)

    if resultado["erro"]:
        print(f"ERRO: {resultado['erro']}")
    else:
        print(f"Total analisadas: {resultado['total_analisadas']}\n")
        for nivel, chave in [("🟢 FÁCIL", "facil"), ("🟡 MÉDIO", "medio"), ("🔴 DIFÍCIL", "dificil")]:
            q = resultado[chave]
            if q:
                print(f"{nivel}: {q['titulo']}")
                print(f"  Justificativa: {q['justificativa_dificuldade']}\n")
