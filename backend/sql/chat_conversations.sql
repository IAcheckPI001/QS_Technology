-- Bảng tóm tắt hội thoại + tìm kiếm cho QS AI Workspace (B2, cách kết hợp Q30, 2026-11-18).
-- Thiết kế, rủi ro R1–R10 và cách giảm: docs/ai/FRONTEND_REQUIREMENTS.md mục 19.11.
-- Chạy thủ công trên Supabase (SQL editor), TRƯỚC khi chạy code B2 (DR-04). Mọi lệnh idempotent.
--
-- Nguyên tắc: Python quyết định "nghĩa" của từng lượt và ghi vào cột cờ của chat_history; trigger ở
-- đây chỉ cộng dồn/gán vào chat_conversations, không đọc JSON, và không bao giờ làm hỏng việc ghi lượt.
--
-- Sau khi áp, theo thứ tự (FRONTEND_REQUIREMENTS 19.11 bước 5):
--   1. từ backend/: python scripts/backfill_history_flags.py        (điền cờ cho lượt cũ)
--   2. select public.rebuild_chat_conversations();                  (dựng lại bảng tóm tắt)
--   3. chạy code B2
--   4. từ backend/: python scripts/check_conversation_summary.py    (so lệch, chỉ đọc)
--
-- Kiểm nhanh sau khi áp (chỉ đọc):
--   select public.immutable_unaccent(lower('Đổi cảm biến báo lỗi ĐƯỜNG'));   -- doi cam bien bao loi duong
--   select count(*) from public.chat_conversations;
--
-- Sửa hoặc xoá chat_history bằng tay → chạy lại: select public.rebuild_chat_conversations();  (R2)
--
-- Gỡ (không ảnh hưởng chat_history; code cũ vẫn chạy):
--   drop trigger if exists chat_history_summary_trg on public.chat_history;
--   drop function if exists public.chat_history_summary_trigger();
--   drop function if exists public.rebuild_chat_conversations();
--   drop function if exists public.chat_conversations_apply(public.chat_history);
--   drop table if exists public.chat_conversations;
--   (cột cờ của chat_history và index giữ lại cũng vô hại)

-- 1. Extension ----------------------------------------------------------------
-- Supabase đặt extension ở schema extensions; Postgres khác: đổi tên schema ở đây và trong các hàm.
create extension if not exists unaccent with schema extensions;
create extension if not exists pg_trgm with schema extensions;

-- Hàm bỏ dấu IMMUTABLE dùng chung với doc_chunks_v2.sql (cùng định nghĩa; tạo lại ở đây để file
-- không phụ thuộc thứ tự áp). Không gỡ hàm này khi còn bảng chat_conversations / index tìm kiếm.
create or replace function public.immutable_unaccent(text)
returns text
language sql
immutable
parallel safe
strict
as $$
  select extensions.unaccent('extensions.unaccent'::regdictionary, $1)
$$;

-- 2. Cột cờ của từng lượt (Python ghi; mặc định an toàn cho code cũ) ------------------------------
alter table public.chat_history
  add column if not exists has_tool_errors boolean not null default false,
  add column if not exists is_handoff boolean not null default false,
  add column if not exists product_models text[] not null default '{}',
  add column if not exists ticket_id text;

-- 3. Bảng tóm tắt: một dòng mỗi phiên ------------------------------------------------------------
create table if not exists public.chat_conversations (
  session_id       uuid primary key,
  channel          text not null,
  started_at       timestamptz not null,
  last_message_at  timestamptz not null,
  last_history_id  uuid not null,
  last_query       text not null,
  last_status      text not null,
  question_count   integer not null default 0,
  cost_usd         double precision not null default 0,
  has_handoff      boolean not null default false,
  has_tool_errors  boolean not null default false,
  product_models   text[] not null default '{}',
  ticket_id        text,
  updated_at       timestamptz not null default now()
);

-- Chặn đọc qua PostgREST (anon/authenticated) như service_keys.sql; backend dùng role sở hữu bảng.
alter table public.chat_conversations enable row level security;

-- 4. Cộng dồn một lượt vào bảng tóm tắt (dùng chung cho trigger và dựng lại: một bản logic, R3) ---
create or replace function public.chat_conversations_apply(h public.chat_history)
returns void
language plpgsql
as $$
begin
  insert into public.chat_conversations as c (
    session_id, channel, started_at, last_message_at, last_history_id, last_query, last_status,
    question_count, cost_usd, has_handoff, has_tool_errors, product_models, ticket_id, updated_at
  ) values (
    h.session_id, h.channel, h.created_at, h.created_at, h.id, h.query_origin, h.status,
    1, coalesce(h.cost_usd, 0), h.is_handoff, h.has_tool_errors, h.product_models, h.ticket_id, now()
  )
  on conflict (session_id) do update set
    question_count  = c.question_count + 1,
    cost_usd        = c.cost_usd + excluded.cost_usd,
    started_at      = least(c.started_at, excluded.started_at),
    has_handoff     = c.has_handoff or excluded.has_handoff,
    has_tool_errors = c.has_tool_errors or excluded.has_tool_errors,
    -- Lượt mới hơn (theo created_at, bằng nhau thì theo id) thay "lượt cuối"; lượt đến muộn hơn
    -- nhưng cũ hơn (vd. ghi bằng session riêng) không ghi đè.
    last_history_id = case when (excluded.last_message_at, excluded.last_history_id) >= (c.last_message_at, c.last_history_id)
                           then excluded.last_history_id else c.last_history_id end,
    last_query      = case when (excluded.last_message_at, excluded.last_history_id) >= (c.last_message_at, c.last_history_id)
                           then excluded.last_query else c.last_query end,
    last_status     = case when (excluded.last_message_at, excluded.last_history_id) >= (c.last_message_at, c.last_history_id)
                           then excluded.last_status else c.last_status end,
    last_message_at = greatest(c.last_message_at, excluded.last_message_at),
    -- Model/ticket: chỉ thay khi lượt mới có giá trị (Python chỉ đặt ở lượt completed).
    product_models  = case when cardinality(excluded.product_models) > 0 then excluded.product_models else c.product_models end,
    ticket_id       = coalesce(excluded.ticket_id, c.ticket_id),
    updated_at      = now();
end;
$$;

-- 5. Trigger: không bao giờ làm hỏng việc ghi lượt (R1, R5) ------------------------------------
create or replace function public.chat_history_summary_trigger()
returns trigger
language plpgsql
as $$
begin
  begin
    -- Dòng tóm tắt đang bị khoá (kết nối khác của cùng phiên chưa commit) → bỏ qua thay vì chờ.
    perform 1 from public.chat_conversations where session_id = new.session_id for update nowait;
    perform public.chat_conversations_apply(new);
  exception
    when lock_not_available then
      raise warning 'chat_conversations skipped (locked) session_id=% history_id=%', new.session_id, new.id;
    when others then
      raise warning 'chat_conversations failed session_id=% history_id=% sqlstate=%', new.session_id, new.id, sqlstate;
  end;
  return new;
end;
$$;

drop trigger if exists chat_history_summary_trg on public.chat_history;
create trigger chat_history_summary_trg
  after insert on public.chat_history
  for each row execute function public.chat_history_summary_trigger();

-- 6. Dựng lại toàn bộ bảng tóm tắt từ chat_history (khởi tạo, sau khi sửa dữ liệu tay) ----------
create or replace function public.rebuild_chat_conversations()
returns integer
language plpgsql
as $$
declare
  h public.chat_history;
  n integer := 0;
begin
  -- Khoá bảng tóm tắt trong lúc dựng lại. Lượt mới ghi trong lúc này KHÔNG chờ: trigger gặp khoá
  -- (NOWAIT) nên bỏ qua và ghi warning → lượt đó thiếu trong bảng (R1). Chạy lúc vắng, rồi chạy
  -- scripts/check_conversation_summary.py; lệch thì chạy lại hàm này.
  lock table public.chat_conversations in exclusive mode;
  delete from public.chat_conversations;
  for h in select * from public.chat_history order by created_at, id loop
    perform public.chat_conversations_apply(h);
    n := n + 1;
  end loop;
  return n;
end;
$$;

-- 7. Index ----------------------------------------------------------------------------------
-- Lượt của một phiên (phân trang /history, EXISTS theo thời gian trong phiên).
create index if not exists chat_history_session_created_idx
  on public.chat_history (session_id, created_at, id);
-- Lọc thời gian, số liệu trong khoảng ngày.
create index if not exists chat_history_created_idx
  on public.chat_history (created_at);
-- Tìm từ khoá không dấu trong câu hỏi (LIKE '%…%' dùng được index nhờ trigram).
create index if not exists chat_history_query_trgm_idx
  on public.chat_history using gin (public.immutable_unaccent(lower(query_origin)) extensions.gin_trgm_ops);
-- Danh sách + phân trang con trỏ theo lần nhắn cuối.
create index if not exists chat_conversations_last_idx
  on public.chat_conversations (last_message_at desc, session_id desc);
create index if not exists chat_conversations_channel_idx
  on public.chat_conversations (channel);
create index if not exists chat_conversations_status_idx
  on public.chat_conversations (last_status);
create index if not exists chat_conversations_models_idx
  on public.chat_conversations using gin (product_models);
