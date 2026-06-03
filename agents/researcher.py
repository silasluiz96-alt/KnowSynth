import os
from pathlib import Path
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

# Caminho da skill que define o comportamento deste agente
SKILL_PATH = Path(__file__).parent.parent / ".claude" / "skills" / "researcher.md"

# Conectivos que indicam tema amplo mesmo com poucas palavras
_CONECTIVOS = {
    "e", "ou", "da", "de", "do", "das", "dos", "na", "no", "nas", "nos",
    "a", "o", "as", "os", "em", "com", "para", "pelo", "pela", "entre",
    "durante", "após", "antes", "sobre", "sob", "contra",
}

# Domínios de fontes didáticas prioritárias (Camada 1)
_FONTES_DIDATICAS = [
    "site:brasilescola.uol.com.br",
    "site:khanacademy.org",
    "site:mundoeducacao.uol.com.br",
    "site:educacao.uol.com.br",
]

# Domínios de fontes jornalísticas confiáveis (Camada 2)
_FONTES_NOTICIAS = [
    "site:g1.globo.com",
    "site:bbc.com/portuguese",
    "site:agenciabrasil.ebc.com.br",
    "site:brasil.elpais.com",
    "site:nexojornal.com.br",
]


def _carregar_skill() -> str:
    """Lê o arquivo da skill e retorna o conteúdo como string."""
    try:
        return SKILL_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _detectar_tipo(input_usuario: str) -> str:
    """
    Classifica o input como 'tema_geral' ou 'palavra_chave'.

    Regras:
    - Mais de 3 palavras → tema_geral
    - Até 3 palavras com conectivo → tema_geral
    - Caso contrário → palavra_chave
    """
    palavras = input_usuario.strip().lower().split()
    if len(palavras) > 3:
        return "tema_geral"
    if any(p in _CONECTIVOS for p in palavras):
        return "tema_geral"
    return "palavra_chave"


def _buscar(client: TavilyClient, query: str, max_results: int = 3) -> dict:
    """Executa uma busca na Tavily e retorna a resposta bruta."""
    try:
        return client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
        )
    except Exception as e:
        return {"results": [], "answer": "", "_erro": str(e)}


def _extrair_fontes(resposta: dict) -> list:
    """Extrai e normaliza a lista de fontes de uma resposta da Tavily."""
    return [
        {
            "titulo": item.get("title", ""),
            "url": item.get("url", ""),
            "conteudo": item.get("content", ""),
        }
        for item in resposta.get("results", [])
    ]


def _deduplicar(fontes: list) -> list:
    """Remove fontes com URL duplicada."""
    vistas = set()
    unicas = []
    for f in fontes:
        if f["url"] not in vistas:
            vistas.add(f["url"])
            unicas.append(f)
    return unicas


def _construir_queries(input_usuario: str, tipo: str) -> dict:
    """
    Monta as queries das 3 camadas de busca de acordo com o tipo detectado.
    Retorna um dicionário com chaves: didatico, noticias, academico.
    """
    if tipo == "tema_geral":
        return {
            "didatico": f"{input_usuario} ENEM ensino médio explicação {_FONTES_DIDATICAS[0]}",
            "noticias": f"{input_usuario} notícias recentes 2024 2025 {_FONTES_NOTICIAS[0]}",
            "academico": f"{input_usuario} artigo acadêmico pesquisa site:scholar.google.com OR site:scielo.br",
        }
    else:
        return {
            "didatico": (
                f"{input_usuario} definição conceito ENEM ensino médio "
                f"{_FONTES_DIDATICAS[0]} OR {_FONTES_DIDATICAS[2]}"
            ),
            "noticias": f"questões ENEM sobre {input_usuario} contexto atual exemplos",
            "academico": (
                f"{input_usuario} significado contexto histórico científico "
                f"site:scholar.google.com OR site:scielo.br"
            ),
        }


def pesquisar(input_usuario: str) -> dict:
    """
    Executa as 3 camadas de busca conforme definido na skill do Pesquisador ENEM.

    Retorna um dicionário estruturado com:
    - tipo_busca, conteudo_didatico, noticias_relevantes, referencias_academicas,
      resumo, relevancia_enem, termos_relacionados, lacunas_e_aprofundamento
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return _resultado_erro(input_usuario, "TAVILY_API_KEY não encontrada no arquivo .env")

    client = TavilyClient(api_key=api_key)
    tipo = _detectar_tipo(input_usuario)
    queries = _construir_queries(input_usuario, tipo)
    lacunas = []

    # ── Camada 1 — Conteúdo Didático ─────────────────────────────────────────
    resp_didatico = _buscar(client, queries["didatico"], max_results=4)
    conteudo_didatico = _extrair_fontes(resp_didatico)
    resumo_didatico = resp_didatico.get("answer", "")
    if resp_didatico.get("_erro") or not conteudo_didatico:
        lacunas.append({
            "camada": "conteúdo didático",
            "descricao": "Não foi possível encontrar fontes didáticas suficientes.",
            "palavras_chave_pt": [f"{input_usuario} ensino médio", f"{input_usuario} resumo ENEM"],
            "palavras_chave_en": [f"{input_usuario} high school", f"{input_usuario} summary"],
            "sugestao_busca": f"Digite no Brasil Escola: '{input_usuario}'",
            "tipo_fonte": "site educacional ou livro didático",
        })

    # ── Camada 2 — Notícias Atuais ────────────────────────────────────────────
    resp_noticias = _buscar(client, queries["noticias"], max_results=3)
    noticias_relevantes = _extrair_fontes(resp_noticias)
    resumo_noticias = resp_noticias.get("answer", "")
    if resp_noticias.get("_erro") or not noticias_relevantes:
        lacunas.append({
            "camada": "notícias atuais",
            "descricao": "Não foram encontradas notícias recentes relacionadas ao tema.",
            "palavras_chave_pt": [f"{input_usuario} 2024", f"{input_usuario} atualidades"],
            "palavras_chave_en": [f"{input_usuario} news 2024", f"{input_usuario} current events"],
            "sugestao_busca": f"Busque no G1 ou BBC Brasil: '{input_usuario}'",
            "tipo_fonte": "portal de notícias confiável",
        })

    # ── Camada 3 — Referências Acadêmicas ────────────────────────────────────
    resp_academico = _buscar(client, queries["academico"], max_results=3)
    referencias_academicas = _extrair_fontes(resp_academico)
    resumo_academico = resp_academico.get("answer", "")
    if resp_academico.get("_erro") or not referencias_academicas:
        lacunas.append({
            "camada": "referências acadêmicas",
            "descricao": "Não foram encontrados artigos acadêmicos acessíveis sobre o tema.",
            "palavras_chave_pt": [f"{input_usuario} pesquisa científica", f"{input_usuario} artigo"],
            "palavras_chave_en": [f"{input_usuario} research", f"{input_usuario} academic paper"],
            "sugestao_busca": f"Digite no Google Scholar: '{input_usuario}'",
            "tipo_fonte": "artigo científico ou dissertação",
        })

    # ── Monta resumo integrado ────────────────────────────────────────────────
    partes_resumo = [p for p in [resumo_didatico, resumo_noticias, resumo_academico] if p]
    resumo = " | ".join(partes_resumo) if partes_resumo else (
        f"Conteúdo coletado sobre '{input_usuario}' a partir de {len(conteudo_didatico + noticias_relevantes + referencias_academicas)} fontes."
    )

    # ── Termos relacionados (busca extra para palavra-chave) ──────────────────
    termos_relacionados = []
    if tipo == "palavra_chave":
        resp_termos = _buscar(
            client,
            f"{input_usuario} termos relacionados ENEM conceitos associados",
            max_results=2,
        )
        answer_termos = resp_termos.get("answer", "")
        if answer_termos:
            # Extrai termos curtos separados por vírgula/ponto-e-vírgula
            import re as _re
            candidatos = _re.split(r"[,;]", answer_termos)
            termos_relacionados = [t.strip() for t in candidatos if 2 < len(t.strip()) < 60][:8]

    return {
        "tema": input_usuario,
        "tipo_busca": tipo,
        "conteudo_didatico": _deduplicar(conteudo_didatico),
        "noticias_relevantes": _deduplicar(noticias_relevantes),
        "referencias_academicas": _deduplicar(referencias_academicas),
        "resumo": resumo,
        "relevancia_enem": (
            f"O tema '{input_usuario}' é relevante para o ENEM pois aparece nas áreas de "
            "Ciências Humanas, Ciências da Natureza ou Linguagens, dependendo do contexto, "
            "e costuma ser explorado com textos de apoio de fontes jornalísticas e acadêmicas."
        ),
        "termos_relacionados": termos_relacionados,
        "lacunas_e_aprofundamento": lacunas,
        "skill_utilizada": str(SKILL_PATH),
    }


def _resultado_erro(tema: str, mensagem: str) -> dict:
    """Retorna um dicionário de erro padronizado sem quebrar o pipeline."""
    return {
        "tema": tema,
        "tipo_busca": "erro",
        "conteudo_didatico": [],
        "noticias_relevantes": [],
        "referencias_academicas": [],
        "resumo": "",
        "relevancia_enem": "",
        "termos_relacionados": [],
        "lacunas_e_aprofundamento": [],
        "erro": mensagem,
        "skill_utilizada": str(SKILL_PATH),
    }


if __name__ == "__main__":
    skill = _carregar_skill()
    print(f"Skill carregada: {len(skill)} caracteres\n")

    testes = [
        "fordismo",
        "Revolução Industrial",
        "fotossíntese",
        "aquecimento global e desigualdade social",
    ]

    for entrada in testes:
        print(f"\n{'=' * 60}")
        resultado = pesquisar(entrada)
        print(f"Input:      {resultado['tema']}")
        print(f"Tipo:       {resultado['tipo_busca']}")
        print(f"Didático:   {len(resultado['conteudo_didatico'])} fontes")
        print(f"Notícias:   {len(resultado['noticias_relevantes'])} fontes")
        print(f"Acadêmico:  {len(resultado['referencias_academicas'])} fontes")
        print(f"Lacunas:    {len(resultado['lacunas_e_aprofundamento'])}")
        if resultado.get("erro"):
            print(f"ERRO:       {resultado['erro']}")
