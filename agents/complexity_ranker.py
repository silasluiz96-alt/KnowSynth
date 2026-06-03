"""
Classificador de complexidade de questões do ENEM — heurísticas locais.
Zero chamadas de API. Classificação por pontuação de texto.
"""

import re

# Palavras técnicas que indicam dificuldade elevada
_VOCAB_TECNICO = {
    "analisar", "inferir", "comparar", "sintetizar", "contextualizar",
    "correlacionar", "paradigma", "epistemológico", "ontológico", "dialético",
    "hegemonia", "fenômeno", "pressuposto", "contraditório", "abstrato",
    "ideológico", "estrutural", "conjuntural", "determinante", "pressupõe",
}

# Comandos simples (fácil)
_COMANDOS_FACIL = {"assinale", "identifique", "indique", "marque", "aponte"}

# Comandos relacionais (médio/difícil)
_COMANDOS_MEDIO = {"relacione", "explique", "justifique", "descreva", "diferencie"}

# Padrões que sugerem dados/gráficos/tabelas no enunciado
_PADRAO_DADOS = re.compile(
    r"(gráfico|tabela|quadro|figura|dado[s]?|porcentagem|%|estatística)", re.IGNORECASE
)


def _contar_palavras(texto: str) -> int:
    return len(texto.split()) if texto else 0


def _tem_vocab_tecnico(texto: str) -> bool:
    palavras = set(re.sub(r"[^\w\s]", "", texto.lower()).split())
    return bool(palavras & _VOCAB_TECNICO)


def _comando_questao(texto: str) -> str:
    """Retorna 'facil', 'medio' ou '' conforme o comando identificado."""
    palavras = set(re.sub(r"[^\w\s]", "", texto.lower()).split())
    if palavras & _COMANDOS_FACIL:
        return "facil"
    if palavras & _COMANDOS_MEDIO:
        return "medio"
    return ""


def classificar_questao(questao: dict) -> tuple[str, int, str]:
    """
    Calcula pontuação de complexidade e retorna (nivel, pontuacao, justificativa).

    Fácil  : 0-3 pontos
    Médio  : 4-6 pontos
    Difícil: 7+  pontos
    """
    enunciado = questao.get("enunciado", "") or ""
    contexto  = questao.get("contexto",  "") or ""

    # Usa o maior entre enunciado e contexto como texto principal
    texto_principal = contexto if len(contexto) > len(enunciado) else enunciado
    palavras_principal = _contar_palavras(texto_principal)

    # Texto de apoio é o outro campo (se diferente e não vazio)
    texto_apoio = contexto if texto_principal is enunciado else enunciado
    palavras_apoio = _contar_palavras(texto_apoio)

    pontos = 0
    motivos = []

    # ── Tamanho do texto principal ────────────────────────────────────────────
    if palavras_principal < 100:
        pontos += 1
        motivos.append("enunciado curto")
    elif palavras_principal <= 200:
        pontos += 2
        motivos.append("enunciado médio")
    else:
        pontos += 3
        motivos.append("enunciado longo")

    # ── Texto de apoio ────────────────────────────────────────────────────────
    if palavras_apoio == 0 or palavras_apoio < 50:
        pontos += 1
        motivos.append("sem texto de apoio ou muito curto")
    elif palavras_apoio <= 150:
        pontos += 2
        motivos.append("texto de apoio moderado")
    else:
        pontos += 2
        motivos.append("texto de apoio longo")

    # ── Vocabulário técnico ───────────────────────────────────────────────────
    texto_completo = f"{texto_principal} {texto_apoio}"
    if _tem_vocab_tecnico(texto_completo):
        pontos += 2
        motivos.append("vocabulário técnico denso")
    else:
        pontos += 1
        motivos.append("vocabulário acessível")

    # ── Comando da questão ────────────────────────────────────────────────────
    cmd = _comando_questao(texto_completo)
    if cmd == "facil":
        pontos += 1
        motivos.append("comando simples")
    elif cmd == "medio":
        pontos += 1
        motivos.append("comando relacional")

    # ── Dados, gráficos, tabelas ──────────────────────────────────────────────
    if _PADRAO_DADOS.search(texto_completo):
        pontos += 2
        motivos.append("referência a dados/gráficos/tabelas")

    # ── Nível final ───────────────────────────────────────────────────────────
    if pontos <= 3:
        nivel = "fácil"
    elif pontos <= 6:
        nivel = "médio"
    else:
        nivel = "difícil"

    justificativa = f"Pontuação {pontos}: {', '.join(motivos)}."
    return nivel, pontos, justificativa


def classificar_lote(questoes: list[dict]) -> list[dict]:
    """
    Classifica uma lista inteira de questões sem nenhuma chamada de API.
    Retorna as questões enriquecidas com 'dificuldade' e 'justificativa_dificuldade'.
    """
    resultado = []
    for q in questoes:
        nivel, pontos, justificativa = classificar_questao(q)
        q2 = dict(q)
        q2["dificuldade"] = nivel
        q2["pontuacao_complexidade"] = pontos
        q2["justificativa_dificuldade"] = justificativa
        resultado.append(q2)
    return resultado


def classificar_top3(questoes: list[dict]) -> dict:
    """
    Recebe uma lista de questões e retorna exatamente 1 fácil, 1 média e 1 difícil.

    Se não houver questão em algum nível, usa a mais próxima pela pontuação.
    Zero chamadas de API.

    Retorna dict com: facil, medio, dificil, total_analisadas, todas_classificadas, erro.
    """
    if not questoes:
        return {
            "facil": None, "medio": None, "dificil": None,
            "total_analisadas": 0,
            "todas_classificadas": [],
            "erro": "Nenhuma questão fornecida para classificação.",
        }

    classificadas = classificar_lote(questoes)

    # Ordena por pontuação para facilitar o fallback
    classificadas_ord = sorted(classificadas, key=lambda q: q.get("pontuacao_complexidade", 0))

    por_nivel: dict[str, list] = {"fácil": [], "médio": [], "difícil": []}
    for q in classificadas:
        nivel = q.get("dificuldade", "médio")
        if nivel in por_nivel:
            por_nivel[nivel].append(q)

    def _pegar(nivel: str) -> dict | None:
        if por_nivel[nivel]:
            return por_nivel[nivel][0]
        # Fallback: pega a questão com pontuação mais próxima do nível desejado
        alvo = {"fácil": 2, "médio": 5, "difícil": 8}[nivel]
        mais_proxima = min(
            classificadas_ord,
            key=lambda q: abs(q.get("pontuacao_complexidade", 0) - alvo),
            default=None,
        )
        if mais_proxima:
            q2 = dict(mais_proxima)
            original = q2["dificuldade"]
            q2["dificuldade"] = nivel
            q2["justificativa_dificuldade"] += (
                f" (reclassificado de '{original}' — sem questões no nível {nivel})"
            )
            return q2
        return None

    return {
        "facil":              _pegar("fácil"),
        "medio":              _pegar("médio"),
        "dificil":            _pegar("difícil"),
        "total_analisadas":   len(classificadas),
        "todas_classificadas": classificadas,
        "erro":               None,
    }


if __name__ == "__main__":
    questoes_exemplo = [
        {
            "titulo": "Questão 1 — ENEM 2022",
            "ano": 2022,
            "disciplina": "Ciências Humanas",
            "enunciado": "Assinale a alternativa que define corretamente o conceito de fordismo.",
            "contexto": "",
            "alternativas": {
                "A": "Sistema de produção baseado na linha de montagem e produção em massa.",
                "B": "Modelo de gestão focado na flexibilização da produção.",
                "C": "Sistema financeiro criado por Henry Ford para bancar trabalhadores.",
                "D": "Movimento sindical surgido nas fábricas americanas.",
                "E": "Técnica de administração do tempo desenvolvida por Taylor.",
            },
            "gabarito": "A",
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
                "B": "O proletariado consolidou-se como classe social.",
                "C": "A burguesia industrial sempre apoiou os movimentos operários.",
                "D": "O socialismo utópico foi a única resposta teórica.",
                "E": "A urbanização ocorreu de forma planejada em toda a Europa.",
            },
            "gabarito": "B",
        },
        {
            "titulo": "Questão 3 — ENEM 2021",
            "ano": 2021,
            "disciplina": "Ciências Humanas",
            "enunciado": (
                "O gráfico abaixo apresenta a correlacionar entre o paradigma epistemológico "
                "das relações dialéticas de hegemonia e a estrutura ontológica do fenômeno "
                "da globalização no contexto das transformações do modo de produção capitalista "
                "tardio. Considerando os dados apresentados e o contexto histórico das "
                "transformações estruturais do século XXI, inferir a alternativa que melhor "
                "sintetiza a dinâmica contextualizar das contradições ideológicas."
            ),
            "contexto": (
                "Tabela com dados estatísticos de desigualdade global entre 2000 e 2020, "
                "apresentando porcentagem de concentração de renda nos 1% mais ricos."
            ),
            "alternativas": {
                "A": "A globalização reduziu as desigualdades entre países desenvolvidos e em desenvolvimento.",
                "B": "O capital financeiro substituiu completamente o capital produtivo.",
                "C": "A hegemonia dos países centrais se manteve através de mecanismos financeiros.",
                "D": "O protecionismo foi a resposta dominante às crises do capitalismo.",
                "E": "A tecnologia eliminou as barreiras entre classes sociais.",
            },
            "gabarito": "C",
        },
    ]

    print("Classificando sem API...\n")
    resultado = classificar_top3(questoes_exemplo)

    print(f"Total analisadas: {resultado['total_analisadas']}\n")
    for nivel, chave in [("🟢 FÁCIL", "facil"), ("🟡 MÉDIO", "medio"), ("🔴 DIFÍCIL", "dificil")]:
        q = resultado[chave]
        if q:
            print(f"{nivel}: {q['titulo']}")
            print(f"  Pontuação : {q.get('pontuacao_complexidade')}")
            print(f"  Justificativa: {q['justificativa_dificuldade']}\n")
