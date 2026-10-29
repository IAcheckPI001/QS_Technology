-- Apply to Supabase public.chat_history before deploying the workspace API.
ALTER TABLE public.chat_history
    ADD COLUMN IF NOT EXISTS updated_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS channel TEXT NOT NULL DEFAULT 'website',
    ADD COLUMN IF NOT EXISTS retrieval_snapshot JSONB;

UPDATE public.chat_history
SET channel = 'website'
WHERE channel IS NULL;

CREATE INDEX IF NOT EXISTS chat_history_updated_date_idx
    ON public.chat_history (updated_date DESC);
CREATE INDEX IF NOT EXISTS chat_history_status_idx
    ON public.chat_history (status);
CREATE INDEX IF NOT EXISTS chat_history_channel_idx
    ON public.chat_history (channel);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chat_history_channel_check'
    ) THEN
        ALTER TABLE public.chat_history
            ADD CONSTRAINT chat_history_channel_check
            CHECK (channel IN ('website', 'crm'));
    END IF;
END $$;
