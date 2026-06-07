"""
Camada de persistência do KnowSynth — DuckDB.

Responsabilidade única: ler e gravar dados de sessão no arquivo local
knowsynth.duckdb. Todo o resto do app (Streamlit, agentes) não precisa
saber que estamos usando DuckDB — só chama as funções aqui.

Tabelas:
    raw_sessions      — uma linha por sessão de estudo encerrada
    raw_agent_calls   — uma linha por agente acionado em cada sessão
"""

import uuid
import duckdb
from datetime import datetime
from pathlib import Path

# Caminho do arquivo DuckDB — fica na raiz do projeto
_DB_PATH = Path(__file__).parent.parent / "knowsynth.duckdb"


def _conectar() -> duckdb.DuckDBPyConnection:
    """Abre (ou cria) a conexão com o arquivo DuckDB."""
    return duckdb.connect(str(_DB_PATH))


def init_db() -> None:
    """
    Cria as tabelas brutas (raw) se ainda não existirem.
    Seguro chamar múltiplas vezes — usa IF NOT EXISTS.
    """
    with _conectar() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS raw_sessions (
                session_id   VARCHAR PRIMARY KEY,
                usuario      VARCHAR,
                ts_inicio    TIMESTAMP,
                ts_fim       TIMESTAMP,
                meta_tempo   VARCHAR,
                total_temas  INTEGER,
                duracao_min  DOUBLE
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS raw_agent_calls (
                id           VARCHAR PRIMARY KEY,
                session_id   VARCHAR,
                ts           TIMESTAMP,
                agente       VARCHAR,
                duracao_s    DOUBLE,
                sucesso      BOOLEAN,
                llm_usado    VARCHAR   -- NULL para agentes sem LLM (Pesquisador, Ranqueador)
            )
        """)


def save_session(
    usuario: str,
    ts_inicio: float,
    ts_fim: float,
    meta_tempo: str,
    total_temas: int,
    agent_log: list[dict],
    llm_por_agente: dict[str, str] | None = None,
) -> str:
    """
    Grava uma sessão completa no DuckDB.

    Parâmetros:
        usuario        — nome do estudante
        ts_inicio      — timestamp Unix do início da sessão
        ts_fim         — timestamp Unix do fim da sessão
        meta_tempo     — "30min", "1h", "Sem limite" etc.
        total_temas    — quantos temas foram estudados
        agent_log      — lista de dicts do _session_log (hooks.py)
        llm_por_agente — dict opcional: {"Crítico": "gemini-...", "Sintetizador": "llama-..."}

    Retorna:
        session_id gerado (UUID4)
    """
    init_db()

    session_id = str(uuid.uuid4())
    ts_ini = datetime.fromtimestamp(ts_inicio)
    ts_fim_dt = datetime.fromtimestamp(ts_fim)
    duracao = (ts_fim - ts_inicio) / 60

    llm_map = llm_por_agente or {}

    with _conectar() as con:
        # Grava a sessão
        con.execute(
            """
            INSERT INTO raw_sessions
                (session_id, usuario, ts_inicio, ts_fim, meta_tempo, total_temas, duracao_min)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [session_id, usuario, ts_ini, ts_fim_dt, meta_tempo, total_temas, round(duracao, 2)],
        )

        # Grava cada chamada de agente que teve duracao_s registrada
        for entrada in agent_log:
            duracao_s = entrada.get("duracao_s")
            if duracao_s is None:
                continue  # ignora entradas sem duração (evento de "inicio" sem conclusão)

            agente = entrada.get("agente", "desconhecido")
            sucesso = bool(entrada.get("sucesso"))
            ts_agente = datetime.fromtimestamp(entrada.get("timestamp", ts_inicio))
            llm = llm_map.get(agente)

            con.execute(
                """
                INSERT INTO raw_agent_calls
                    (id, session_id, ts, agente, duracao_s, sucesso, llm_usado)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [str(uuid.uuid4()), session_id, ts_agente, agente, duracao_s, sucesso, llm],
            )

    return session_id


def load_sessions_summary(usuario: str | None = None) -> list[dict]:
    """
    Retorna um resumo das sessões gravadas.

    Parâmetros:
        usuario: se informado, retorna apenas sessões deste usuário.
                 se None, retorna todas (uso administrativo).

    Usado pela aba Analytics do Streamlit.
    """
    init_db()
    with _conectar() as con:
        if usuario:
            rows = con.execute("""
                SELECT
                    session_id, usuario, ts_inicio, ts_fim,
                    meta_tempo, total_temas, duracao_min
                FROM raw_sessions
                WHERE usuario = ?
                ORDER BY ts_inicio DESC
            """, [usuario]).fetchall()
        else:
            rows = con.execute("""
                SELECT
                    session_id, usuario, ts_inicio, ts_fim,
                    meta_tempo, total_temas, duracao_min
                FROM raw_sessions
                ORDER BY ts_inicio DESC
            """).fetchall()

        cols = ["session_id", "usuario", "ts_inicio", "ts_fim",
                "meta_tempo", "total_temas", "duracao_min"]
        return [dict(zip(cols, row)) for row in rows]


def load_agent_stats(usuario: str | None = None) -> list[dict]:
    """
    Retorna estatísticas agregadas por agente — tempo médio e taxa de fallback Groq.

    Parâmetros:
        usuario: se informado, considera apenas sessões deste usuário.
                 se None, agrega todas as sessões.

    Usado pela aba Analytics do Streamlit.
    """
    init_db()
    with _conectar() as con:
        if usuario:
            rows = con.execute("""
                SELECT
                    ac.agente,
                    COUNT(*)                                                   AS total_chamadas,
                    ROUND(AVG(ac.duracao_s), 2)                               AS duracao_media_s,
                    ROUND(MAX(ac.duracao_s), 2)                               AS duracao_max_s,
                    SUM(CASE WHEN ac.sucesso = false THEN 1 ELSE 0 END)       AS total_erros,
                    SUM(CASE WHEN ac.llm_usado ILIKE '%llama%' THEN 1 ELSE 0 END)  AS chamadas_groq,
                    SUM(CASE WHEN ac.llm_usado ILIKE '%gemini%' THEN 1 ELSE 0 END) AS chamadas_gemini
                FROM raw_agent_calls ac
                INNER JOIN raw_sessions s ON s.session_id = ac.session_id
                WHERE s.usuario = ?
                GROUP BY ac.agente
                ORDER BY duracao_media_s DESC
            """, [usuario]).fetchall()
        else:
            rows = con.execute("""
                SELECT
                    agente,
                    COUNT(*)                                                   AS total_chamadas,
                    ROUND(AVG(duracao_s), 2)                                  AS duracao_media_s,
                    ROUND(MAX(duracao_s), 2)                                  AS duracao_max_s,
                    SUM(CASE WHEN sucesso = false THEN 1 ELSE 0 END)          AS total_erros,
                    SUM(CASE WHEN llm_usado ILIKE '%llama%' THEN 1 ELSE 0 END)  AS chamadas_groq,
                    SUM(CASE WHEN llm_usado ILIKE '%gemini%' THEN 1 ELSE 0 END) AS chamadas_gemini
                FROM raw_agent_calls
                GROUP BY agente
                ORDER BY duracao_media_s DESC
            """).fetchall()

        cols = ["agente", "total_chamadas", "duracao_media_s", "duracao_max_s",
                "total_erros", "chamadas_groq", "chamadas_gemini"]
        return [dict(zip(cols, row)) for row in rows]


def count_sessions(usuario: str | None = None) -> int:
    """
    Retorna o total de sessões gravadas.

    Parâmetros:
        usuario: se informado, conta apenas sessões deste usuário.
    """
    init_db()
    with _conectar() as con:
        if usuario:
            return con.execute(
                "SELECT COUNT(*) FROM raw_sessions WHERE usuario = ?", [usuario]
            ).fetchone()[0]
        return con.execute("SELECT COUNT(*) FROM raw_sessions").fetchone()[0]
