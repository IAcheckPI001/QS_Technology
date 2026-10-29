-- Apply to Supabase before deploying POST /chat/crm (service key auth).
-- Idempotent: chạy lại nhiều lần không lỗi.

-- Hệ thống tích hợp (CRM backend) được phép gọi Chatbot server-to-server.
-- id là subject_id của principal service; giữ nguyên khi xoay vòng key.
CREATE TABLE IF NOT EXISTS public.service_integrations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'qs_technology',
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    disabled_at TIMESTAMPTZ
);

-- Credential của integration. Chỉ lưu SHA-256 (hex) của phần secret; key đầy
-- đủ `qsk_<id>_<secret>` chỉ hiển thị một lần khi cấp.
CREATE TABLE IF NOT EXISTS public.service_keys (
    id TEXT PRIMARY KEY,
    integration_id TEXT NOT NULL REFERENCES public.service_integrations (id),
    secret_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS service_keys_integration_idx
    ON public.service_keys (integration_id);

-- Bật RLS, không tạo policy: chặn đọc qua PostgREST (anon/authenticated).
-- Backend kết nối DATABASE_URL bằng role sở hữu bảng nên không bị RLS chặn.
ALTER TABLE public.service_integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.service_keys ENABLE ROW LEVEL SECURITY;
