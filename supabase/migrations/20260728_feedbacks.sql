-- Tabela de feedback pós-sessão (v3)
CREATE TABLE IF NOT EXISTS public.feedbacks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    criado_em   TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    sessao_id   UUID             REFERENCES public.sessoes(id) ON DELETE SET NULL,
    user_id     UUID             REFERENCES auth.users(id)     ON DELETE SET NULL,
    aluno_nome  TEXT             NOT NULL,
    nota        SMALLINT         NOT NULL CHECK (nota BETWEEN 1 AND 5),
    comentario  TEXT
);

ALTER TABLE public.feedbacks ENABLE ROW LEVEL SECURITY;

-- Aluno autenticado só vê seus próprios feedbacks
CREATE POLICY "feedback_select_own"
    ON public.feedbacks FOR SELECT
    USING (auth.uid() = user_id);

-- Qualquer um pode inserir (inclui acesso rápido sem user_id)
CREATE POLICY "feedback_insert_any"
    ON public.feedbacks FOR INSERT
    WITH CHECK (true);
