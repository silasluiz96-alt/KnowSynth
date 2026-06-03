"""
Sub-agente classificador de complexidade de questões do ENEM.

Recebe uma lista de questões (formato enem_api.py) e usa o Groq LLM
para analisar cada uma e retornar um Top 3 ordenado:
fácil → médio → difícil, com justificativa pedagógica.
"""

import os
import sys
from dotenv import load_dotenv

try:
    from utils.llm_client import chamar_llm, parse_resposta_json
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from utils.llm_client import chamar_llm, parse_resposta_json

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


def _classificar_lote(questoes: list[dict]) -> list[dict]:
    """
    Classifica todas as questões em uma única chamada LLM (economiza até 14 requests).
    Retorna as questões enriquecidas com dificuldade e justificativa.
    """
    blocos = []
    for i, q in enumerate(questoes):
        texto = _extrair_texto_questao(q)
        blocos.append(f"=== QUESTÃO {i} ===\n{texto}")

    prompt = f"""Analise as questões do ENEM abaixo e classifique a complexidade de cada uma.

{chr(10).join(blocos)}

CRITÉRIOS:
- fácil: {CRITERIOS['fácil']}
- médio: {CRITERIOS['médio']}
- difícil: {CRITERIOS['difícil']}

Responda APENAS com JSON válido — uma lista com exatamente {len(questoes)} objetos, na mesma ordem:
[
  {{"indice": 0, "dificuldade": "fácil"|"médio"|"difícil", "justificativa": "1-2 frases"}},
  ...
]"""

    r = chamar_llm(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        max_tokens=min(150 * len(questoes), 2000),
    )

    classificacoes: dict[int, dict] = {}
    if not r["erro"]:
        dados = parse_resposta_json(r["texto"])
        if isinstance(dados, list):
            for item in dados:
                idx = item.get("indice")
                nivel = (item.get("dificuldade") or "médio").lower()
                if idx is not None and nivel in ("fácil", "médio", "difícil"):
                    classificacoes[idx] = {
                        "dificuldade": nivel,
                        "justificativa": item.get("justificativa", ""),
                    }

    resultado = []
    for i, q in enumerate(questoes):
        q2 = dict(q)
        info = classificacoes.get(i, {})
        q2["dificuldade"] = info.get("dificuldade", "médio")
        q2["justificativa_dificuldade"] = info.get(
            "justificativa", "Classificação automática — análise indisponível."
        )
        resultado.append(q2)
    return resultado


def classificar_top3(questoes: list[dict]) -> dict:
    """
    Recebe uma lista de questões e retorna um Top 3 ordenado:
    fácil → médio → difícil, com justificativa pedagógica de cada uma.

    Parâmetros:
        questoes: lista de dicts no formato padrão KnowSynth/enem_api

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

    if not os.getenv("GROQ_API_KEY"):
        return {
            "facil": None, "medio": None, "dificil": None,
            "total_analisadas": 0,
            "todas_classificadas": [],
            "erro": "GROQ_API_KEY não encontrada no arquivo .env",
        }

    classificadas = _classificar_lote(questoes)

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

