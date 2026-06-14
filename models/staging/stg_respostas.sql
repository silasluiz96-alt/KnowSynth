select
    id,
    sessao_id,
    questao_id,
    alternativa_escolhida,
    alternativa_correta,
    acertou,
    dicas_usadas,
    created_at
from {{ source('public', 'respostas') }}