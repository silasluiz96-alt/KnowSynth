-- =============================================================
-- KnowSynth v2 — Migration 001
-- Criação das tabelas raw de ingestão de dados de sessão
-- Autor: Silas Luiz Bom Fim
-- Data: 2026-06-08
-- Branch: feat/v2-supabase-infra
-- =============================================================
-- Rodar no SQL Editor do Supabase: Dashboard → SQL Editor → New query
-- =============================================================


-- -------------------------------------------------------------
-- TABELA: sessoes
-- Uma linha por sessão de estudo encerrada pelo aluno.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessoes (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_nome      TEXT        NOT NULL,
    inicio          TIMESTAMPTZ NOT NULL,
    fim             TIMESTAMPTZ,
    tema            TEXT        NOT NULL,
    disciplina      TEXT,
    meta_tempo      TEXT,                       -- "30min", "1h", "Sem limite"
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  sessoes              IS 'Sessões de estudo encerradas — uma linha por sessão.';
COMMENT ON COLUMN sessoes.aluno_nome  IS 'Nome digitado pelo aluno na tela de login.';
COMMENT ON COLUMN sessoes.tema        IS 'Último tema estudado na sessão.';
COMMENT ON COLUMN sessoes.meta_tempo  IS 'Meta de tempo escolhida pelo aluno no início da sessão.';


-- -------------------------------------------------------------
-- TABELA: respostas
-- Uma linha por resposta dada a uma questão dentro de uma sessão.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS respostas (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    sessao_id            UUID        NOT NULL REFERENCES sessoes(id) ON DELETE CASCADE,
    questao_id           TEXT        NOT NULL,   -- ex: "questao-54-2021" ou "ai-generated"
    alternativa_escolhida TEXT,                  -- A, B, C, D ou E
    alternativa_correta   TEXT,
    acertou              BOOLEAN     NOT NULL DEFAULT FALSE,
    dicas_usadas         INTEGER     NOT NULL DEFAULT 0,
    tempo_resposta_s     NUMERIC(8,2),           -- tempo em segundos até responder
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  respostas                    IS 'Respostas individuais às questões dentro de cada sessão.';
COMMENT ON COLUMN respostas.questao_id        IS 'ID da questão — prefixo "ai-" para geradas pelo LLM, número para questões reais do ENEM.';
COMMENT ON COLUMN respostas.dicas_usadas      IS 'Quantidade de dicas solicitadas antes de responder (0 a 3).';
COMMENT ON COLUMN respostas.tempo_resposta_s  IS 'Tempo em segundos desde a exibição da questão até o clique na resposta.';


-- -------------------------------------------------------------
-- TABELA: questoes_cache
-- Catálogo de questões já exibidas — evita rebuscar na enem.dev
-- e enriquece os modelos dbt com metadados das questões.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questoes_cache (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    questao_id      TEXT        NOT NULL UNIQUE,  -- chave de negócio
    titulo          TEXT,
    ano             INTEGER,
    tema            TEXT,
    disciplina      TEXT,
    dificuldade     TEXT,                          -- "fácil", "médio", "difícil"
    tem_imagem      BOOLEAN     NOT NULL DEFAULT FALSE,
    is_ai_generated BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  questoes_cache                 IS 'Catálogo de questões exibidas — base para os modelos dbt dim_questoes.';
COMMENT ON COLUMN questoes_cache.questao_id     IS 'Identificador único da questão. Formato: "<titulo>-<ano>" para reais, "ai-<uuid>" para geradas.';
COMMENT ON COLUMN questoes_cache.is_ai_generated IS 'TRUE para questões geradas pelo Sintetizador, FALSE para questões reais do ENEM.';


-- -------------------------------------------------------------
-- ÍNDICES — aceleram as queries mais frequentes dos marts dbt
-- -------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_sessoes_aluno_nome  ON sessoes   (aluno_nome);
CREATE INDEX IF NOT EXISTS idx_sessoes_tema        ON sessoes   (tema);
CREATE INDEX IF NOT EXISTS idx_respostas_sessao_id ON respostas (sessao_id);
CREATE INDEX IF NOT EXISTS idx_respostas_acertou   ON respostas (acertou);
CREATE INDEX IF NOT EXISTS idx_questoes_tema       ON questoes_cache (tema);
CREATE INDEX IF NOT EXISTS idx_questoes_disciplina ON questoes_cache (disciplina);


-- -------------------------------------------------------------
-- ROW LEVEL SECURITY (RLS)
-- Habilita RLS nas três tabelas.
-- Por ora sem policies (acesso via service_role apenas).
-- Policies por aluno_nome serão adicionadas na Fase 3
-- quando o app autenticar usuários via Supabase Auth.
-- -------------------------------------------------------------
ALTER TABLE sessoes        ENABLE ROW LEVEL SECURITY;
ALTER TABLE respostas      ENABLE ROW LEVEL SECURITY;
ALTER TABLE questoes_cache ENABLE ROW LEVEL SECURITY;


-- =============================================================
-- FIM DA MIGRATION 001
-- Próxima migration: 20260608_002 — inserção via supabase-py
-- =============================================================
