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
import random
import logging
from dotenv import load_dotenv
import requests
from groq import Groq

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

# Mapa de termos expandidos para busca por tema
# Quando o tema não for encontrado literalmente, tenta sinônimos relacionados
_EXPANSAO_TEMAS = {
    "fordismo":             ["ford", "linha de montagem", "producao em serie", "taylorismo"],
    "toyotismo":            ["toyota", "just-in-time", "kanban", "producao flexivel"],
    "globalização":         ["globalizacao", "neoliberal", "mercado global", "fmi"],
    "fotossíntese":         ["fotossintese", "clorofila", "luz solar", "glicose"],
    "genética mendeliana":  ["mendel", "hereditariedade", "dominante", "recessivo"],
    "leis de newton":       ["newton", "inercia", "forcas", "movimento"],
    "revolução industrial": ["revolucao industrial", "vapor", "industrializacao", "operario"],
    "iluminismo":           ["iluminismo", "luzes", "razao", "voltaire", "rousseau"],
    "aquecimento global":   ["aquecimento global", "efeito estufa", "clima", "carbono"],
    "modernismo brasileiro":["modernismo", "semana de arte moderna", "1922"],
}


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
        texto = alt.get("text", "")
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
        " ".join((q.get("alternativas") or {}).values()),
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


def search_questions_by_topic(topic: str, limit: int = 15) -> list[dict]:
    """
    Busca questões relacionadas a um tema percorrendo todos os anos disponíveis
    com paginação completa.

    MELHORIAS:
    - Paginação automática (não só 45/ano)
    - Termos expandidos (sinônimos automáticos)
    - Fallback: se 0 resultados, retorna questões aleatórias dos anos recentes

    Retorna até `limit` questões.
    """
    exames = get_exams()
    if not exames:
        log.warning("get_exams() retornou vazio")
        return []

    anos    = sorted([e["ano"] for e in exames if e["ano"]], reverse=True)
    termos  = _termos_busca(topic)
    log.info(f"search_questions_by_topic('{topic}') | termos: {termos} | anos: {anos[:5]}")

    encontradas = []

    for ano in anos:
        if len(encontradas) >= limit:
            break
        try:
            todas_do_ano = _buscar_paginas(ano, max_questoes=200)
            for q in todas_do_ano:
                if _questao_contem_tema(q, termos):
                    encontradas.append(q)
                    log.info(f"  ✓ Encontrada: [{ano}] {q.get('titulo','')[:60]}")
                    if len(encontradas) >= limit:
                        break
        except Exception as e:
            log.warning(f"  Erro ao processar ano {ano}: {e}")
            continue

    log.info(f"search_questions_by_topic → {len(encontradas)} questões encontradas para '{topic}'")

    # Fallback: se 0 resultados, retorna questões aleatórias dos 3 anos mais recentes
    if not encontradas:
        log.warning(f"Nenhuma questão encontrada para '{topic}'. Usando fallback aleatório.")
        pool = []
        for ano in anos[:3]:
            try:
                pool.extend(_buscar_paginas(ano, max_questoes=90))
            except Exception:
                continue

        if pool:
            encontradas = random.sample(pool, min(limit, len(pool)))
            # Marca que são de fallback (tema não encontrado)
            for q in encontradas:
                q["_fallback"] = True
            log.info(f"  Fallback: {len(encontradas)} questões aleatórias retornadas")

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

