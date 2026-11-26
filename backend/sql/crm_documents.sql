-- Danh mục tài liệu lấy từ kho tài liệu công khai của CRM (company-docs/website-tree), cho màn "Tài liệu & chunk"
-- của Support Workspace (B6 phần đọc, 2026-11-26). Idempotent: chạy lại an toàn. Áp tay trên Supabase trước khi
-- bật WORKSPACE_DOCUMENTS_API_ENABLED (DR-04).
--
-- Bảng do lệnh CLI ghi (chạy tay):
--   .\venv\Scripts\python.exe -m app.modules.chunking_loader.sync_crm_documents --tree --apply
-- Nguồn: sổ crm_sources.lock.json (tài liệu đã đồng bộ để cắt đoạn) + cây CRM (mọi tài liệu, kể cả nhánh chưa dùng).
-- Không lưu URL đã ký của CRM (hết hạn); link xem/tải PDF xin mới mỗi lần bấm qua API Workspace.

create table if not exists public.crm_documents (
  crm_id           uuid        primary key,                -- `id` của node tài liệu trên CRM
  doc_id           text,                                   -- doc_chunks_v2.doc_id; null = chưa đưa vào chatbot
  name             text        not null,
  branch           text        not null,                   -- nhánh gốc trên CRM: "Bộ điều khiển", "QS Servo"…
  folder           text,                                   -- thư mục chứa tài liệu (thư mục sản phẩm, vd "Astro 6AV")
  model            text,                                   -- mã model trong registry (F54, 6AVE…)
  document_type    text,                                   -- installation | operation | … (như CRM)
  language         text,                                   -- en | vi
  connection_types text[]      not null default '{}',
  version          text,
  file_size        bigint,
  sha256           text,                                   -- của PDF đã tải (sổ nguồn); null = chưa tải
  sync_mode        text        not null default 'none' check (sync_mode in ('build', 'run_only', 'none')),
  sync_state       text,                                   -- trạng thái trong sổ nguồn (fetched…)
  synced_at        date,                                   -- ngày tải PDF (sổ nguồn)
  crm_updated_at   timestamptz,
  on_crm           boolean     not null default true,      -- false: không còn trong cây CRM lần đồng bộ gần nhất
  last_seen_at     timestamptz,                            -- lần gần nhất thấy trong cây CRM
  sort_order       int,
  updated_at       timestamptz not null default now()
);

create index if not exists crm_documents_doc_id_idx on public.crm_documents (doc_id) where doc_id is not null;
create index if not exists crm_documents_branch_idx on public.crm_documents (branch, folder);

-- Chỉ backend (service role / kết nối DATABASE_URL) đọc ghi; không mở cho anon.
alter table public.crm_documents enable row level security;
