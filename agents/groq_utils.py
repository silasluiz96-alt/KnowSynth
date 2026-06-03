"""
Utilitário centralizado de chamadas a LLM com fallback automático.

Ordem de tentativa:
  1. Google Gemini gemini-2.5-flash  ← modelo principal
  2. Groq llama-3.3-70b-versatile    ← fallback

Pacotes necessários: google-genai, groq
Chaves no .env: GEMINI_API_KEY, GROQ_API_KEY

IMPORTANTE — thinking do Gemini 2.5 Flash:
  O modelo usa tokens internos de "thinking" que consomem parte do orçamento
  de max_output_tokens, causando JSON truncado. Solução: thinking_budget=0
  (desabilitado) para tarefas de extração JSON estruturada — não é necessário
  raciocínio prolongado aqui.

Se ambos falharem, retorna mensagem amigável sem quebrar o pipeline.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_MODELO_GEMINI = "gemini-2.5-flash"
_MODELO_GROQ   = "llama-3.3-70b-versatile"
_MSG_INDISPONIVEL = (
    "⏳ Serviço temporariamente indisponível. Tente em alguns minutos."
)


def _gemini(messages: list[dict], max_tokens: int) -> dict | None:
    """
    Tenta chamar o Gemini com thinking desabilitado.
    Retorna dict com texto não-vazio, ou None se falhar.
    """
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        log.debug("GEMINI_API_KEY não encontrada — pulando Gemini.")
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        # Separa system instruction das mensagens de conversa
        system_instruction = None
        contents = []
        for msg in messages:
            role    = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            else:
                gemini_role = "model" if role == "assistant" else "user"
                contents.append({"role": gemini_role, "parts": [{"text": content}]})

        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
            # Desabilita thinking: economiza tokens para o JSON de saída.
            # Gemini 2.5 Flash consome ~800-1000 tokens de thinking por padrão,
            # o que trunca respostas JSON grandes quando max_output_tokens é baixo.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        resposta = client.models.generate_content(
            model=_MODELO_GEMINI,
            contents=contents,
            config=config,
        )

        # Detecta resposta cortada pelo limite de tokens
        if resposta.candidates:
            finish = resposta.candidates[0].finish_reason
            if hasattr(finish, "name") and finish.name == "MAX_TOKENS":
                log.warning(
                    "Gemini atingiu MAX_TOKENS (max_output_tokens=%d). "
                    "JSON possivelmente incompleto — ativando fallback Groq.",
                    max_tokens,
                )
                return None

        texto = resposta.text or ""
        if not texto.strip():
            log.warning("Gemini retornou texto vazio — ativando fallback Groq.")
            return None

        tokens = 0
        if hasattr(resposta, "usage_metadata") and resposta.usage_metadata:
            tokens = getattr(resposta.usage_metadata, "total_token_count", 0)

        log.debug("Gemini OK — modelo=%s tokens=%d", _MODELO_GEMINI, tokens)
        return {
            "texto": texto,
            "tokens_usados": tokens,
            "modelo_usado": _MODELO_GEMINI,
            "erro": None,
        }

    except Exception as exc:
        log.warning("Gemini falhou (%s: %s) — ativando fallback Groq.", type(exc).__name__, exc)
        return None


def _groq(messages: list[dict], max_tokens: int) -> dict | None:
    """
    Tenta chamar o Groq.
    Retorna dict com texto não-vazio, ou None se falhar.
    """
    key = os.getenv("GROQ_API_KEY")
    if not key:
        log.debug("GROQ_API_KEY não encontrada — pulando Groq.")
        return None

    try:
        from groq import Groq

        client   = Groq(api_key=key)
        resposta = client.chat.completions.create(
            model=_MODELO_GROQ,
            max_tokens=max_tokens,
            messages=messages,
        )
        texto = resposta.choices[0].message.content or ""
        if not texto.strip():
            log.warning("Groq retornou texto vazio.")
            return None

        tokens = resposta.usage.total_tokens if resposta.usage else 0
        log.debug("Groq OK — modelo=%s tokens=%d", _MODELO_GROQ, tokens)
        return {
            "texto": texto,
            "tokens_usados": tokens,
            "modelo_usado": _MODELO_GROQ,
            "erro": None,
        }

    except Exception as exc:
        log.warning("Groq falhou (%s: %s).", type(exc).__name__, exc)
        return None


def chamar_llm(
    messages: list[dict],
    max_tokens: int = 1000,
) -> dict:
    """
    Chama o LLM com fallback automático: Gemini → Groq.

    Parâmetros:
        messages:   Lista de dicts [{role, content}]
                    role pode ser "system", "user" ou "assistant"
        max_tokens: Limite de tokens na resposta (sem contar thinking)

    Retorna dict com:
        texto         — conteúdo da resposta
        tokens_usados — tokens consumidos
        modelo_usado  — nome do modelo que respondeu
        erro          — None se sucesso, mensagem amigável se falhou
    """
    # 1ª tentativa: Gemini
    resultado = _gemini(messages, max_tokens)
    if resultado and resultado.get("texto"):
        return resultado

    # 2ª tentativa: Groq
    resultado = _groq(messages, max_tokens)
    if resultado and resultado.get("texto"):
        return resultado

    # Ambos falharam
    log.error("Gemini e Groq falharam — retornando mensagem de indisponibilidade.")
    return {
        "texto": "",
        "tokens_usados": 0,
        "modelo_usado": None,
        "erro": _MSG_INDISPONIVEL,
    }


# Alias para compatibilidade com imports existentes
chamar_groq = chamar_llm
