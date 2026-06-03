"""
Utilitário centralizado de chamadas ao Groq com fallback automático de modelo.

Ordem de tentativa em caso de rate limit (429):
  1. llama-3.3-70b-versatile   ← modelo principal, mais capaz
  2. llama3-70b-8192            ← fallback 1
  3. mixtral-8x22b-instruct     ← fallback 2

Nos modelos de fallback (2º e 3º), o prompt é automaticamente enxugado:
  - system: truncado em 2.000 chars (mantém instruções essenciais do topo)
  - user:   truncado em 3.500 chars (mantém contexto principal, corta exemplos)
  - max_tokens: limitado a 1.500 para caber dentro do TPM dos modelos menores

Se todos falharem, retorna mensagem amigável sem quebrar o pipeline.
"""

import os
from dotenv import load_dotenv
from groq import Groq, RateLimitError

load_dotenv()

# ── Configuração dos modelos ──────────────────────────────────────────────────

# Modelo principal — sem restrições de prompt
_MODELO_PRINCIPAL = "llama-3.3-70b-versatile"

# Fallbacks — usam prompt enxugado e max_tokens limitado
_MODELOS_FALLBACK = [
    "llama3-70b-8192",
    "mixtral-8x22b-instruct",
]

# Limites de truncamento para fallbacks
_MAX_CHARS_SYSTEM  = 2_000   # chars do system message nos fallbacks
_MAX_CHARS_USER    = 3_500   # chars do user message nos fallbacks
_MAX_TOKENS_FALLBACK = 1_500 # max_tokens da resposta nos fallbacks


# ── Helpers ───────────────────────────────────────────────────────────────────

def _truncar(texto: str, limite: int) -> str:
    """Trunca texto no limite de chars, adicionando aviso se necessário."""
    if len(texto) <= limite:
        return texto
    return texto[:limite] + "\n\n[...conteúdo resumido para otimizar uso da API...]"


def _slim_messages(messages: list[dict]) -> list[dict]:
    """
    Retorna uma versão enxuta das mensagens para uso nos modelos de fallback.

    Estratégia:
    - system: mantém as instruções essenciais do início (primeiros 2.000 chars)
    - user:   mantém o contexto principal, corta exemplos extensos do final
    - outras roles: mantidas sem alteração
    """
    slim = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "system":
            slim.append({"role": role, "content": _truncar(content, _MAX_CHARS_SYSTEM)})
        elif role == "user":
            slim.append({"role": role, "content": _truncar(content, _MAX_CHARS_USER)})
        else:
            slim.append(msg)

    return slim


# ── Função principal ──────────────────────────────────────────────────────────

def chamar_groq(
    messages: list[dict],
    max_tokens: int = 1000,
    api_key: str = None,
) -> dict:
    """
    Chama a API do Groq com fallback automático de modelo.

    Parâmetros:
        messages:   Lista de dicts no formato [{role, content}, ...]
        max_tokens: Limite de tokens na resposta do modelo principal
        api_key:    Chave de API (padrão: lê de GROQ_API_KEY no .env)

    Retorna dict com:
        texto         — conteúdo da resposta (str)
        tokens_usados — total de tokens consumidos (int)
        modelo_usado  — nome do modelo que respondeu (str)
        erro          — None se sucesso, mensagem de erro se falhou (str | None)
    """
    key = api_key or os.getenv("GROQ_API_KEY")
    client = Groq(api_key=key)

    # ── 1ª tentativa: modelo principal com prompt completo ────────────────────
    try:
        resposta = client.chat.completions.create(
            model=_MODELO_PRINCIPAL,
            max_tokens=max_tokens,
            messages=messages,
        )
        return {
            "texto": resposta.choices[0].message.content,
            "tokens_usados": resposta.usage.total_tokens if resposta.usage else 0,
            "modelo_usado": _MODELO_PRINCIPAL,
            "erro": None,
        }

    except RateLimitError:
        pass  # Segue para os fallbacks

    except Exception as e:
        # Erro não relacionado a rate limit — não adianta trocar modelo
        return {
            "texto": "",
            "tokens_usados": 0,
            "modelo_usado": _MODELO_PRINCIPAL,
            "erro": f"Erro ao chamar Groq ({_MODELO_PRINCIPAL}): {e}",
        }

    # ── Fallbacks: prompt enxugado + max_tokens reduzido ─────────────────────
    messages_slim = _slim_messages(messages)
    max_tokens_fb  = min(max_tokens, _MAX_TOKENS_FALLBACK)

    for modelo in _MODELOS_FALLBACK:
        try:
            resposta = client.chat.completions.create(
                model=modelo,
                max_tokens=max_tokens_fb,
                messages=messages_slim,
            )
            return {
                "texto": resposta.choices[0].message.content,
                "tokens_usados": resposta.usage.total_tokens if resposta.usage else 0,
                "modelo_usado": modelo,
                "erro": None,
            }

        except RateLimitError:
            continue  # Tenta o próximo

        except Exception as e:
            return {
                "texto": "",
                "tokens_usados": 0,
                "modelo_usado": modelo,
                "erro": f"Erro ao chamar Groq ({modelo}): {e}",
            }

    # ── Todos os modelos falharam com rate limit ──────────────────────────────
    return {
        "texto": "",
        "tokens_usados": 0,
        "modelo_usado": None,
        "erro": "Limite de uso atingido, tente em alguns minutos",
    }
