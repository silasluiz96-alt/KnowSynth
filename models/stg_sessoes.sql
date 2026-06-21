select
    id,
    aluno_nome,
    tema,
    disciplina,
    meta_tempo,
    inicio as inicio_at,
    fim     as fim_at,
    created_at
from {{ source('public', 'sessoes') }}