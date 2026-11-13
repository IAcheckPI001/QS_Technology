-- doc_chunks_v2 + match_doc_chunks_v2 cho tầng retrieve (D-009, 2026-11-13).
-- Thiết kế và lý do từng cột: docs/ai/reports/p2_doc_chunks_schema_review.md (§4, §5, §10–§12).
-- Tạo SONG SONG bảng doc_chunks cũ (không đụng doc_chunks / match_doc_chunks).
-- Chạy thủ công trên Supabase (SQL editor); repo chưa có migration tool (DR-04). File chạy lại được:
-- mọi lệnh idempotent (hàm match được drop rồi tạo lại để đổi được kết quả trả về).
--
-- Điểm đang đo (bật/tắt bằng tham số, chốt sau Bước 4 trên DB thật):
--   p_include_parents (D-008), p_codes / code_k (S-02), p_unaccent + cột fts_unaccent (S-05),
--   p_chunk_types / type_boost (S-04), vector_weight / fts_weight / code_weight (R-4),
--   p_scope_mode = 'boost' + scope_boost (R-2). Bỏ dấu không có lợi → bỏ cột fts_unaccent và tham số.
--
-- Kiểm sau khi áp (chỉ đọc): backend/scripts/inspect_doc_chunks.py --table doc_chunks_v2
-- Gỡ toàn bộ v2 (không ảnh hưởng doc_chunks cũ):
--   drop function if exists public.match_doc_chunks_v2(vector, text, text, text[], text[], text[], text[], text[],
--     text[], int, int, int, int, float8, float8, boolean, boolean, boolean, float8, float8, float8, text, float8);
--   drop table if exists public.doc_chunks_v2;
--   drop function if exists public.immutable_unaccent(text);   -- sau khi bỏ bảng (cột fts_unaccent dùng hàm này)
--   drop extension if exists unaccent;                          -- nếu không còn dùng

-- 1. Extension ----------------------------------------------------------------
-- vector đã có ở schema public; Supabase để các extension khác ở schema extensions.
create extension if not exists vector;
create extension if not exists unaccent with schema extensions;

-- unaccent() là STABLE (phụ thuộc search_path/từ điển) nên không dùng được trong cột generated.
-- Bọc với từ điển ghi rõ schema → IMMUTABLE.
create or replace function public.immutable_unaccent(text)
returns text
language sql
immutable
parallel safe
strict
as $$
  select extensions.unaccent('extensions.unaccent'::regdictionary, $1)
$$;

-- 2. Bảng ---------------------------------------------------------------------
create table if not exists public.doc_chunks_v2 (
  id                 bigint generated always as identity primary key,
  -- tài liệu
  doc_id             text   not null,
  doc_version        text   not null,
  doc_title          text   not null,
  doc_type           text   not null,
  lang               text   not null default 'en',
  -- khóa và cấu trúc
  chunk_key          text   not null,
  chunk_index        int    not null,
  chunk_role         text   not null check (chunk_role in ('parent', 'child', 'standalone')),
  parent_id          bigint references public.doc_chunks_v2 (id) on delete cascade,
  chunk_type         text   not null,
  -- lọc
  domain             text   not null check (domain in ('technical_docs', 'company_info', 'product_catalog')),
  scopes             text[] not null default '{}'
                     check (scopes <@ array['installation', 'operation', 'configuration', 'maintenance']),
  -- Không check danh sách model: loader kiểm theo registry (một nguồn; tránh lệch như ASTRO_* ở bảng cũ).
  product_models     text[] not null default '{}',
  applies_to_models  text[] not null default '{}',
  control_interface  text[] not null default '{}',
  spec_attributes    text[] not null default '{}',
  -- vị trí
  section_id         text,
  section_path       text[] not null default '{}',
  section_title      text   not null,
  page_start         int,
  page_end           int,
  printed_page_start int,
  printed_page_end   int,
  -- nội dung
  content            text   not null,
  summary_vi         text,
  keywords           text[] not null default '{}',
  codes              text[] not null default '{}',
  -- tìm kiếm
  embed_text         text   not null,
  embedding          vector(1536),
  embedding_model    text,
  token_count        int,
  content_hash       text   not null,
  fts                tsvector generated always as (to_tsvector('simple', embed_text)) stored,
  fts_unaccent       tsvector generated always as
                       (to_tsvector('simple', public.immutable_unaccent(embed_text))) stored,
  -- kèm theo
  assets             jsonb  not null default '[]',
  metadata           jsonb  not null default '{}',
  -- vận hành
  source             text   not null check (source in ('builder', 'manual')),
  review_status      text   not null default 'draft' check (review_status in ('draft', 'approved')),
  is_active          boolean not null default true,
  source_run         text,
  loaded_at          timestamptz not null default now(),

  constraint doc_chunks_v2_key_uniq   unique (doc_id, doc_version, chunk_key),
  constraint doc_chunks_v2_index_uniq unique (doc_id, doc_version, chunk_index),
  constraint doc_chunks_v2_tech_scopes check ((domain = 'technical_docs') = (cardinality(scopes) > 0)),
  constraint doc_chunks_v2_tech_models check (domain <> 'technical_docs' or cardinality(product_models) > 0),
  constraint doc_chunks_v2_child_parent check (chunk_role <> 'child' or parent_id is not null),
  -- D-008: chunk lá bắt buộc có embedding; chunk cha được rỗng.
  constraint doc_chunks_v2_leaf_embedding check (chunk_role = 'parent' or embedding is not null),
  constraint doc_chunks_v2_embedding_model check (embedding is null or embedding_model is not null)
);

-- 3. Index --------------------------------------------------------------------
-- Dòng embedding null (chunk cha) không vào HNSW.
create index if not exists doc_chunks_v2_embedding_hnsw
  on public.doc_chunks_v2 using hnsw (embedding vector_cosine_ops);
create index if not exists doc_chunks_v2_fts_gin          on public.doc_chunks_v2 using gin (fts);
create index if not exists doc_chunks_v2_fts_unaccent_gin on public.doc_chunks_v2 using gin (fts_unaccent);
create index if not exists doc_chunks_v2_codes_gin        on public.doc_chunks_v2 using gin (codes);
create index if not exists doc_chunks_v2_scopes_gin       on public.doc_chunks_v2 using gin (scopes);
create index if not exists doc_chunks_v2_models_gin       on public.doc_chunks_v2 using gin (product_models);
create index if not exists doc_chunks_v2_ci_gin           on public.doc_chunks_v2 using gin (control_interface);
create index if not exists doc_chunks_v2_doc_idx          on public.doc_chunks_v2 (doc_id, doc_version);
create index if not exists doc_chunks_v2_parent_idx       on public.doc_chunks_v2 (parent_id);
create index if not exists doc_chunks_v2_domain_live_idx
  on public.doc_chunks_v2 (domain) where is_active and review_status = 'approved';

-- 4. Hybrid search ------------------------------------------------------------
-- Lọc (giống nhau ở mọi nhánh): is_active, domain bắt buộc; scopes/models/control_interface rỗng hoặc null
-- = không lọc (sửa E-05); chunk không gắn control_interface áp dụng chung; p_approved_only (D-009) chỉ lấy
-- chunk approved; chunk cha không được tìm trừ khi p_include_parents (D-008).
-- Nhánh: vector (HNSW, iterative scan để bộ lọc không làm hụt kết quả), FTS (OR các từ, ts_rank_cd; bỏ dấu khi
-- p_unaccent), mã (chỉ khi p_codes không rỗng; xếp theo số mã trùng). Hợp nhất RRF + spec_boost + type_boost.
-- vector_score là cosine similarity của mọi dòng trả về (0 khi dòng không có embedding) để tầng ứng dụng áp
-- ngưỡng liên quan.
-- 2026-11-13 (R-4, R-2 — website-qa LOG "Eval 14 câu"): trọng số từng nhánh khi trộn RRF (vector_weight,
-- fts_weight, code_weight; mặc định 1 = như cũ) và p_scope_mode: 'filter' (mặc định, như cũ: scope là bộ lọc cứng) |
-- 'boost' (không lọc theo scope, cộng scope_boost cho chunk đúng scope).
drop function if exists public.match_doc_chunks_v2(
  vector, text, text, text[], text[], text[], text[], text[], text[],
  int, int, int, int, float8, float8, boolean, boolean, boolean);
drop function if exists public.match_doc_chunks_v2(
  vector, text, text, text[], text[], text[], text[], text[], text[],
  int, int, int, int, float8, float8, boolean, boolean, boolean, float8, float8, float8, text, float8);

create function public.match_doc_chunks_v2(
  query_embedding     vector(1536),
  query_text          text,
  p_domain            text,
  p_scopes            text[]  default null,
  p_models            text[]  default null,
  p_control_interface text[]  default null,
  p_spec_attributes   text[]  default null,
  p_codes             text[]  default null,
  p_chunk_types       text[]  default null,
  vector_k            int     default 20,
  fts_k               int     default 20,
  code_k              int     default 20,
  rrf_k               int     default 60,
  spec_boost          float8  default 0.005,
  type_boost          float8  default 0,
  p_approved_only     boolean default true,
  p_include_parents   boolean default false,
  p_unaccent          boolean default false,
  vector_weight       float8  default 1,
  fts_weight          float8  default 1,
  code_weight         float8  default 1,
  p_scope_mode        text    default 'filter',
  scope_boost         float8  default 0
)
returns table (
  id                 bigint,
  parent_id          bigint,
  chunk_key          text,
  chunk_role         text,
  chunk_type         text,
  doc_id             text,
  doc_version        text,
  doc_title          text,
  section_title      text,
  section_path       text[],
  page_start         int,
  page_end           int,
  printed_page_start int,
  printed_page_end   int,
  content            text,
  assets             jsonb,
  vector_score       float8,
  keyword_score      float8,
  code_score         float8,
  vector_rank        bigint,
  keyword_rank       bigint,
  code_rank          bigint,
  fused_score        float8
)
language sql
stable
set hnsw.iterative_scan = 'relaxed_order'
set hnsw.ef_search = '100'
as $$
  with
  q as (
    select nullif(
      replace(
        websearch_to_tsquery(
          'simple',
          case when p_unaccent then public.immutable_unaccent(coalesce(query_text, ''))
               else coalesce(query_text, '') end
        )::text,
        '&', '|'),
      ''
    )::tsquery as tsq
  ),
  vec_raw as materialized (
    select c.id, c.embedding <=> query_embedding as dist
    from public.doc_chunks_v2 c
    where c.embedding is not null
      and c.is_active
      and c.domain = p_domain
      and (not p_approved_only or c.review_status = 'approved')
      and (p_include_parents or c.chunk_role <> 'parent')
      and (p_scope_mode = 'boost' or coalesce(cardinality(p_scopes), 0) = 0 or c.scopes && p_scopes)
      and (coalesce(cardinality(p_models), 0) = 0 or c.product_models && p_models)
      and (coalesce(cardinality(p_control_interface), 0) = 0
           or cardinality(c.control_interface) = 0
           or c.control_interface && p_control_interface)
    order by c.embedding <=> query_embedding
    limit vector_k
  ),
  -- relaxed_order có thể trả lệch thứ tự nhẹ → xếp hạng lại theo khoảng cách.
  vec as (
    select v.id, row_number() over (order by v.dist, v.id) as rank
    from vec_raw v
  ),
  kw as (
    select c.id,
           ts_rank_cd(case when p_unaccent then c.fts_unaccent else c.fts end, q.tsq)::float8 as score,
           row_number() over (
             order by ts_rank_cd(case when p_unaccent then c.fts_unaccent else c.fts end, q.tsq) desc, c.id
           ) as rank
    from public.doc_chunks_v2 c, q
    where q.tsq is not null
      and ((not p_unaccent and c.fts @@ q.tsq) or (p_unaccent and c.fts_unaccent @@ q.tsq))
      and c.is_active
      and c.domain = p_domain
      and (not p_approved_only or c.review_status = 'approved')
      and (p_include_parents or c.chunk_role <> 'parent')
      and (p_scope_mode = 'boost' or coalesce(cardinality(p_scopes), 0) = 0 or c.scopes && p_scopes)
      and (coalesce(cardinality(p_models), 0) = 0 or c.product_models && p_models)
      and (coalesce(cardinality(p_control_interface), 0) = 0
           or cardinality(c.control_interface) = 0
           or c.control_interface && p_control_interface)
    order by score desc, c.id
    limit fts_k
  ),
  cd as (
    select c.id,
           (select count(*) from unnest(c.codes) as x where x = any (p_codes))::float8 as score
    from public.doc_chunks_v2 c
    where coalesce(cardinality(p_codes), 0) > 0
      and c.codes && p_codes
      and c.is_active
      and c.domain = p_domain
      and (not p_approved_only or c.review_status = 'approved')
      and (p_include_parents or c.chunk_role <> 'parent')
      and (p_scope_mode = 'boost' or coalesce(cardinality(p_scopes), 0) = 0 or c.scopes && p_scopes)
      and (coalesce(cardinality(p_models), 0) = 0 or c.product_models && p_models)
      and (coalesce(cardinality(p_control_interface), 0) = 0
           or cardinality(c.control_interface) = 0
           or c.control_interface && p_control_interface)
    order by score desc, c.id
    limit code_k
  ),
  cd_ranked as (
    select d.id, d.score, row_number() over (order by d.score desc, d.id) as rank
    from cd d
  ),
  ids as (
    select vec.id from vec
    union
    select kw.id from kw
    union
    select cd_ranked.id from cd_ranked
  )
  select c.id, c.parent_id, c.chunk_key, c.chunk_role, c.chunk_type,
         c.doc_id, c.doc_version, c.doc_title, c.section_title, c.section_path,
         c.page_start, c.page_end, c.printed_page_start, c.printed_page_end,
         c.content, c.assets,
         coalesce(1 - (c.embedding <=> query_embedding), 0)::float8 as vector_score,
         kw.score as keyword_score,
         cd_ranked.score as code_score,
         vec.rank as vector_rank,
         kw.rank as keyword_rank,
         cd_ranked.rank as code_rank,
         vector_weight * coalesce(1.0 / (rrf_k + vec.rank), 0)::float8
           + fts_weight * coalesce(1.0 / (rrf_k + kw.rank), 0)::float8
           + code_weight * coalesce(1.0 / (rrf_k + cd_ranked.rank), 0)::float8
           + case when p_scope_mode = 'boost' and coalesce(cardinality(p_scopes), 0) > 0
                       and c.scopes && p_scopes
                  then scope_boost else 0 end
           + case when coalesce(cardinality(p_spec_attributes), 0) > 0
                       and c.spec_attributes && p_spec_attributes
                  then spec_boost else 0 end
           + case when coalesce(cardinality(p_chunk_types), 0) > 0
                       and c.chunk_type = any (p_chunk_types)
                  then type_boost else 0 end
           as fused_score
  from ids
  join public.doc_chunks_v2 c on c.id = ids.id
  left join vec on vec.id = c.id
  left join kw on kw.id = c.id
  left join cd_ranked on cd_ranked.id = c.id
  order by fused_score desc, c.id;
$$;
