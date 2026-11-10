-- Trace của từng lượt chat (cây span, chỉ metadata). Áp dụng trên Supabase trước khi
-- đặt CHAT_TRACE_PERSIST=true. Không có retention tự động: xóa thủ công theo created_at.
CREATE TABLE IF NOT EXISTS public.chat_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL,
    -- chat_history.id của lượt; không khóa ngoại vì trace ghi bằng session riêng.
    history_id UUID,
    session_id UUID,
    channel TEXT NOT NULL,
    outcome TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    span_count INTEGER NOT NULL,
    trace JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chat_traces_session_created_idx
    ON public.chat_traces (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS chat_traces_history_idx
    ON public.chat_traces (history_id);
CREATE INDEX IF NOT EXISTS chat_traces_request_idx
    ON public.chat_traces (request_id);
CREATE INDEX IF NOT EXISTS chat_traces_created_idx
    ON public.chat_traces (created_at DESC);
