-- =============================================================
-- KnowSynth v2 — Migration 002
-- RLS Policies — acesso via anon key (fase inicial sem Auth)
-- Autor: Silas Luiz Bom Fim
-- Data: 2026-06-08
-- =============================================================
-- Contexto:
--   A Migration 001 habilitou RLS nas 3 tabelas mas não criou policies,
--   bloqueando qualquer inserção via anon key.
--
--   Nesta fase o app não usa Supabase Auth — o aluno se identifica
--   apenas pelo nome digitado. Por isso criamos policies permissivas
--   para o role 'anon' (leitura e escrita liberadas).
--
--   Na Fase 3 (Supabase Auth), estas policies serão substituídas
--   por policies baseadas em auth.uid(), restringindo cada aluno
--   a visualizar apenas seus próprios dados.
-- =============================================================
-- Rodar no SQL Editor do Supabase após a Migration 001
-- =============================================================


-- -------------------------------------------------------------
-- TABELA: sessoes
-- -------------------------------------------------------------
CREATE POLICY "anon_all_sessoes"
    ON sessoes
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);


-- -------------------------------------------------------------
-- TABELA: respostas
-- -------------------------------------------------------------
CREATE POLICY "anon_all_respostas"
    ON respostas
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);


-- -------------------------------------------------------------
-- TABELA: questoes_cache
-- -------------------------------------------------------------
CREATE POLICY "anon_all_questoes_cache"
    ON questoes_cache
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);


-- =============================================================
-- FIM DA MIGRATION 002
-- TODO Fase 3: substituir por policies auth.uid() quando
--              Supabase Auth for implementado
-- =============================================================
