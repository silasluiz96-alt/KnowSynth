"""
Camada de persistência do KnowSynth v2 — Supabase.

Responsabilidade única: ler e gravar dados de sessão no Supabase.
Todo o resto do app (Streamlit, agentes) não precisa saber que estamos
usando Supabase — só chama as funções aqui.

Tabelas:
    sessoes         — uma linha por sessão de estudo encerrada
    respostas       — uma linha por questão respondida dentro da sessão
    questoes_cache  — catálogo de questões já exibidas (evita rebuscar na API)

Uso:
    from utils.supabase_db import save_sessao, save_resposta, save_questao_cache
"""

import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# ── Cliente Supabase (singleton por processo) ─────────────────────────────────

_client = None


def _get_client():
    """
    Retorna o cliente Supabase, criando-o na primeira chamada.
    Singleton simples — uma instância por processo.
    """
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL e SUPABASE_KEY devem estar configuradas no .env "
            "ou nos Secrets do Streamlit Cloud."
        )

    from supabase import create_client
    _client = create_client(url, key)
    log.info("[supabase_db] Cliente criado — %s", url)
    return _client


# ── Funções públicas ──────────────────────────────────────────────────────────

def save_sessao(
    aluno_nome: str,
    inicio: float,
    fim: float,
    tema: str,
    disciplina: str | None = None,
    meta_tempo: str | None = None,
) -> str | None:
    """
    Insere uma sessão encerrada na tabela `sessoes`.

    Parâmetros:
        aluno_nome  — nome digitado pelo aluno no login
        inicio      — timestamp Unix do início da sessão
        fim         — timestamp Unix do encerramento
        tema        — último tema estudado na sessão
        disciplina  — disciplina do tema (opcional)
        meta_tempo  — "30min", "1h", "Sem limite" etc. (opcional)

    Retorna:
        UUID da sessão inserida, ou None se falhar.
    """
    try:
        payload = {
            "aluno_nome": aluno_nome,
            "inicio":     _unix_to_iso(inicio),
            "fim":        _unix_to_iso(fim),
            "tema":       tema,
            "disciplina": disciplina,
            "meta_tempo": meta_tempo,
        }
        r = _get_client().table("sessoes").insert(payload).execute()
        sessao_id = r.data[0]["id"] if r.data else None
        log.info("[supabase_db] sessao salva — id=%s aluno=%s tema=%s", sessao_id, aluno_nome, tema)
        return sessao_id

    except Exception as exc:
        log.warning("[supabase_db] Falha ao salvar sessao: %s", exc)
        return None


def save_resposta(
    sessao_id: str,
    questao_id: str,
    alternativa_escolhida: str | None,
    alternativa_correta: str | None,
    acertou: bool,
    dicas_usadas: int = 0,
    tempo_resposta_s: float | None = None,
) -> str | None:
    """
    Insere uma resposta individual na tabela `respostas`.

    Parâmetros:
        sessao_id             — UUID da sessão (retornado por save_sessao)
        questao_id            — identificador da questão (ex: "Questão 54 - ENEM 2021")
        alternativa_escolhida — letra escolhida pelo aluno (A-E)
        alternativa_correta   — letra correta da questão
        acertou               — True se acertou
        dicas_usadas          — quantidade de dicas usadas antes de responder (0-3)
        tempo_resposta_s      — segundos até responder (opcional)

    Retorna:
        UUID da resposta inserida, ou None se falhar.
    """
    try:
        payload = {
            "sessao_id":             sessao_id,
            "questao_id":            questao_id,
            "alternativa_escolhida": alternativa_escolhida,
            "alternativa_correta":   alternativa_correta,
            "acertou":               acertou,
            "dicas_usadas":          dicas_usadas,
            "tempo_resposta_s":      tempo_resposta_s,
        }
        r = _get_client().table("respostas").insert(payload).execute()
        resposta_id = r.data[0]["id"] if r.data else None
        log.info("[supabase_db] resposta salva — id=%s questao=%s acertou=%s", resposta_id, questao_id, acertou)
        return resposta_id

    except Exception as exc:
        log.warning("[supabase_db] Falha ao salvar resposta: %s", exc)
        return None


def save_questao_cache(
    questao_id: str,
    titulo: str | None = None,
    ano: int | None = None,
    tema: str | None = None,
    disciplina: str | None = None,
    dificuldade: str | None = None,
    tem_imagem: bool = False,
    is_ai_generated: bool = False,
) -> bool:
    """
    Insere uma questão no catálogo `questoes_cache` se ainda não existir.
    Usa upsert com ON CONFLICT DO NOTHING — seguro chamar múltiplas vezes
    para a mesma questão.

    Retorna:
        True se inseriu ou já existia, False se falhou.
    """
    try:
        payload = {
            "questao_id":      questao_id,
            "titulo":          titulo,
            "ano":             ano,
            "tema":            tema,
            "disciplina":      disciplina,
            "dificuldade":     dificuldade,
            "tem_imagem":      tem_imagem,
            "is_ai_generated": is_ai_generated,
        }
        _get_client().table("questoes_cache").upsert(
            payload, on_conflict="questao_id"
        ).execute()
        log.info("[supabase_db] questao_cache upsert — questao_id=%s", questao_id)
        return True

    except Exception as exc:
        log.warning("[supabase_db] Falha ao salvar questao_cache: %s", exc)
        return False


def get_mapa_pontos_fracos(aluno_nome: str) -> list[dict]:
    """
    Retorna o desempenho consolidado do aluno a partir da view mart_desempenho.

    A view é mantida pelo job diário do dbt Cloud e fica no schema dbt_knowsynth.
    Retorna lista ordenada por taxa_acerto_pct ascendente (piores temas primeiro).

    Parâmetros:
        aluno_nome — nome do aluno logado na sessão

    Retorna:
        Lista de dicts com: tema, disciplina, total_questoes, total_acertos,
        total_erros, taxa_acerto_pct, media_dicas, total_sessoes.
        Retorna [] se não houver dados ou se falhar.
    """
    try:
        r = (
            _get_client()
            .schema("dbt_knowsynth")
            .from_("mart_desempenho")
            .select(
                "tema, disciplina, total_questoes, total_acertos, "
                "total_erros, taxa_acerto_pct, media_dicas, total_sessoes"
            )
            .eq("aluno_nome", aluno_nome)
            .order("taxa_acerto_pct", desc=False)
            .execute()
        )
        log.info(
            "[supabase_db] mapa_pontos_fracos — aluno=%s registros=%d",
            aluno_nome,
            len(r.data),
        )
        return r.data or []

    except Exception as exc:
        log.warning("[supabase_db] Falha ao ler mart_desempenho: %s", exc)
        return []


# ── Helpers internos ──────────────────────────────────────────────────────────

def _unix_to_iso(ts: float) -> str:
    """Converte timestamp Unix (float) para string ISO 8601 com timezone UTC."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
