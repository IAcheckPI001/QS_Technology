-- doc_chunks + match_doc_chunks cho tầng retrieve của chatbot.
-- Chạy thủ công trên Supabase (SQL editor); repo chưa có migration tool.
-- File có thể chạy lại: mọi lệnh đều idempotent.

create extension if not exists vector;

-- 1. Bảng (bỏ qua nếu đã tồn tại) -------------------------------------------
create table if not exists doc_chunks (
  id            bigint generated always as identity primary key,
  parent_id     bigint references doc_chunks(id),
  domain        text   not null check (domain in ('technical_docs','company_info','product_catalog')),
  scopes        text[] not null default '{}'
                check (scopes <@ array['installation','operation','configuration','maintenance']),
  product_models    text[] not null default '{}'
                check (product_models <@ array['F54','F86','F10T','ASTRO_10S','ASTRO_6AH','ASTRO_6AV','ASTRO_10I']),
  control_interface text[] not null default '{}',
  spec_attributes   text[] not null default '{}',
  chunk_type    text not null,
  is_active     boolean not null default true,
  check ((domain = 'technical_docs') = (cardinality(scopes) > 0)),
  check (domain <> 'technical_docs' or cardinality(product_models) > 0),
  doc_id        text not null,
  doc_type      text not null,
  lang          text not null default 'en',
  section_id    text,
  section_path  text[] not null default '{}',
  section_title text not null,
  page_start    int, page_end int,
  chunk_index   int not null,
  assets        jsonb not null default '[]',
  metadata      jsonb not null default '{}',
  content       text not null,
  summary_vi    text,
  keywords      text[] not null default '{}',
  embed_text    text not null,
  token_count   int,
  content_hash  text not null,
  embedding     vector(1536) not null,
  fts           tsvector generated always as (to_tsvector('simple', embed_text)) stored,
  unique (doc_id, chunk_index)
);

-- 2. FTS trên embed_text ------------------------------------------------------
-- embed_text gồm tiêu đề, tóm tắt tiếng Việt, câu hỏi thường gặp và từ khóa nên
-- khớp được câu hỏi tiếng Việt; bản đầu build trên section_title + content (tiếng Anh).
-- Cột generated không đổi biểu thức được nên drop/add lại (giá trị tự tính lại).
alter table doc_chunks drop column if exists fts;
alter table doc_chunks
  add column fts tsvector generated always as (to_tsvector('simple', embed_text)) stored;

-- 3. Index --------------------------------------------------------------------
create index if not exists doc_chunks_embedding_hnsw
  on doc_chunks using hnsw (embedding vector_cosine_ops);
create index if not exists doc_chunks_fts_gin on doc_chunks using gin (fts);
create index if not exists doc_chunks_scopes_gin on doc_chunks using gin (scopes);
create index if not exists doc_chunks_product_models_gin on doc_chunks using gin (product_models);
create index if not exists doc_chunks_control_interface_gin on doc_chunks using gin (control_interface);
create index if not exists doc_chunks_parent_id_idx on doc_chunks (parent_id);
create index if not exists doc_chunks_domain_active_idx on doc_chunks (domain) where is_active;

-- 4. Hybrid search: metadata filter + vector + FTS, hợp nhất bằng RRF ---------
-- Filter (giống nhau ở cả hai nhánh):
--   domain bắt buộc; scopes/models/control_interface rỗng hoặc null = không lọc;
--   chunk không gắn control_interface được coi là áp dụng chung.
-- spec_attributes chỉ cộng spec_boost vào fused_score, không lọc.
-- vector_score là cosine similarity của mọi dòng trả về (kể cả dòng chỉ đến từ FTS)
-- để tầng ứng dụng áp ngưỡng liên quan.
create or replace function match_doc_chunks(
  query_embedding    vector(1536),
  query_text         text,
  p_domain           text,
  p_scopes           text[] default null,
  p_models           text[] default null,
  p_control_interface text[] default null,
  p_spec_attributes  text[] default null,
  vector_k           int    default 20,
  fts_k              int    default 20,
  rrf_k              int    default 60,
  spec_boost         float8 default 0.005
)
returns table (
  id            bigint,
  parent_id     bigint,
  doc_id        text,
  section_title text,
  section_path  text[],
  page_start    int,
  page_end      int,
  content       text,
  assets        jsonb,
  vector_score  float8,
  keyword_score float8,
  fused_score   float8
)
language sql stable
as $$
  with
  -- Câu hỏi tự nhiên hiếm khi chứa mọi từ của chunk: chuyển AND thành OR,
  -- ts_rank_cd xếp chunk khớp nhiều từ hơn lên trên.
  q as (
    select nullif(
      replace(websearch_to_tsquery('simple', coalesce(query_text, ''))::text, '&', '|'),
      ''
    )::tsquery as tsq
  ),
  vec as (
    select c.id,
           row_number() over (order by c.embedding <=> query_embedding) as rank
    from doc_chunks c
    where c.is_active
      and c.domain = p_domain
      and (coalesce(cardinality(p_scopes), 0) = 0 or c.scopes && p_scopes)
      and (p_models is null or c.product_models && p_models)
      and (coalesce(cardinality(p_control_interface), 0) = 0
           or cardinality(c.control_interface) = 0
           or c.control_interface && p_control_interface)
    order by c.embedding <=> query_embedding
    limit vector_k
  ),
  kw as (
    select c.id,
           ts_rank_cd(c.fts, q.tsq) as score,
           row_number() over (order by ts_rank_cd(c.fts, q.tsq) desc) as rank
    from doc_chunks c, q
    where q.tsq is not null
      and c.fts @@ q.tsq
      and c.is_active
      and c.domain = p_domain
      and (coalesce(cardinality(p_scopes), 0) = 0 or c.scopes && p_scopes)
      and (p_models is null or c.product_models && p_models)
      and (coalesce(cardinality(p_control_interface), 0) = 0
           or cardinality(c.control_interface) = 0
           or c.control_interface && p_control_interface)
    order by score desc
    limit fts_k
  )
  select c.id, c.parent_id, c.doc_id, c.section_title, c.section_path,
         c.page_start, c.page_end, c.content, c.assets,
         1 - (c.embedding <=> query_embedding) as vector_score,
         kw.score as keyword_score,
         coalesce(1.0 / (rrf_k + vec.rank), 0)
           + coalesce(1.0 / (rrf_k + kw.rank), 0)
           + case when coalesce(cardinality(p_spec_attributes), 0) > 0
                       and c.spec_attributes && p_spec_attributes
                  then spec_boost else 0 end as fused_score
  from vec
  full outer join kw on kw.id = vec.id
  join doc_chunks c on c.id = coalesce(vec.id, kw.id)
  order by fused_score desc, c.id;
$$;
