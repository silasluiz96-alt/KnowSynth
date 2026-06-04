"""
Agente de integração com a API pública enem.dev
https://api.enem.dev/v1

CORREÇÕES aplicadas:
- _formatar_questao: alternativas agora lidas da lista [{letter, text, isCorrect}]
- search_questions_by_topic: busca paginada em todos os anos (não só 45/ano)
  + termos expandidos (sinônimos) + fallback com questões aleatórias quando 0 resultados
- Logs detalhados em cada chamada (URL, status, quantidade)
- Gabarito lido de correctAlternative E de isCorrect nas alternativas (dupla verificação)
"""

import os
import re
import sys
import json
import random
import logging
from dotenv import load_dotenv
import requests

load_dotenv()

logging.basicConfig(level=logging.INFO, format="[enem_api] %(message)s")
log = logging.getLogger("enem_api")

BASE_URL = "https://api.enem.dev/v1"
TIMEOUT  = 20

DISCIPLINES = {
    "ciencias-humanas":  "Ciências Humanas e suas Tecnologias",
    "ciencias-natureza": "Ciências da Natureza e suas Tecnologias",
    "linguagens":        "Linguagens, Códigos e suas Tecnologias",
    "matematica":        "Matemática e suas Tecnologias",
}

# Valores do campo "language" na API enem.dev que indicam idioma estrangeiro
_LANGUAGE_SLUGS_ESTRANGEIRO = {"ingles", "espanhol", "english", "spanish"}

# Palavras-gatilho para detecção de inglês (3+ ocorrências → inglês)
_PALAVRAS_INGLES = {
    "the", "is", "are", "was", "were", "have", "has", "that", "this",
    "with", "from", "they", "their", "would", "could", "should",
}

# Palavras-gatilho para detecção de espanhol (3+ ocorrências → espanhol)
_PALAVRAS_ESPANHOL = {
    "que", "una", "del", "los", "las", "con", "para", "por", "como",
    "pero", "más", "también",
}

# Mapa tema → disciplina na API enem.dev
TEMA_DISCIPLINA: dict[str, str] = {
    # Ciências Humanas
    "revolução industrial":        "ciencias-humanas",
    "segunda guerra mundial":      "ciencias-humanas",
    "ditadura militar brasileira": "ciencias-humanas",
    "globalização":                "ciencias-humanas",
    # Ciências da Natureza
    "aquecimento global":          "ciencias-natureza",
    "fotossíntese":                "ciencias-natureza",
    "genética mendeliana":         "ciencias-natureza",
    "leis de newton":              "ciencias-natureza",
    # Matemática
    "funções do 1º e 2º grau":    "matematica",
    "progressão aritmética":       "matematica",
    "probabilidade":               "matematica",
    "geometria plana":             "matematica",
    # Linguagens
    "modernismo brasileiro":       "linguagens",
    "interpretação de texto":      "linguagens",
    "figuras de linguagem":        "linguagens",
}

# Offset inicial por disciplina (onde as questões dessa disciplina começam na prova)
_OFFSET_DISCIPLINA: dict[str, int] = {
    "linguagens":        0,
    "ciencias-humanas":  29,
    "ciencias-natureza": 90,
    "matematica":        127,
}

# Mapa tema → palavras-chave para filtro de texto (sem LLM)
_KEYWORDS_TEMA: dict[str, list[str]] = {
    # Ciências Humanas
    "revolução industrial":        ["revolução industrial", "industrialização", "vapor", "operário", "fábrica", "ford", "taylor"],
    "segunda guerra mundial":      ["segunda guerra", "nazismo", "holocausto", "hitler", "aliados", "guerra mundial"],
    "ditadura militar brasileira": ["ditadura militar", "golpe", "regime militar", "AI-5", "redemocratização", "censura"],
    "globalização":                ["globalização", "neoliberal", "mercado global", "fmi", "interdependência", "livre-comércio"],
    # Ciências da Natureza
    "aquecimento global":          ["aquecimento global", "efeito estufa", "clima", "carbono", "emissão", "temperatura"],
    "fotossíntese":                ["fotossíntese", "clorofila", "luz solar", "glicose", "cloroplasto", "fotossintético"],
    "genética mendeliana":         ["mendel", "hereditariedade", "dominante", "recessivo", "gene", "genótipo", "fenótipo"],
    "leis de newton":              ["newton", "inércia", "força", "movimento", "aceleração", "dinâmica", "gravitação"],
    # Matemática
    "funções do 1º e 2º grau":    ["função", "parábola", "raiz", "coeficiente", "equação", "gráfico"],
    "progressão aritmética":       ["progressão aritmética", "razão", "sequência", "termo", "pa"],
    "probabilidade":               ["probabilidade", "evento", "espaço amostral", "combinatória", "chance"],
    "geometria plana":             ["área", "perímetro", "triângulo", "círculo", "quadrado", "polígono"],
    # Linguagens
    "modernismo brasileiro":       ["modernismo", "semana de arte moderna", "1922", "vanguarda", "modernista"],
    "interpretação de texto":      ["inferência", "compreensão", "leitura", "texto", "interpretação"],
    "figuras de linguagem":        ["metáfora", "metonímia", "ironia", "hipérbole", "figura de linguagem"],
}


# ── Detecção de idioma estrangeiro ────────────────────────────────────────────

def _detectar_idioma_estrangeiro(questao: dict) -> bool:
    """
    Retorna True se a questão é de língua estrangeira (inglês ou espanhol).

    Critérios em ordem de confiança:
    1. Campo "idioma" preenchido pela API (fonte de verdade)
    2. ¿ ou ¡ no texto → espanhol
    3. Fallback: palavras-gatilho de inglês ou espanhol (3+ hits)
    """
    # Critério 1: campo "language" da API — mais confiável
    idioma = (questao.get("idioma", "") or "").lower().strip()
    if idioma in _LANGUAGE_SLUGS_ESTRANGEIRO:
        return True

    contexto = (questao.get("contexto", "") or "").lower()
    texto_completo = contexto + " " + (questao.get("enunciado", "") or "").lower()

    # Critério 2: caracteres exclusivos do espanhol
    if "¿" in texto_completo or "¡" in texto_completo:
        return True

    # Critério 3: fallback por palavras-gatilho (3+ hits)
    palavras = set(re.sub(r"[^\w\s]", "", contexto).split())
    if sum(1 for p in _PALAVRAS_INGLES if p in palavras) >= 3:
        return True
    if sum(1 for p in _PALAVRAS_ESPANHOL if p in palavras) >= 3:
        return True

    return False


# ── Helpers internos ──────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = None) -> dict | list | None:
    """GET na API com log de URL, status e erros."""
    url = f"{BASE_URL}{endpoint}"
    log.info(f"GET {url} | params={params}")
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        log.info(f"  → status={r.status_code} | size={len(r.content)} bytes")
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Não foi possível conectar à API enem.dev.")
    except requests.exceptions.Timeout:
        raise TimeoutError("Timeout na API enem.dev.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Erro HTTP {r.status_code}: {e}")
    except Exception as e:
        raise RuntimeError(f"Erro inesperado: {e}")


def _formatar_questao(q: dict, ano: int = None) -> dict:
    """
    Normaliza uma questão da API para o formato padrão KnowSynth.

    CORREÇÃO: alternativas vêm como lista [{letter, text, isCorrect, file}]
    — não como dicionário. Gabarito lido de correctAlternative com fallback
    em isCorrect.
    """
    alternativas = {}
    gabarito_por_isCorrect = ""

    for alt in q.get("alternatives", []):
        letra = alt.get("letter", "").upper()
        texto = alt.get("text") or ""  # None explícito da API vira ""
        if letra:
            alternativas[letra] = texto
        if alt.get("isCorrect"):
            gabarito_por_isCorrect = letra

    # Gabarito: prioriza campo correctAlternative, fallback em isCorrect
    gabarito = (q.get("correctAlternative") or gabarito_por_isCorrect or "").upper()

    # Enunciado: alternativesIntroduction é o comando da questão
    # context é o texto de apoio
    enunciado = q.get("alternativesIntroduction", "") or ""
    contexto  = q.get("context", "") or ""

    return {
        "titulo":          q.get("title", ""),
        "indice":          q.get("index"),
        "enunciado":       enunciado,
        "contexto":        contexto,
        "alternativas":    alternativas,
        "gabarito":        gabarito,
        "gabarito_interno": gabarito,   # compatibilidade com Estrategista
        "ano":             q.get("year") or ano,
        "disciplina":      DISCIPLINES.get(q.get("discipline", ""), q.get("discipline", "")),
        "disciplina_slug": q.get("discipline", ""),
        "idioma":          q.get("language"),
        "fonte":           "enem.dev (questão oficial ENEM)",
        "dificuldade":     None,
        "is_ai_generated": False,
    }


def _buscar_paginas(ano: int, discipline: str = None, max_questoes: int = 200) -> list[dict]:
    """
    Busca todas as questões de um ano usando paginação automática.
    Retorna lista de questões formatadas.
    """
    todas = []
    offset = 0
    limit  = 45  # máximo razoável por página

    while len(todas) < max_questoes:
        params = {"limit": limit, "offset": offset}
        if discipline:
            params["discipline"] = discipline

        try:
            dados = _get(f"/exams/{ano}/questions", params=params)
        except Exception as e:
            log.warning(f"  Falha ao buscar ano {ano} offset {offset}: {e}")
            break

        if not dados:
            break

        questoes_bruto = dados.get("questions", [])
        meta           = dados.get("metadata", {})
        total_api      = meta.get("total", 0)

        log.info(f"  ano={ano} offset={offset} → {len(questoes_bruto)} questões (total API: {total_api})")

        for q in questoes_bruto:
            todas.append(_formatar_questao(q, ano=ano))

        # Verifica se há mais páginas
        if not meta.get("hasMore", False) or len(todas) >= total_api:
            break

        offset += limit

    log.info(f"  Total coletado para {ano}: {len(todas)} questões")
    return todas


def _termos_busca(topic: str) -> list[str]:
    """Retorna lista de termos para busca: o próprio topic + expansões."""
    topic_lower = topic.lower().strip()
    termos = [topic_lower]

    # Expansão direta
    for chave, sinonimos in _EXPANSAO_TEMAS.items():
        if chave in topic_lower or topic_lower in chave:
            termos.extend(sinonimos)
            break

    # Palavras do próprio tema (para temas compostos)
    palavras = [p for p in topic_lower.split() if len(p) > 4]
    termos.extend(palavras)

    return list(dict.fromkeys(termos))  # remove duplicatas mantendo ordem


def _questao_contem_tema(q: dict, termos: list[str]) -> bool:
    """Verifica se algum dos termos aparece no texto completo da questão."""
    texto = " ".join([
        q.get("contexto", "") or "",
        q.get("enunciado", "") or "",
        " ".join(v for v in (q.get("alternativas") or {}).values() if v),
    ]).lower()

    return any(t in texto for t in termos)


# ── Funções públicas ──────────────────────────────────────────────────────────

def get_exams() -> list[dict]:
    """Lista todos os anos disponíveis na API enem.dev."""
    dados = _get("/exams")
    if not isinstance(dados, list):
        return []
    return [
        {
            "ano":         exam.get("year"),
            "titulo":      exam.get("title"),
            "disciplinas": [d["value"] for d in exam.get("disciplines", [])],
            "idiomas":     [l["value"] for l in exam.get("languages", [])],
        }
        for exam in dados
    ]


def get_questions(year: int, discipline: str = None, limit: int = 10, offset: int = 0) -> dict:
    """Busca questões por ano e disciplina com paginação."""
    params = {"limit": limit, "offset": offset}
    if discipline:
        params["discipline"] = discipline

    dados = _get(f"/exams/{year}/questions", params=params)
    if not dados:
        return {"total": 0, "has_more": False, "questoes": []}

    questoes = [_formatar_questao(q, ano=year) for q in dados.get("questions", [])]
    meta     = dados.get("metadata", {})
    log.info(f"get_questions(year={year}) → {len(questoes)} questões (total={meta.get('total')})")

    return {
        "total":    meta.get("total", len(questoes)),
        "has_more": meta.get("hasMore", False),
        "limit":    meta.get("limit", limit),
        "offset":   meta.get("offset", offset),
        "questoes": questoes,
    }


def get_random_question(discipline: str = None) -> dict | None:
    """Retorna uma questão aleatória, opcionalmente filtrada por disciplina."""
    exames = get_exams()
    if not exames:
        return None

    anos = [e["ano"] for e in exames if e["ano"]]
    for _ in range(3):
        ano      = random.choice(anos)
        resultado = get_questions(ano, discipline=discipline, limit=45)
        questoes  = resultado.get("questoes", [])
        if questoes:
            return random.choice(questoes)

    return None


def search_questions_by_topic(topic: str, limit: int = 10) -> list[dict]:
    """
    Busca questões dos anos 2021-2023 filtrando por disciplina e keyword.
    Zero chamadas LLM.

    Fluxo:
    1. Resolve disciplina e keywords do tema via TEMA_DISCIPLINA / _KEYWORDS_TEMA
    2. Busca a partir do offset correto da disciplina (evita varrer blocos errados)
    3. Para ao acumular 10 questões da disciplina que contenham keyword do tema
    4. Retorna as brutas para classificar_top3() no caller
    """
    _ANOS = [2023, 2022, 2021]
    topic_lower = topic.lower().strip()

    # Resolve disciplina
    disciplina = TEMA_DISCIPLINA.get(topic_lower)
    offset_ini = _OFFSET_DISCIPLINA.get(disciplina, 0) if disciplina else 0

    # Resolve keywords: mapa fixo + palavras longas do próprio tema
    keywords = list(_KEYWORDS_TEMA.get(topic_lower, []))
    keywords += [p.lower() for p in topic_lower.split() if len(p) > 4]
    keywords = list(dict.fromkeys(keywords))  # deduplicar mantendo ordem

    log.info(
        f"search_questions_by_topic('{topic}') | disciplina={disciplina} "
        f"offset_ini={offset_ini} | keywords={keywords[:5]}"
    )

    _META   = 10
    encontradas: list[dict] = []

    for ano in _ANOS:
        if len(encontradas) >= _META:
            break
        offset = offset_ini
        while len(encontradas) < _META:
            try:
                dados = _get(f"/exams/{ano}/questions", params={"limit": 45, "offset": offset})
            except Exception as e:
                log.warning(f"  Erro ano={ano} offset={offset}: {e}")
                break

            if not dados:
                break

            questoes_pagina = dados.get("questions", [])
            if not questoes_pagina:
                break

            for q in questoes_pagina:
                # Filtra idioma estrangeiro
                if (q.get("language") or ""):
                    continue
                # Filtra disciplina (client-side, pois filtro da API não funciona)
                if disciplina and q.get("discipline") != disciplina:
                    continue
                qf = _formatar_questao(q, ano=ano)
                # Filtra por keyword no texto
                texto = " ".join([
                    (qf.get("contexto") or ""),
                    (qf.get("enunciado") or ""),
                ]).lower()
                if keywords and not any(kw in texto for kw in keywords):
                    continue
                encontradas.append(qf)
                if len(encontradas) >= _META:
                    break

            meta = dados.get("metadata", {})
            if not meta.get("hasMore", False):
                break
            offset += 45

        log.info(f"  ano={ano} → {len(encontradas)} questões acumuladas para '{topic}'")

    log.info(f"  Total: {len(encontradas)} questões para '{topic}'")
    return encontradas


def get_questions_by_difficulty(topic: str, discipline: str = None) -> dict:
    """
    Busca questões do tema, classifica com Groq e retorna 3 (fácil/médio/difícil).
    """
    questoes = search_questions_by_topic(topic, limit=15)

    if discipline and questoes:
        filtradas = [q for q in questoes if q.get("disciplina_slug") == discipline]
        questoes  = filtradas if filtradas else questoes

    if len(questoes) < 3:
        return {
            "facil": None, "media": None, "dificil": None,
            "total_analisadas": len(questoes),
            "erro": f"Apenas {len(questoes)} questão(ões) encontrada(s) para '{topic}'.",
        }

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "facil": None, "media": None, "dificil": None,
            "total_analisadas": 0,
            "erro": "GROQ_API_KEY não encontrada.",
        }

    client = Groq(api_key=api_key)
    classificadas = []

    for q in questoes:
        enunciado = q.get("contexto") or q.get("enunciado") or ""
        alts_txt  = "\n".join(f"{l}) {t}" for l, t in q.get("alternativas", {}).items())
        prompt    = (
            f"Classifique a dificuldade desta questão do ENEM.\n\n"
            f"QUESTÃO:\n{enunciado[:1000]}\n\nALTERNATIVAS:\n{alts_txt[:500]}\n\n"
            f"Critérios: extensão do enunciado, complexidade do vocabulário, "
            f"número de conceitos, nível de abstração.\n\n"
            f"Responda APENAS com uma palavra: fácil, média ou difícil"
        )
        try:
            resp  = client.chat.completions.create(
                model="llama-3.3-70b-versatile", max_tokens=10,
                messages=[
                    {"role": "system", "content": "Responda APENAS: fácil, média ou difícil."},
                    {"role": "user",   "content": prompt},
                ],
            )
            nivel = resp.choices[0].message.content.strip().lower()
            if nivel not in ("fácil", "média", "difícil"):
                nivel = "média"
        except Exception:
            nivel = "média"

        q2 = dict(q)
        q2["dificuldade"] = nivel
        classificadas.append(q2)

    por_nivel = {"fácil": [], "média": [], "difícil": []}
    for q in classificadas:
        nivel = q.get("dificuldade", "média")
        if nivel in por_nivel:
            por_nivel[nivel].append(q)

    def _pegar(nivel):
        if por_nivel[nivel]:
            return por_nivel[nivel][0]
        for fb in ("média", "fácil", "difícil"):
            if por_nivel[fb]:
                q = dict(por_nivel[fb].pop(0))
                q["dificuldade"] = nivel
                return q
        return None

    return {
        "facil":            _pegar("fácil"),
        "media":            _pegar("média"),
        "dificil":          _pegar("difícil"),
        "total_analisadas": len(classificadas),
        "erro":             None,
    }


def search_language_questions(language: str) -> list[dict]:
    """
    Busca até 6 questões de língua estrangeira dos anos 2021-2023.

    language: "ingles" ou "espanhol"

    Estratégia por idioma:
    - espanhol: filtra pelo campo language='espanhol' da API (confiável)
    - ingles: a API nunca retorna language='ingles' — usa heurística de
      palavras-gatilho em questões de linguagens com language=null
    """
    _ANOS = [2023, 2022, 2021]
    log.info(f"search_language_questions('{language}') | anos: {_ANOS}")

    questoes: list[dict] = []

    for ano in _ANOS:
        if len(questoes) >= 6:
            break
        # Questões de idioma ficam no início da prova (offset 0 já cobre)
        try:
            dados = _get(f"/exams/{ano}/questions", params={"limit": 45, "offset": 0})
        except Exception as e:
            log.warning(f"  Erro ao buscar ano {ano}: {e}")
            continue

        if not dados:
            continue

        for q in dados.get("questions", []):
            lang_api = (q.get("language") or "").lower().strip()

            if language == "espanhol":
                # Campo language é confiável para espanhol
                if lang_api != "espanhol":
                    continue

            elif language == "ingles":
                # A API nunca marca language='ingles' — detecta por heurística
                if lang_api:
                    continue  # tem idioma marcado → é espanhol, pular
                if q.get("discipline") != "linguagens":
                    continue  # inglês sempre fica em linguagens
                contexto = (q.get("context") or "").lower()
                palavras = set(re.sub(r"[^\w\s]", "", contexto).split())
                if sum(1 for p in _PALAVRAS_INGLES if p in palavras) < 3:
                    continue  # não parece inglês

            questoes.append(_formatar_questao(q, ano=ano))
            if len(questoes) >= 6:
                break

        log.info(f"  ano={ano} → {len(questoes)} questões de {language} acumuladas")

    log.info(f"  Total: {len(questoes)} questões de {language}")
    return questoes


# ── Teste local ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== 1. ANOS DISPONÍVEIS ===")
    for e in get_exams()[:3]:
        print(f"  {e['titulo']}")

    print("\n=== 2. QUESTÕES 2023 — 3 primeiras ===")
    res = get_questions(2023, limit=3)
    print(f"  Total disponível: {res['total']}")
    for q in res["questoes"]:
        print(f"  [{q['ano']}] {q['titulo']} | Gabarito: {q['gabarito']} | alts: {list(q['alternativas'].keys())}")

    print("\n=== 3. BUSCA POR TEMA: fordismo ===")
    qs = search_questions_by_topic("fordismo", limit=5)
    print(f"  {len(qs)} questões encontradas")
    for q in qs:
        fb = " [FALLBACK]" if q.get("_fallback") else ""
        print(f"  [{q['ano']}] {q['titulo']}{fb}")

    print("\n=== 4. BUSCA POR TEMA: trabalho ===")
    qs2 = search_questions_by_topic("trabalho", limit=5)
    print(f"  {len(qs2)} questões encontradas")
    for q in qs2:
        print(f"  [{q['ano']}] {q['titulo'][:70]}")

