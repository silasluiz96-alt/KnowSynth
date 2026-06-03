"""
Utilitário centralizado de chamadas ao Groq.

Modelo único: llama-3.3-70b-versatile

Em caso de erro 429 (rate limit) ou 413 (prompt muito grande),
retorna mensagem amigável sem tentar outros modelos.
"""

import os
from dotenv import load_dotenv
from groq import Groq, RateLimitError, BadRequestError

load_dotenv()

_MODELO = "llama-3.3-70b-versatile"
_MSG_LIMITE = (
    "⏳ Limite de uso atingido. O serviço será restabelecido em breve. "
    "Tente novamente em alguns minutos."
)


def chamar_groq(
    messages: list[dict],
    max_tokens: int = 1000,
    api_key: str = None,
) -> dict:
    """
    Chama a API do Groq usando llama-3.3-70b-versatile.

    Parâmetros:
        messages:   Lista de dicts no formato [{role, content}, ...]
        max_tokens: Limite de tokens na resposta (padrão: 1000)
        api_key:    Chave de API (padrão: lê de GROQ_API_KEY no .env)

    Retorna dict com:
        texto         — conteúdo da resposta (str)
        tokens_usados — total de tokens consumidos (int)
        modelo_usado  — nome do modelo utilizado (str)
        erro          — None se sucesso, mensagem amigável se falhou (str | None)
    """
    key = api_key or os.getenv("GROQ_API_KEY")
    client = Groq(api_key=key)

    try:
        resposta = client.chat.completions.create(
            model=_MODELO,
            max_tokens=max_tokens,
            messages=messages,
        )
        return {
            "texto": resposta.choices[0].message.content,
            "tokens_usados": resposta.usage.total_tokens if resposta.usage else 0,
            "modelo_usado": _MODELO,
            "erro": None,
        }

    except (RateLimitError, BadRequestError):
        # 429 — rate limit diário  |  413 — prompt muito grande
        return {
            "texto": "",
            "tokens_usados": 0,
            "modelo_usado": _MODELO,
            "erro": _MSG_LIMITE,
        }

    except Exception as e:
        return {
            "texto": "",
            "tokens_usados": 0,
            "modelo_usado": _MODELO,
            "erro": f"Erro ao chamar a API do Groq: {e}",
        }
