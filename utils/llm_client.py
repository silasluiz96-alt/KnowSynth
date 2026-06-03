"""
Cliente LLM centralizado do KnowSynth.

Responsabilidades:
  - Escolher o melhor modelo disponível (Gemini → Groq)
  - Abstrair diferenças de API entre providers
  - Fazer parse seguro de JSON em respostas de qualquer provider
  - Logar qual modelo foi usado em cada chamada

Providers e modelos:
  Principal : Google Gemini gemini-2.5-flash  (GEMINI_API_KEY no .env)
  Fallback  : Groq llama-3.3-70b-versatile    (GROQ_API_KEY  no .env)

Uso básico nos agentes:
    from utils.llm_client import chamar_llm, parse_resposta_json

    r = chamar_llm(prompt="...", system_prompt="...", max_tokens=2000)
    if r["erro"]:
        return {"erro": r["erro"]}
    dados = parse_resposta_json(r["texto"])
"""

import json
import logging
import os
import re

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# ── Configuração dos modelos ──────────────────────────────────────────────────

_MODELO_GEMINI = "gemini-2.5-flash"
_MODELO_GROQ   = "llama-3.3-70b-versatile"

_MSG_INDISPONIVEL = (
    "⏳ Serviço temporariamente indisponível. Tente em alguns minutos."
)


# ── Providers ─────────────────────────────────────────────────────────────────

def _chamar_gemini(prompt: str, system_prompt: str | None, max_tokens: int) -> dict | None:
    """
    Chama o Gemini 2.5 Flash com thinking desabilitado.

    Thinking desabilitado porque:
    - O modelo aloca ~800-1000 tokens de thinking do budget de max_output_tokens
    - Isso trunca JSONs grandes (max_tokens=2000 virava ~1100 de saída real)
    - Para extração JSON estruturada não é necessário raciocínio prolongado

    Retorna dict com texto não-vazio, ou None se falhar por qualquer motivo.
    """
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        log.debug("GEMINI_API_KEY ausente — pulando Gemini.")
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            system_instruction=system_prompt or None,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        resposta = client.models.generate_content(
            model=_MODELO_GEMINI,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config=config,
        )

        # Detecta corte por limite de tokens (JSON incompleto = inútil)
        if resposta.candidates:
            finish = resposta.candidates[0].finish_reason
            if hasattr(finish, "name") and finish.name == "MAX_TOKENS":
                log.warning(
                    "Gemini atingiu MAX_TOKENS (max_tokens=%d) — fallback para Groq.",
                    max_tokens,
                )
                return None

        texto = resposta.text or ""
        if not texto.strip():
            log.warning("Gemini retornou texto vazio — fallback para Groq.")
            return None

        tokens = 0
        if hasattr(resposta, "usage_metadata") and resposta.usage_metadata:
            tokens = getattr(resposta.usage_metadata, "total_token_count", 0)

        log.info("[LLM] %s | tokens=%d", _MODELO_GEMINI, tokens)
        return {
            "texto":         texto,
            "tokens_usados": tokens,
            "modelo_usado":  _MODELO_GEMINI,
            "erro":          None,
        }

    except Exception as exc:
        log.warning("Gemini falhou (%s: %s) — fallback para Groq.", type(exc).__name__, exc)
        return None


def _chamar_groq(prompt: str, system_prompt: str | None, max_tokens: int) -> dict | None:
    """
    Chama o Groq llama-3.3-70b-versatile.
    Retorna dict com texto não-vazio, ou None se falhar.
    """
    key = os.getenv("GROQ_API_KEY")
    if not key:
        log.debug("GROQ_API_KEY ausente — pulando Groq.")
        return None

    try:
        from groq import Groq

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

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
        log.info("[LLM] %s | tokens=%d", _MODELO_GROQ, tokens)
        return {
            "texto":         texto,
            "tokens_usados": tokens,
            "modelo_usado":  _MODELO_GROQ,
            "erro":          None,
        }

    except Exception as exc:
        log.warning("Groq falhou (%s: %s).", type(exc).__name__, exc)
        return None


# ── Interface pública ─────────────────────────────────────────────────────────

def chamar_llm(
    prompt: str,
    system_prompt: str | None = None,
    max_tokens: int = 1500,
) -> dict:
    """
    Chama o melhor LLM disponível: Groq primeiro, Gemini como fallback.

    Ordem invertida para respeitar o limite de 20 req/min do Gemini.
    Groq tem limites mais generosos e latência menor.

    Parâmetros:
        prompt        — mensagem principal do usuário
        system_prompt — instrução de sistema / persona do agente (opcional)
        max_tokens    — limite de tokens na resposta (padrão: 1500)

    Retorna dict com:
        texto         — conteúdo da resposta (str)
        tokens_usados — tokens consumidos (int)
        modelo_usado  — nome do modelo que respondeu (str | None)
        erro          — None se sucesso, mensagem amigável se falhou (str | None)
    """
    resultado = _chamar_gemini(prompt, system_prompt, max_tokens)
    if resultado and resultado.get("texto"):
        return resultado

    resultado = _chamar_groq(prompt, system_prompt, max_tokens)
    if resultado and resultado.get("texto"):
        return resultado

    log.error("Gemini e Groq falharam — retornando mensagem de indisponibilidade.")
    return {
        "texto":         "",
        "tokens_usados": 0,
        "modelo_usado":  None,
        "erro":          _MSG_INDISPONIVEL,
    }


def parse_resposta_json(texto: str) -> dict:
    """
    Faz parse seguro de JSON retornado por qualquer LLM.

    Trata:
    - Blocos de código markdown  (```json ... ```)
    - Escapes inválidos do Groq  (\\x não reconhecidos)
    - JSON embutido em texto livre

    Retorna o dict parseado, ou {"content": texto} como fallback
    para que o agente possa exibir o texto bruto sem quebrar.
    """
    if not texto:
        return {}

    t = texto.strip()

    # Remove bloco de código markdown
    if t.startswith("```"):
        linhas = t.splitlines()
        # Remove primeira linha (```json ou ```) e última (```)
        interior = linhas[1:-1] if linhas[-1].strip() == "```" else linhas[1:]
        t = "\n".join(interior).strip()

    # Tenta parse direto
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    # Tenta corrigir escapes inválidos (comum no Groq)
    try:
        cleaned = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', t)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Tenta extrair JSON embutido em texto livre
    match = re.search(r'\{[\s\S]*\}', t)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback: devolve o texto bruto para o agente exibir
    log.warning("parse_resposta_json: nenhum JSON válido encontrado — retornando fallback.")
    return {"content": texto}
