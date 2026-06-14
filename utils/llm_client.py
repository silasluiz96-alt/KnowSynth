"""
Cliente LLM centralizado do KnowSynth.

Responsabilidades:
  - Escolher o melhor modelo disponível (Gemini → Groq → OpenAI)
  - Abstrair diferenças de API entre providers
  - Fazer parse seguro de JSON em respostas de qualquer provider
  - Logar qual modelo foi usado em cada chamada

Providers e modelos:
  Principal  : Google Gemini gemini-2.5-flash  (GEMINI_API_KEY no .env)
  Fallback 1 : Groq llama-3.3-70b-versatile    (GROQ_API_KEY  no .env)
  Fallback 2 : OpenAI gpt-4o-mini              (OPENAI_API_KEY no .env) — último recurso

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

_MODELO_GEMINI = "gemini-2.5-flash-lite"
_MODELO_GROQ   = "llama-3.3-70b-versatile"
_MODELO_OPENAI = "gpt-4o-mini"

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

        texto = resposta.text or ""

        # MAX_TOKENS: retorna o texto gerado até agora como resposta válida.
        # Não faz fallback — o conteúdo já existe, só foi cortado no limite.
        if resposta.candidates:
            finish = resposta.candidates[0].finish_reason
            if hasattr(finish, "name") and finish.name == "MAX_TOKENS":
                log.warning(
                    "Gemini atingiu MAX_TOKENS (max_tokens=%d) — usando texto parcial.",
                    max_tokens,
                )
                # Se não há texto algum, aí sim é erro real
                if not texto.strip():
                    log.warning("Gemini: MAX_TOKENS sem texto — fallback para Groq.")
                    return None

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


def _chamar_openai(prompt: str, system_prompt: str | None, max_tokens: int) -> dict | None:
    """
    Chama o OpenAI gpt-4o-mini — último recurso quando Gemini e Groq falham.
    Retorna dict com texto não-vazio, ou None se falhar.
    """
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        log.debug("OPENAI_API_KEY ausente — pulando OpenAI.")
        return None

    try:
        from openai import OpenAI

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        client   = OpenAI(api_key=key)
        resposta = client.chat.completions.create(
            model=_MODELO_OPENAI,
            max_tokens=max_tokens,
            messages=messages,
        )

        texto = resposta.choices[0].message.content or ""
        if not texto.strip():
            log.warning("OpenAI retornou texto vazio.")
            return None

        tokens = resposta.usage.total_tokens if resposta.usage else 0
        log.info("[LLM] %s | tokens=%d", _MODELO_OPENAI, tokens)
        return {
            "texto":         texto,
            "tokens_usados": tokens,
            "modelo_usado":  _MODELO_OPENAI,
            "erro":          None,
        }

    except Exception as exc:
        log.warning("OpenAI falhou (%s: %s).", type(exc).__name__, exc)
        return None


# ── Interface pública ─────────────────────────────────────────────────────────

def chamar_llm(
    prompt: str,
    system_prompt: str | None = None,
    max_tokens: int = 1500,
) -> dict:
    """
    Chama o melhor LLM disponível: Gemini primeiro, Groq como fallback, OpenAI como último recurso.

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

    resultado = _chamar_openai(prompt, system_prompt, max_tokens)
    if resultado and resultado.get("texto"):
        return resultado

    log.error("Gemini, Groq e OpenAI falharam — retornando mensagem de indisponibilidade.")
    return {
        "texto":         "",
        "tokens_usados": 0,
        "modelo_usado":  None,
        "erro":          _MSG_INDISPONIVEL,
    }


def _fix_json_newlines(s: str) -> str:
    """
    Substitui quebras de linha literais dentro de strings JSON por \\n.

    O LLM frequentemente escreve campos multi-parágrafo com newlines reais
    dentro das aspas — isso é JSON inválido. Esta função percorre o texto
    caractere a caractere e corrige apenas os newlines que estão dentro de
    uma string (entre aspas duplas não escapadas).
    """
    result = []
    in_string = False
    escaped = False
    for ch in s:
        if escaped:
            result.append(ch)
            escaped = False
        elif ch == "\\" and in_string:
            result.append(ch)
            escaped = True
        elif ch == '"':
            in_string = not in_string
            result.append(ch)
        elif ch == "\n" and in_string:
            result.append("\\n")
        elif ch == "\r" and in_string:
            result.append("\\r")
        else:
            result.append(ch)
    return "".join(result)


def parse_resposta_json(texto: str) -> dict:
    """
    Faz parse seguro de JSON retornado por qualquer LLM.

    Trata:
    - Blocos de código markdown  (```json ... ```)
    - Newlines literais dentro de strings JSON (causa mais comum de falha)
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

    # Corrige newlines literais dentro de strings JSON (causa mais comum)
    try:
        return json.loads(_fix_json_newlines(t))
    except json.JSONDecodeError:
        pass

    # Tenta corrigir escapes inválidos (comum no Groq)
    try:
        cleaned = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', t)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Combina as duas correções
    try:
        cleaned = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', _fix_json_newlines(t))
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Tenta extrair JSON embutido em texto livre
    match = re.search(r'\{[\s\S]*\}', t)
    if match:
        try:
            return json.loads(_fix_json_newlines(match.group(0)))
        except json.JSONDecodeError:
            pass

    # Fallback: tenta extrair campos principais do Sintetizador via regex
    log.warning("parse_resposta_json: JSON inválido — tentando extração por regex.")
    extraido = _extrair_campos_regex(t)
    if extraido:
        return extraido

    # Último recurso: devolve o texto bruto para o agente exibir
    log.warning("parse_resposta_json: extração regex falhou — retornando texto bruto.")
    return {"content": texto}


def _extrair_campos_regex(texto: str) -> dict:
    """
    Tenta extrair campos principais do Sintetizador quando o JSON está malformado.
    Procura por padrões como "introducao": "..." ou "introducao": [...]
    Retorna dict com os campos encontrados, ou {} se nada for extraído.
    """
    resultado = {}

    # introducao — string entre aspas após a chave
    m = re.search(r'"introducao"\s*:\s*"([\s\S]{20,}?)"(?=\s*[,}])', texto)
    if m:
        resultado["introducao"] = m.group(1).replace('\\"', '"')

    # dicas_de_prova — array de strings
    m = re.search(r'"dicas_de_prova"\s*:\s*\[([\s\S]*?)\]', texto)
    if m:
        dicas_raw = re.findall(r'"(.*?)"', m.group(1))
        if dicas_raw:
            resultado["dicas_de_prova"] = dicas_raw

    # pontos_essenciais — array de objetos (extrai apenas conceito+definicao)
    m = re.search(r'"pontos_essenciais"\s*:\s*\[([\s\S]*?)\](?=\s*[,}])', texto)
    if m:
        pontos = []
        for bloco in re.finditer(r'\{([^{}]+)\}', m.group(1)):
            p = {}
            cm = re.search(r'"conceito"\s*:\s*"([^"]+)"', bloco.group(1))
            dm = re.search(r'"definicao"\s*:\s*"([^"]+)"', bloco.group(1))
            em = re.search(r'"exemplo"\s*:\s*"([^"]+)"', bloco.group(1))
            if cm:
                p["conceito"] = cm.group(1)
            if dm:
                p["definicao"] = dm.group(1)
            if em:
                p["exemplo"] = em.group(1)
            p["cobrado_enem"] = True
            if p.get("conceito"):
                pontos.append(p)
        if pontos:
            resultado["pontos_essenciais"] = pontos

    return resultado
