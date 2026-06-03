"""
Agente de integração com a API pública enem.dev
https://api.enem.dev/v1

Fornece questões reais do ENEM com classificação de dificuldade via Groq.
Todas as questões retornadas têm is_ai_generated=False.
"""

import os
import random
from pathlib import Path
from dotenv import load_dotenv
import requests
from groq import Groq

load_dotenv()

BASE_URL = "https://api.enem.dev/v1"
TIMEOUT = 15  # segundos

# Disciplinas válidas conforme a API
DISCIPLINES = {
    "ciencias-humanas":   "Ciências Humanas e suas Tecnologias",
    "ciencias-natureza":  "Ciências da Natureza e suas Tecnologias",
    "linguagens":         "Linguagens, Códigos e suas Tecnologias",
    "matematica":         "Matemática e suas Tecnologias",
}


# ── Helpers internos ──────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = None) -> dict | list | None:
    """Faz GET na API enem.dev com tratamento de erros."""
    try:
        url = f"{BASE_URL}{endpoint}"
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Não foi possível conectar à API enem.dev. Verifique sua conexão.")
    except requests.exceptions.Timeout:
        raise TimeoutError("A API enem.dev demorou demais para responder. Tente novamente.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Erro HTTP na API enem.dev: {e}")
    except Exception as e:
        raise RuntimeError(f"Erro inesperado ao acessar a API enem.dev: {e}")


def _formatar_questao(q: dict, ano: int = None) -> dict:
    """Normaliza uma questão da API para o formato padrão do EduSynth."""
    alternativas = {}
    for alt in q.get("alternatives", []):
        letra = alt.get("letter", "").upper()
        alternativas[letra] = alt.get("text", "")

    return {
        "titulo": q.get("title", ""),
        "indice": q.get("index"),
        "enunciado": q.get("alternativesIntroduction", "") or q.get("context", ""),
        "contexto": q.get("context", ""),
        "alternativas": alternativas,
        "gabarito": q.get("correctAlternative", "").upper(),
        "ano": q.get("year") or ano,
        "disciplina": DISCIPLINES.get(q.get("discipline", ""), q.get("discipline", "")),
        "disciplina_slug": q.get("discipline", ""),
        "idioma": q.get("language"),
        "fonte": "enem.dev (questão oficial ENEM)",
        "dificuldade": None,  # preenchido por get_questions_by_difficulty()
        "is_ai_generated": False,
    }


def _classificar_dificuldade_groq(questoes: list[dict]) -> list[dict]:
    """
    Usa o Groq para classificar cada questão como 'fácil', 'média' ou 'difícil'.

    Critérios avaliados:
    - Extensão do enunciado
    - Complexidade do vocabulário
    - Número de conceitos envolvidos
    - Nível de abstração exigido
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY não encontrada no arquivo .env")

    client = Groq(api_key=api_key)

    questoes_classificadas = []
    for q in questoes:
        enunciado = q.get("contexto") or q.get("enunciado") or ""
        alternativas_txt = "\n".join(
            f"{letra}) {texto}"
            for letra, texto in q.get("alternativas", {}).items()
        )

        prompt = f"""Analise esta questão do ENEM e classifique sua dificuldade.

QUESTÃO:
{enunciado[:1200]}

ALTERNATIVAS:
{alternativas_txt[:600]}

Avalie com base em:
1. Extensão e densidade do enunciado (longo e denso = mais difícil)
2. Complexidade do vocabulário (técnico/acadêmico = mais difícil)
3. Número de conceitos envolvidos (vários = mais difícil)
4. Nível de abstração (interpretação profunda = mais difícil)

Responda com APENAS uma palavra: fácil, média ou difícil"""

        try:
            resposta = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=10,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Você é um especialista em avaliação de questões do ENEM. "
                            "Responda APENAS com uma das três palavras: fácil, média ou difícil."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            nivel = resposta.choices[0].message.content.strip().lower()
            # Garante valor válido
            if nivel not in ("fácil", "média", "difícil"):
                nivel = "média"
        except Exception:
            nivel = "média"

        q_classificada = dict(q)
        q_classificada["dificuldade"] = nivel
        questoes_classificadas.append(q_classificada)

    return questoes_classificadas


# ── Funções públicas ──────────────────────────────────────────────────────────

def get_exams() -> list[dict]:
    """
    Lista todos os anos disponíveis na API enem.dev.

    Retorna lista de dicts com: year, title, disciplines, languages
    """
    dados = _get("/exams")
    if not isinstance(dados, list):
        return []

    return [
        {
            "ano": exam.get("year"),
            "titulo": exam.get("title"),
            "disciplinas": [d["value"] for d in exam.get("disciplines", [])],
            "idiomas": [l["value"] for l in exam.get("languages", [])],
        }
        for exam in dados
    ]


def get_questions(year: int, discipline: str = None, limit: int = 10, offset: int = 0) -> dict:
    """
    Busca questões por ano e disciplina opcional.

    Parâmetros:
        year: ano do ENEM (ex: 2023)
        discipline: slug da disciplina (ex: "ciencias-humanas", "matematica")
                    Se None, retorna todas as disciplinas.
        limit: número máximo de questões (padrão 10)
        offset: paginação (padrão 0)

    Retorna dict com: total, has_more, questoes (lista formatada)
    """
    params = {"limit": limit, "offset": offset}
    if discipline:
        params["discipline"] = discipline

    dados = _get(f"/exams/{year}/questions", params=params)
    if not dados:
        return {"total": 0, "has_more": False, "questoes": []}

    questoes = [_formatar_questao(q, ano=year) for q in dados.get("questions", [])]
    meta = dados.get("metadata", {})

    return {
        "total": meta.get("total", len(questoes)),
        "has_more": meta.get("hasMore", False),
        "limit": meta.get("limit", limit),
        "offset": meta.get("offset", offset),
        "questoes": questoes,
    }


def get_random_question(discipline: str = None) -> dict | None:
    """
    Retorna uma questão aleatória, opcionalmente filtrada por disciplina.

    Parâmetros:
        discipline: slug da disciplina (opcional)

    Retorna dict com a questão formatada ou None se não encontrar.
    """
    # Busca os anos disponíveis
    exames = get_exams()
    if not exames:
        return None

    anos = [e["ano"] for e in exames if e["ano"]]

    # Tenta até 3 anos aleatórios
    for _ in range(3):
        ano = random.choice(anos)
        resultado = get_questions(ano, discipline=discipline, limit=45)
        questoes = resultado.get("questoes", [])
        if questoes:
            return random.choice(questoes)

    return None


def search_questions_by_topic(topic: str, limit: int = 10) -> list[dict]:
    """
    Busca questões relacionadas a um tema percorrendo os anos disponíveis.

    Estratégia: busca questões sem filtro de disciplina e filtra pelo tema
    no contexto/enunciado. Retorna até `limit` questões.

    Parâmetros:
        topic: tema a buscar (ex: "fordismo", "fotossíntese")
        limit: número máximo de resultados (padrão 10)

    Retorna lista de questões formatadas que mencionam o tema.
    """
    exames = get_exams()
    if not exames:
        return []

    anos = sorted([e["ano"] for e in exames if e["ano"]], reverse=True)
    topic_lower = topic.lower()
    encontradas = []

    for ano in anos:
        if len(encontradas) >= limit:
            break
        try:
            resultado = get_questions(ano, limit=45)
            for q in resultado.get("questoes", []):
                texto = (
                    (q.get("contexto") or "") + " " +
                    (q.get("enunciado") or "") + " " +
                    " ".join(q.get("alternativas", {}).values())
                ).lower()
                if topic_lower in texto:
                    encontradas.append(q)
                    if len(encontradas) >= limit:
                        break
        except Exception:
            continue

    return encontradas


def get_questions_by_difficulty(topic: str, discipline: str = None) -> dict:
    """
    Busca 10+ questões do tema, classifica cada uma com o Groq LLM e
    retorna exatamente 3 questões — uma de cada nível de dificuldade.

    Critérios de classificação:
    - Extensão do enunciado
    - Complexidade do vocabulário
    - Número de conceitos envolvidos
    - Nível de abstração exigido

    Parâmetros:
        topic: tema a buscar
        discipline: slug da disciplina (opcional)

    Retorna dict com:
        - facil: questão de nível fácil
        - media: questão de nível médio
        - dificil: questão de nível difícil
        - total_analisadas: quantas questões foram classificadas
        - erro: mensagem de erro se algo falhar (None se sucesso)
    """
    # Coleta questões pelo tema
    questoes = search_questions_by_topic(topic, limit=15)

    # Filtra por disciplina se informada
    if discipline and questoes:
        filtradas = [q for q in questoes if q.get("disciplina_slug") == discipline]
        questoes = filtradas if filtradas else questoes  # fallback sem filtro

    if len(questoes) < 3:
        return {
            "facil": None,
            "media": None,
            "dificil": None,
            "total_analisadas": len(questoes),
            "erro": (
                f"Apenas {len(questoes)} questão(ões) encontrada(s) sobre '{topic}'. "
                "São necessárias pelo menos 3 para classificar por dificuldade."
            ),
        }

    # Classifica com o Groq
    try:
        classificadas = _classificar_dificuldade_groq(questoes)
    except Exception as e:
        return {
            "facil": None,
            "media": None,
            "dificil": None,
            "total_analisadas": len(questoes),
            "erro": f"Erro ao classificar dificuldade: {e}",
        }

    # Separa por nível
    por_nivel = {"fácil": [], "média": [], "difícil": []}
    for q in classificadas:
        nivel = q.get("dificuldade", "média")
        if nivel in por_nivel:
            por_nivel[nivel].append(q)

    # Garante uma questão por nível — usa fallback se algum nível ficar vazio
    def _pegar_uma(nivel: str) -> dict | None:
        if por_nivel[nivel]:
            return por_nivel[nivel][0]
        # Fallback: pega do nível mais próximo
        for fallback in ("média", "fácil", "difícil"):
            if por_nivel[fallback]:
                q = por_nivel[fallback].pop(0)
                q["dificuldade"] = nivel  # reclassifica para não repetir
                return q
        return None

    return {
        "facil":  _pegar_uma("fácil"),
        "media":  _pegar_uma("média"),
        "dificil": _pegar_uma("difícil"),
        "total_analisadas": len(classificadas),
        "erro": None,
    }


# ── Teste local ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("1. ANOS DISPONÍVEIS")
    exames = get_exams()
    for e in exames[:3]:
        print(f"  {e['titulo']} — disciplinas: {e['disciplinas']}")

    print("\n" + "=" * 60)
    print("2. QUESTÕES 2023 — CIÊNCIAS HUMANAS (3 primeiras)")
    resultado = get_questions(2023, discipline="ciencias-humanas", limit=3)
    print(f"  Total disponível: {resultado['total']}")
    for q in resultado["questoes"]:
        print(f"  [{q['ano']}] {q['titulo']} | Gabarito: {q['gabarito']} | IA: {q['is_ai_generated']}")

    print("\n" + "=" * 60)
    print("3. QUESTÃO ALEATÓRIA")
    q = get_random_question(discipline="matematica")
    if q:
        print(f"  {q['titulo']} | Disciplina: {q['disciplina']} | Gabarito: {q['gabarito']}")

    print("\n" + "=" * 60)
    print("4. BUSCA POR TEMA: 'fordismo'")
    encontradas = search_questions_by_topic("fordismo", limit=5)
    print(f"  {len(encontradas)} questões encontradas")
    for q in encontradas:
        print(f"  [{q['ano']}] {q['titulo']}")

    print("\n" + "=" * 60)
    print("5. QUESTÕES POR DIFICULDADE: 'trabalho'")
    por_dif = get_questions_by_difficulty("trabalho")
    print(f"  Total analisadas: {por_dif['total_analisadas']}")
    if por_dif["erro"]:
        print(f"  ERRO: {por_dif['erro']}")
    else:
        for nivel, chave in [("Fácil", "facil"), ("Média", "media"), ("Difícil", "dificil")]:
            q = por_dif[chave]
            if q:
                print(f"  {nivel}: [{q['ano']}] {q['titulo']}")
