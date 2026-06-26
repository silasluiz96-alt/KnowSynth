"""
Módulo de autenticação do KnowSynth via Supabase Auth.

Responsabilidade única: sign_up, sign_in, sign_out e recuperação do usuário
autenticado. Não contém lógica de negócio nem de interface.

Uso:
    from utils.auth import sign_up, sign_in, sign_out, get_user

    ok, resultado = sign_up("aluno@email.com", "senha123", consent_ts)
    ok, resultado = sign_in("aluno@email.com", "senha123")
"""

import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


def _get_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL e SUPABASE_KEY não configuradas.")
    from supabase import create_client
    return create_client(url, key)


def sign_up(email: str, password: str, consent_timestamp: str) -> tuple[bool, dict | str]:
    """
    Cria uma nova conta no Supabase Auth e registra o consentimento LGPD.

    Parâmetros:
        email             — e-mail do novo usuário
        password          — senha escolhida (mínimo 6 caracteres)
        consent_timestamp — ISO 8601 do momento em que o checkbox foi marcado

    Retorna:
        (True, {"user_id": ..., "email": ...}) se criou com sucesso
        (False, "mensagem de erro amigável") se falhou
    """
    try:
        client = _get_client()
        response = client.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "lgpd_consent": True,
                    "lgpd_consent_at": consent_timestamp,
                }
            }
        })

        if response.user:
            # Sem sessão = e-mail de confirmação foi enviado (comportamento padrão do Supabase)
            needs_confirmation = response.session is None
            log.info("[auth] sign_up — user_id=%s needs_confirmation=%s", response.user.id, needs_confirmation)
            return True, {
                "user_id": response.user.id,
                "email": response.user.email,
                "needs_confirmation": needs_confirmation,
            }

        return False, "Não foi possível criar a conta. Tente novamente."

    except Exception as exc:
        msg = str(exc)
        log.warning("[auth] sign_up falhou: %s", msg)
        if "already registered" in msg or "already been registered" in msg:
            return False, "Este e-mail já está cadastrado. Tente fazer login."
        if "Password should be at least" in msg:
            return False, "A senha deve ter pelo menos 6 caracteres."
        return False, "Erro ao criar conta. Tente novamente mais tarde."


def sign_in(email: str, password: str) -> tuple[bool, dict | str]:
    """
    Autentica um usuário existente no Supabase Auth.

    Retorna:
        (True, {"user_id": ..., "email": ...}) se autenticou
        (False, "mensagem de erro amigável") se falhou
    """
    try:
        client = _get_client()
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })

        if response.user:
            log.info("[auth] sign_in — user_id=%s", response.user.id)
            return True, {"user_id": response.user.id, "email": response.user.email}

        return False, "E-mail ou senha incorretos."

    except Exception as exc:
        msg = str(exc)
        log.warning("[auth] sign_in falhou: %s", msg)
        if "Email not confirmed" in msg or "email_not_confirmed" in msg:
            return False, "E-mail ainda não confirmado. Verifique sua caixa de entrada e clique no link de confirmação."
        if "Invalid login" in msg or "invalid_credentials" in msg:
            return False, "E-mail ou senha incorretos."
        return False, "Erro ao fazer login. Tente novamente mais tarde."


def sign_out() -> None:
    """Encerra a sessão do usuário autenticado."""
    try:
        _get_client().auth.sign_out()
        log.info("[auth] sign_out — sessão encerrada")
    except Exception as exc:
        log.warning("[auth] sign_out falhou: %s", exc)


def consent_now() -> str:
    """Retorna o timestamp atual em ISO 8601 UTC — usado para registrar consentimento LGPD."""
    return datetime.now(tz=timezone.utc).isoformat()
