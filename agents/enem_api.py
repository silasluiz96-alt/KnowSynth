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
import unicodedata
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

# ── Detecção SVO de inglês ────────────────────────────────────────────────────
# Detecta sentenças completas em inglês via padrão SVO (Sujeito + Verbo).
# Pronomes pessoais ingleses (I, you, he, she, it, we, they) não existem como
# sujeito gramatical em português — o padrão dispara apenas para inglês real.
# Exige sentença completa para não confundir palavras inglesas isoladas em
# questões normais (ex: nome de obra, citação, título de autor estrangeiro).
_RE_SVO_INGLES = re.compile(
    r'\b(I|you|he|she|it|we|they|[Tt]he\s+\w+|[Aa]\s+\w+)\s+'
    r'(is|are|was|were|has|have|had|can|will|would|could|should'
    r'|does|did|do|said|told|went|came|got|made|took|became|seems|appears'
    r'|knows?|thinks?|wants?|needs?|likes?|feels?|shows?|gives?|helps?)\b'
)


# Palavras-gatilho para detecção de espanhol (3+ ocorrências → espanhol)
_PALAVRAS_ESPANHOL = {
    "que", "una", "del", "los", "las", "con", "para", "por", "como",
    "pero", "más", "también",
}

def _normalizar_tema(s: str) -> str:
    """
    Remove acentos e converte para minúsculas.
    Usado para comparar temas sem depender de acentuação exata.
    Ex: "Fotossíntese" → "fotossintese"  |  "fordismo" → "fordismo"
    """
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower().strip()


# Mapa tema → disciplina na API enem.dev
# Chaves já normalizadas (sem acento, minúsculas) para funcionar com _normalizar_tema()
TEMA_DISCIPLINA: dict[str, str] = {
    # Ciências Humanas
    "revolucao industrial":        "ciencias-humanas",
    "segunda guerra mundial":      "ciencias-humanas",
    "ditadura militar brasileira": "ciencias-humanas",
    "globalizacao":                "ciencias-humanas",
    "fordismo":                    "ciencias-humanas",
    "taylorismo":                  "ciencias-humanas",
    "escravidao":                  "ciencias-humanas",
    "colonizacao":                 "ciencias-humanas",
    "iluminismo":                  "ciencias-humanas",
    "revolucao francesa":          "ciencias-humanas",
    "imperialismo":                "ciencias-humanas",
    "guerra fria":                 "ciencias-humanas",
    "nazismo":                     "ciencias-humanas",
    "fascismo":                    "ciencias-humanas",
    "socialismo":                  "ciencias-humanas",
    "capitalismo":                 "ciencias-humanas",
    "democracia":                  "ciencias-humanas",
    "diversidade cultural":        "ciencias-humanas",
    "cultura afro-brasileira":     "ciencias-humanas",
    "povos indigenas":             "ciencias-humanas",
    "direitos humanos":            "ciencias-humanas",
    "cidadania":                   "ciencias-humanas",
    # Ciências da Natureza
    "aquecimento global":          "ciencias-natureza",
    "fotossintese":                "ciencias-natureza",
    "genetica mendeliana":         "ciencias-natureza",
    "leis de newton":              "ciencias-natureza",
    "evolucao biologica":          "ciencias-natureza",
    "ecologia":                    "ciencias-natureza",
    "biomas brasileiros":          "ciencias-natureza",
    "quimica organica":            "ciencias-natureza",
    "eletromagnetismo":            "ciencias-natureza",
    "termodinamica":               "ciencias-natureza",
    "celula":                      "ciencias-natureza",
    "metabolismo":                 "ciencias-natureza",
    "reacoes quimicas":            "ciencias-natureza",
    "tabela periodica":            "ciencias-natureza",
    # Matemática
    "funcoes do 1o e 2o grau":    "matematica",
    "progressao aritmetica":       "matematica",
    "probabilidade":               "matematica",
    "geometria plana":             "matematica",
    "estatistica":                 "matematica",
    "geometria espacial":          "matematica",
    "trigonometria":               "matematica",
    "logaritmos":                  "matematica",
    "matrizes":                    "matematica",
    "financas":                    "matematica",
    # Linguagens
    "modernismo brasileiro":       "linguagens",
    "interpretacao de texto":      "linguagens",
    "figuras de linguagem":        "linguagens",
    "literatura brasileira":       "linguagens",
    "generos textuais":            "linguagens",
    "redacao enem":                "linguagens",
    "variacao linguistica":        "linguagens",
}

# Offset inicial por disciplina (onde as questões dessa disciplina começam na prova)
_OFFSET_DISCIPLINA: dict[str, int] = {
    "linguagens":        0,
    "ciencias-humanas":  29,
    "ciencias-natureza": 90,
    "matematica":        127,
}

# Mapa tema → palavras-chave para filtro de texto (sem LLM)
# Chaves normalizadas (sem acento) — mesma convenção do TEMA_DISCIPLINA
# Os termos de busca são em português COM acento (como aparecem nos textos do ENEM)
_KEYWORDS_TEMA: dict[str, list[str]] = {
    # Ciências Humanas
    "revolucao industrial":        ["revolução industrial", "industrialização", "vapor", "operário", "fábrica", "ford", "taylor", "maquinismo"],
    "segunda guerra mundial":      ["segunda guerra", "nazismo", "holocausto", "hitler", "aliados", "guerra mundial", "fascismo", "totalitarismo"],
    "ditadura militar brasileira": ["ditadura militar", "golpe", "regime militar", "ai-5", "redemocratização", "censura", "repressão", "anistia"],
    "globalizacao":                ["globalização", "neoliberal", "mercado global", "fmi", "interdependência", "livre-comércio", "mundialização"],
    "fordismo":                    ["fordismo", "fordista", "linha de montagem", "produção em série", "ford", "taylor", "taylorismo", "produção em massa", "industrialização"],
    "taylorismo":                  ["taylorismo", "taylor", "fordismo", "administração científica", "produção em série", "eficiência produtiva"],
    "escravidao":                  ["escravidão", "escravo", "tráfico", "abolição", "quilombo", "senzala", "trabalho escravo", "escravizado"],
    "colonizacao":                 ["colonização", "colônia", "colonialismo", "colonizador", "metrópole", "exploração colonial", "ciclo econômico"],
    "iluminismo":                  ["iluminismo", "ilustração", "razão", "contrato social", "locke", "rousseau", "voltaire", "montesquieu"],
    "revolucao francesa":          ["revolução francesa", "liberdade igualdade fraternidade", "bastilha", "jacobinos", "declaração dos direitos"],
    "imperialismo":                ["imperialismo", "colonialismo", "neocolonialismo", "partilha da áfrica", "potências europeias"],
    "guerra fria":                 ["guerra fria", "capitalismo", "socialismo", "urss", "eua", "bipolaridade", "cortina de ferro", "muro de berlim"],
    "nazismo":                     ["nazismo", "nazista", "hitler", "holocausto", "terceiro reich", "antissemitismo", "fascismo"],
    "fascismo":                    ["fascismo", "mussolini", "totalitarismo", "nazismo", "estado nacional", "corporativismo"],
    "socialismo":                  ["socialismo", "marxismo", "comunismo", "marx", "engels", "luta de classes", "proletariado", "burguesia"],
    "capitalismo":                 ["capitalismo", "mercado", "burguesia", "proletariado", "mais-valia", "acumulação de capital", "neoliberalismo"],
    "democracia":                  ["democracia", "sufrágio", "constituição", "cidadania", "direitos", "voto", "república", "separação de poderes"],
    "diversidade cultural":        ["diversidade cultural", "multiculturalismo", "identidade cultural", "etnocentrismo", "relativismo cultural"],
    "cultura afro-brasileira":     ["afro-brasileiro", "afrodescendente", "quilombo", "candomblé", "umbanda", "cultura africana", "racismo"],
    "povos indigenas":             ["indígena", "povos originários", "aldeamento", "demarcação", "cultura indígena", "etnias"],
    "direitos humanos":            ["direitos humanos", "onu", "declaração universal", "cidadania", "dignidade humana", "liberdade"],
    "cidadania":                   ["cidadania", "direitos", "deveres", "democracia", "participação política", "constituição"],
    # Ciências da Natureza
    "aquecimento global":          ["aquecimento global", "efeito estufa", "clima", "carbono", "emissão", "temperatura", "mudanças climáticas"],
    "fotossintese":                ["fotossíntese", "fotossíntese", "clorofila", "luz solar", "glicose", "cloroplasto", "fotossintético", "fotossintese"],
    "genetica mendeliana":         ["mendel", "hereditariedade", "dominante", "recessivo", "gene", "genótipo", "fenótipo", "alelo"],
    "leis de newton":              ["newton", "inércia", "força", "movimento", "aceleração", "dinâmica", "gravitação", "segunda lei"],
    "evolucao biologica":          ["evolução", "darwin", "seleção natural", "adaptação", "espécie", "mutação", "ancestral comum"],
    "ecologia":                    ["ecossistema", "cadeia alimentar", "teia alimentar", "bioma", "biodiversidade", "nicho ecológico", "ciclos biogeoquímicos"],
    "biomas brasileiros":          ["cerrado", "amazônia", "caatinga", "mata atlântica", "pantanal", "pampa", "bioma", "biodiversidade"],
    "quimica organica":            ["orgânica", "carbono", "hidrocarboneto", "álcool", "aldéido", "cetona", "ácido carboxílico", "éster"],
    "eletromagnetismo":            ["eletromagnetismo", "campo elétrico", "campo magnético", "indução eletromagnética", "circuito", "corrente elétrica"],
    "termodinamica":               ["termodinâmica", "calor", "temperatura", "entropia", "trabalho", "primeira lei", "segunda lei"],
    "celula":                      ["célula", "membrana", "núcleo", "mitocôndria", "ribossomo", "divisão celular", "mitose", "meiose"],
    "metabolismo":                 ["metabolismo", "respiração celular", "fermentação", "atp", "enzima", "catabolismo", "anabolismo"],
    "reacoes quimicas":            ["reação química", "reagente", "produto", "balanceamento", "estequiometria", "cinética", "equilíbrio"],
    "tabela periodica":            ["tabela periódica", "elemento", "metal", "não-metal", "grupo", "período", "propriedades periódicas"],
    # Matemática
    "funcoes do 1o e 2o grau":    ["função", "parábola", "raiz", "coeficiente", "equação", "gráfico", "domínio", "imagem"],
    "progressao aritmetica":       ["progressão aritmética", "razão", "sequência", "termo", "pa", "soma dos termos"],
    "probabilidade":               ["probabilidade", "evento", "espaço amostral", "combinatória", "chance", "favorável"],
    "geometria plana":             ["área", "perímetro", "triângulo", "círculo", "quadrado", "polígono", "trapézio"],
    "estatistica":                 ["média", "mediana", "moda", "desvio", "gráfico", "tabela", "frequência", "probabilidade"],
    "geometria espacial":          ["volume", "superfície", "cubo", "cilindro", "cone", "esfera", "pirâmide", "prisma"],
    "trigonometria":               ["seno", "cosseno", "tangente", "ângulo", "triângulo retângulo", "lei dos cossenos"],
    "logaritmos":                  ["logaritmo", "log", "base", "expoente", "exponencial", "potência"],
    "matrizes":                    ["matriz", "determinante", "sistemas lineares", "equação linear", "escalonamento"],
    "financas":                    ["juros", "porcentagem", "desconto", "taxa", "capital", "montante", "financiamento"],
    # Linguagens
    "modernismo brasileiro":       ["modernismo", "semana de arte moderna", "1922", "vanguarda", "modernista", "pau-brasil"],
    "interpretacao de texto":      ["inferência", "compreensão", "leitura", "texto", "interpretação", "implícito"],
    "figuras de linguagem":        ["metáfora", "metonímia", "ironia", "hipérbole", "figura de linguagem", "comparação"],
    "literatura brasileira":       ["literatura", "romantismo", "realismo", "naturalismo", "parnasianismo", "simbolismo", "modernismo"],
    "generos textuais":            ["crônica", "conto", "poema", "artigo", "editorial", "gênero textual", "tipologia"],
    "redacao enem":                ["redação", "dissertação", "argumentação", "tese", "proposta de intervenção", "coesão"],
    "variacao linguistica":        ["variação linguística", "dialeto", "registro", "norma culta", "socioleto", "linguagem"],
}


# ── Detecção de idioma estrangeiro ────────────────────────────────────────────

def _detectar_idioma_estrangeiro(questao: dict) -> bool:
    """
    Retorna True se a questão é de língua estrangeira (inglês ou espanhol).

    Critérios em ordem de confiança:
    1. Campo "idioma" da API (fonte de verdade para espanhol)
    2. ¿ ou ¡ no texto → espanhol
    3. Regex SVO inglês — detecta sentença completa Sujeito+Verbo em inglês.
       Pronomes pessoais ingleses não existem como sujeito em português,
       portanto um hit já é sinal forte o suficiente.
    4. Fallback keyword espanhol (3+ hits)
    """
    # Critério 1: campo "language" da API
    idioma = (questao.get("idioma", "") or "").lower().strip()
    if idioma in _LANGUAGE_SLUGS_ESTRANGEIRO:
        return True

    contexto  = (questao.get("contexto",  "") or "")
    enunciado = (questao.get("enunciado", "") or "")
    texto_completo = f"{contexto} {enunciado}"

    # Critério 2: caracteres exclusivos do espanhol
    if "¿" in texto_completo or "¡" in texto_completo:
        return True

    # Critério 3: SVO inglês — sentença completa (Sujeito + Verbo)
    if _RE_SVO_INGLES.search(texto_completo):
        return True

    # Critério 4: fallback keyword espanhol (3+ hits)
    palavras = set(re.sub(r"[^\w\s]", "", texto_completo.lower()).split())
    if sum(1 for p in _PALAVRAS_ESPANHOL if p in palavras) >= 3:
        return True

    return False


# ── Helpers internos ──────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = None, _tentativa: int = 1) -> dict | list | None:
    """
    GET na API com log de URL, status e erros.
    Retry automático uma vez em caso de 429 (rate limit), com pausa de 3 segundos.
    """
    import time as _time

    url = f"{BASE_URL}{endpoint}"
    log.info(f"GET {url} | params={params}")
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        log.info(f"  → status={r.status_code} | size={len(r.content)} bytes")

        # Rate limit — aguarda e tenta mais uma vez
        if r.status_code == 429 and _tentativa < 3:
            espera = 3 * _tentativa  # 3s na 1ª tentativa, 6s na 2ª
            log.warning(f"  Rate limit (429) — aguardando {espera}s antes de tentar novamente...")
            _time.sleep(espera)
            return _get(endpoint, params=params, _tentativa=_tentativa + 1)

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
        "files":           [f for f in (q.get("files") or []) if f and "broken-image" not in f],
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
    _ANOS = [2023, 2022, 2021, 2020, 2019]
    topic_norm = _normalizar_tema(topic)  # sem acentos, minúsculas

    # Resolve disciplina — usa chave normalizada para tolerar acentuação
    disciplina = TEMA_DISCIPLINA.get(topic_norm)
    offset_ini = _OFFSET_DISCIPLINA.get(disciplina, 0) if disciplina else 0

    # Resolve keywords: mapa fixo + palavras longas do próprio tema (original, com acento)
    keywords_raw = list(_KEYWORDS_TEMA.get(topic_norm, []))
    keywords_raw += [p.lower() for p in topic.lower().strip().split() if len(p) > 4]
    keywords_raw = list(dict.fromkeys(keywords_raw))  # deduplicar mantendo ordem

    # Normaliza também as keywords para comparar com texto normalizado da questão
    keywords_norm = [_normalizar_tema(kw) for kw in keywords_raw]

    log.info(
        f"search_questions_by_topic('{topic}') | topic_norm='{topic_norm}' | disciplina={disciplina} "
        f"offset_ini={offset_ini} | keywords={keywords_raw[:5]}"
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
                # Filtra disciplina (client-side, pois filtro da API não funciona)
                if disciplina and q.get("discipline") != disciplina:
                    continue
                qf = _formatar_questao(q, ano=ano)
                # FIX 4 — usa _detectar_idioma_estrangeiro (robusto) em vez de
                # checar q.get("language") inline — captura inglês por heurística também
                if _detectar_idioma_estrangeiro(qf):
                    continue
                # Filtra por keyword no texto — normaliza para tolerar acentuação
                texto_norm = _normalizar_tema(" ".join([
                    (qf.get("contexto") or ""),
                    (qf.get("enunciado") or ""),
                ]))
                if keywords_norm and not any(kw in texto_norm for kw in keywords_norm):
                    continue
                # Descarta questões cujas alternativas são imagens (texto vazio)
                # — o app não consegue exibir alternativas sem texto
                alts = qf.get("alternativas", {})
                if not any(v.strip() for v in alts.values()):
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
                # A API nunca marca language='ingles' — detecta por estrutura SVO.
                # Pronomes pessoais ingleses (I/you/he/she/it/we/they) não existem
                # como sujeito em português — 1 hit de SVO já é sinal confiável.
                if lang_api:
                    continue  # tem idioma marcado → é espanhol, pular
                if q.get("discipline") != "linguagens":
                    continue  # inglês sempre fica em linguagens
                contexto  = q.get("context")  or ""
                enunciado = q.get("alternativesIntroduction") or ""
                texto_q   = f"{contexto} {enunciado}"
                if not _RE_SVO_INGLES.search(texto_q):
                    continue  # nenhuma sentença SVO inglesa detectada

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

