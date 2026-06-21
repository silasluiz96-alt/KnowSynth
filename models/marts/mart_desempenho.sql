with sessoes as (
    select * from {{ ref('stg_sessoes') }}
),

respostas as (
    select * from {{ ref('stg_respostas') }}
),

desempenho as (
    select
        s.aluno_nome,
        s.tema,
        s.disciplina,
        count(r.id)                                           as total_questoes,
        sum(case when r.acertou then 1 else 0 end)           as total_acertos,
        sum(case when not r.acertou then 1 else 0 end)       as total_erros,
        round(
            sum(case when r.acertou then 1 else 0 end) * 100.0
            / nullif(count(r.id), 0), 1
        )                                                     as taxa_acerto_pct,
        avg(r.dicas_usadas)                                   as media_dicas,
        count(distinct s.id)                                  as total_sessoes,
        min(s.inicio_at)                                      as primeira_sessao,
        max(s.fim_at)                                         as ultima_sessao
    from sessoes s
    left join respostas r on r.sessao_id = s.id
    group by s.aluno_nome, s.tema, s.disciplina
)

select * from desempenho