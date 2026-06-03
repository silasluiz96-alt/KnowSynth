"""
Utilitário centralizado de chamadas ao Groq com fallback automático de modelo.

Ordem de tentativa em caso de rate limit (429):
  1. llama-3.3-70b-versatile   ← modelo principal, mais capaz
  2. llama-3.1-8b-instant       ← fallback rápido
  3. gemma2-9b-it               ← último recurso

Se todos falharem, retorna mensagem amigável sem quebrar o pipeline.
"""

import os
from dotenv import load_dotenv
from groq import Groq, RateLimitError

load_dotenv()

# Ordem de preferência dos modelos
MODELOS_FALLBACK = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]


def chamar_groq(
    messages: list[dict],
    max_tokens: int = 1000,
    api_key: str = None,
) -> dict:
    """
    Chama a API do Groq com fallback automático de modelo.

    Parâmetros:
        messages:   Lista de dicts no formato [{role, content}, ...]
        max_tokens: Limite de tokens na resposta (padrão: 1000)
        api_key:    Chave de API (padrão: lê de GROQ_API_KEY no .env)

    Retorna dict com:
        texto         — conteúdo da resposta (str)
        tokens_usados — total de tokens consumidos (int)
        modelo_usado  — nome do modelo que respondeu (str)
        erro          — None se sucesso, mensagem de erro se falhou (str | None)
    """
    key = api_key or os.getenv("GROQ_API_KEY")
    client = Groq(api_key=key)
    ultimo_erro = None

    for modelo in MODELOS_FALLBACK:
        try:
            resposta = client.chat.completions.create(
                model=modelo,
                max_tokens=max_tokens,
                messages=messages,
            )
            return {
                "texto": resposta.choices[0].message.content,
                "tokens_usados": resposta.usage.total_tokens if resposta.usage else 0,
                "modelo_usado": modelo,
                "erro": None,
            }

        except RateLimitError as e:
            # Rate limit: tenta o próximo modelo da lista
            ultimo_erro = e
            continue

        except Exception as e:
            # Qualquer outro erro (autenticação, rede, etc.) → não adianta trocar modelo
            return {
                "texto": "",
                "tokens_usados": 0,
                "modelo_usado": modelo,
                "erro": f"Erro ao chamar Groq ({modelo}): {e}",
            }

    # Todos os modelos falharam com rate limit
    return {
        "texto": "",
        "tokens_usados": 0,
        "modelo_usado": None,
        "erro": "Limite de uso atingido, tente em alguns minutos",
    }
