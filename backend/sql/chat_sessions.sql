-- Apply to Supabase before deploying POST /chat/website and POST /chat/crm.
-- Idempotent: chạy lại nhiều lần không lỗi.

-- Chủ sở hữu của hội thoại chatbot. Session chỉ được dùng lại khi principal
-- (principal_type, subject_id, tenant_id, acting_user_id) và channel khớp,
-- chưa revoked/expired.
CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id UUID PRIMARY KEY,
    principal_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    tenant_id TEXT,
    channel TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS chat_sessions_owner_idx
    ON public.chat_sessions (principal_type, subject_id, channel);

-- Nhân viên mà principal service (CRM) chat thay; NULL với guest.
ALTER TABLE public.chat_sessions
    ADD COLUMN IF NOT EXISTS acting_user_id TEXT;

CREATE INDEX IF NOT EXISTS chat_sessions_acting_user_idx
    ON public.chat_sessions (subject_id, acting_user_id)
    WHERE acting_user_id IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chat_sessions_principal_type_check'
    ) THEN
        ALTER TABLE public.chat_sessions
            ADD CONSTRAINT chat_sessions_principal_type_check
            CHECK (principal_type IN ('guest', 'employee', 'service'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chat_sessions_channel_check'
    ) THEN
        ALTER TABLE public.chat_sessions
            ADD CONSTRAINT chat_sessions_channel_check
            CHECK (channel IN ('website', 'crm'));
    END IF;
END $$;

-- Header Idempotency-Key của client, lưu theo từng lượt. Hiện chỉ lưu, chưa
-- chống xử lý trùng nên index chưa UNIQUE.
ALTER TABLE public.chat_history
    ADD COLUMN IF NOT EXISTS idempotency_key UUID;

CREATE INDEX IF NOT EXISTS chat_history_idempotency_key_idx
    ON public.chat_history (session_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- Chưa thêm FK chat_history.session_id -> chat_sessions.id: các session cũ chỉ
-- có trong chat_history, không có chủ sở hữu. Session cũ sẽ nhận 404
-- session_not_found ở /chat/* và client tạo session mới.
