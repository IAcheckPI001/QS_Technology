# Đánh giá lại `doc_chunks` + `match_doc_chunks` (Bước 5, bản đề xuất v2)

Cập nhật: 2026-11-13 · Trạng thái: **đã duyệt các điểm C** (Toma, 2026-11-13 → D-009 trong
[decisions.md](../decisions.md)); danh sách cột chốt ở §10, đo bỏ dấu ở §11, quy tắc `approved` ở §12. Hẹn từ
contract C2 §13 ([p2_chunk_contract.md](p2_chunk_contract.md)).

## 0. Bối cảnh

- Supabase Cloud chỉ có một môi trường, **chưa có người dùng thật**. Bảng `doc_chunks` hiện chỉ có 3 chunk thử. Bảng và
  hàm là thiết kế bản trước, chưa chạy với chunk thật (Toma, 2026-11-13).
- Mục tiêu: trước đợt nạp chunk từ luồng chunking (F54 thí điểm, rồi các PDF upload), chốt cấu trúc bảng và hàm
  tìm kiếm để tìm, so sánh và lọc chunk chính xác nhất. Thiết kế phải chung cho mọi tài liệu, không riêng F54.
- Nguyên tắc: điểm nào **chắc chắn** (sửa lỗi, quyết định đã có) thì làm luôn trong v2; điểm nào phải **đo** mới biết
  thì đưa vào v2 dưới dạng tham số bật/tắt để so A/B trên cùng dữ liệu, chốt sau khi đo (Bước 4/5).

## 1. Hiện trạng trên Supabase (đọc ngày 2026-11-13)

Đọc bằng `backend/scripts/inspect_doc_chunks.py` (chỉ SELECT, transaction READ ONLY).

| Mục | Giá trị thật |
|---|---|
| Postgres / pgvector | 17.11 / **0.8.2** (có iterative scan cho HNSW khi có bộ lọc; đang `off`; `hnsw.ef_search` = 40) |
| Extension có thể cài | `unaccent` 1.1, `pg_trgm` 1.6 (chưa cài) |
| Dữ liệu | 3 dòng, đều **không phải** `technical_docs`: F86 spec (`product_catalog` × 2), giới thiệu công ty (`company_info`); có embedding, không có `parent_id` |
| Index | HNSW cosine, GIN `fts`/`scopes`/`product_models`/`control_interface`, btree `parent_id`, `(domain) where is_active` |

**Lệch giữa repo và database** (phải xử lý, không âm thầm sửa):

| # | Repo (`backend/sql/…`) | Database thật | Hệ quả |
|---|---|---|---|
| L-1 | `embedding vector(1536) not null` | `vector(1536)` **nullable** | Khớp với loader cũ (insert trước, embed sau); repo sai |
| L-2 | `product_models` ⊆ {F54, F86, F86E, F10T, 6AH, 6AHE, 6AV, 6AVE, 10iV, 10iVE} (`migrate_product_models_crm.sql`) | ⊆ {F54, F86, F10T, **ASTRO_10S, ASTRO_6AH, ASTRO_6AV, ASTRO_10I**} | Migration model **chưa áp**; registry dùng mã mới (6AH, 10iV…) → nạp chunk 6AH sẽ bị từ chối |
| L-3 | Nhánh vector lọc model bằng `cardinality(p_models)`, nhánh FTS bằng `p_models is null` (E-05) | **Cả hai nhánh** dùng `p_models is null` | Truyền `p_models = []` → cả vector lẫn FTS trả rỗng (nặng hơn E-05 ghi trong repo) |
| L-4 | Registry coverage `technical_docs: {F86: …}` | 0 dòng `technical_docs` | Câu hỏi kỹ thuật F86 hiện không có chunk nào để tìm |

## 2. Dữ liệu sẽ nạp (bằng chứng từ luồng chunking)

| | F54 (`f54/eval-k`) | F86 Installation (`eval-j-regress`) |
|---|---|---|
| Dòng | 296: 53 cha, 150 con, 93 độc lập | 23 độc lập |
| Loại chunk | procedure 70, section 53, figure 51, wiring 51, parameter 34, overview 27, table 8, dimension 1, alarm 1 | figure 9, wiring 8, pinout 6 |
| Token chunk lá | p50 341, p90 467, max 792; cha max 712 | p50 96, max 529 |
| Mã kỹ thuật | `param_refs` có cấu trúc ở 65 lá (vd. `{prefix: M, codes: [1920…1923]}`, có dải); `io_codes` ở 13 lá; nhãn hình OCR ở 105 lá | `io_codes` ở 8 lá |
| Ghi chú áp dụng (T-13) | 2 chunk (vd. "Not available on F54 controller") | 0 |
| Làm giàu VI | 243/243 lá (bản nháp v4) | chưa |
| `assets` | 189 dòng | 16 dòng |
| Phiên bản | `doc_version` = "V.02" | "2024-04-25" |

**Khóa chunk không ổn định giữa các lần build**: so `eval-h` với `eval-k`, 0/294 chunk giữ nguyên `chunk_key`
(B-số đánh lại khi số chunk đổi), trong khi cặp (`content_hash`, `section_path`) khớp 294/296. → `chunk_key` chỉ
dùng làm khóa **trong một phiên bản**; nhãn đánh giá và việc so chunk giữa các lần nạp dùng (`content_hash`,
`section_path`).

## 3. Yêu cầu từ luồng tra cứu

1. D-008: chỉ tìm chunk con/độc lập; cha chỉ mở rộng ngữ cảnh (retriever đã gom theo `parent_id`, chỉ thiếu dữ liệu).
2. Thay cả bộ chunk của một tài liệu một cách nguyên tử khi nạp lại (không trộn bản cũ/mới).
3. Câu hỏi theo mã (`M1920`, `#12010`, `X41`, `CN3`, `D4000`) phải khớp chính xác; parser `simple` hiện tách
   `#12010` → `12010` và dải `#12090–#12093` không khớp từng mã (S-02).
4. Lọc model đúng ở cả hai nhánh; `[]` và `null` cùng nghĩa "không lọc" (L-3/E-05).
5. Trace phải biết chunk nào, vai trò, loại, điểm từng nhánh để đánh giá và dò tham số.
6. Chung cho mọi tài liệu: không ràng buộc riêng hãng/model cứng trong SQL nếu tránh được.

## 4. Đề xuất bảng `doc_chunks_v2`

Ký hiệu cột "Mức": **C** = chắc chắn làm; **Đ** = có trong v2 nhưng dùng hay không quyết sau khi đo; **G** = giữ như v1.

| Cột | Kiểu | Mức | Lý do / ghi chú |
|---|---|---|---|
| `id` | bigint identity PK | G | |
| `doc_id`, `doc_version` | text not null | **C** | S-01: nhiều phiên bản cùng tài liệu; nạp lại thay theo cặp này |
| `chunk_key` | text not null | **C** | Khóa trong phiên bản; `unique (doc_id, doc_version, chunk_key)` |
| `chunk_index` | int not null | G | `unique (doc_id, doc_version, chunk_index)` (thay `unique(doc_id, chunk_index)`) |
| `chunk_role` | text not null, check in (`parent`, `child`, `standalone`) | **C** | D-008 (S-03) |
| `parent_id` | bigint FK → id, `on delete cascade` | G | Loader gán thật (sửa E-01); check: `child` phải có `parent_id` |
| `domain`, `scopes`, `control_interface`, `spec_attributes` | như v1 | G | Giữ check `domain`, `scopes` và ràng buộc technical_docs |
| `product_models` | text[] not null | **C** (bỏ check cứng) | L-2: danh sách model trong SQL lệch registry và phải sửa SQL mỗi khi có model mới. Đề xuất: **loader kiểm theo registry** (một nguồn), bảng chỉ giữ check "technical_docs phải có model" |
| `applies_to_models` | text[] default `{}` | Đ | S-06: model áp dụng cấp chunk (rỗng = theo `product_models`). F54 hiện 0 chunk dùng → lọc theo cột này để sau |
| `chunk_type` | text not null | G | Dùng cho cộng điểm theo loại (S-04, Đ) |
| `doc_type`, `lang`, `section_id`, `section_path`, `section_title`, `page_start`, `page_end` | như v1 | G | |
| `printed_page_start`, `printed_page_end` | int | **C** | Trích dẫn cho người dùng theo số trang in trên sách (đang nằm trong `metadata`) |
| `content` | text not null | G | Đưa cho LLM trả lời và hiển thị |
| `summary_vi` | text | G | |
| `keywords` | text[] | G | |
| `codes` | text[] not null default `{}` | **C** (cột) / Đ (nhánh tìm) | S-02: mã đã chuẩn hóa (`M1920`, `#12010`, `X41`, `CN3`, `D4000`), **trải dải** (`#12090–#12093` → 4 mã, giới hạn 64), từ `param_refs`, `io_codes`, nhãn hình đã xác minh. GIN |
| `embed_text` | text not null | G | |
| `embedding` | vector(1536), check `chunk_role = 'parent' or embedding is not null` | **C** | Lá bắt buộc có embedding; cha được rỗng (D-008). Giai đoạn đo vẫn embed cha (53 dòng, ~0 USD) để so biến thể "tìm cả cha" |
| `embedding_model` | text not null | **C** | S-07: biết khi nào phải embed lại |
| `fts` | tsvector generated `to_tsvector('simple', embed_text)` | G | |
| `fts_unaccent` | tsvector generated qua hàm `immutable_unaccent` | Đ | S-05: câu hỏi không dấu. Cần `create extension unaccent` + hàm wrapper immutable. Giữ cả hai cột tới khi đo xong |
| `token_count`, `content_hash` | | G | `content_hash` + `section_path` là khóa so giữa các lần build |
| `assets` | jsonb | G | Giữ chỗ cho mô tả ảnh/facts (chưa embed; chờ quyết định vision) |
| `metadata` | jsonb | G | Provenance, `faq_vi`, `flags`, `param_refs`, ghi chú áp dụng T-13 |
| `source` | text check in (`builder`, `manual`) | **C** | S-07: phân biệt chunk tay và chunk builder |
| `review_status` | text check in (`draft`, `approved`) | **C** | S-07: trạng thái cổng 2b/2c; retriever có thể chỉ dùng `approved` khi lên production |
| `source_run`, `loaded_at` | text, timestamptz default now() | **C** | Truy về run `data/ingest_runs/...` |
| `is_active` | bool | G | Bật/tắt cả một phiên bản |

Index: HNSW cosine trên `embedding` (dòng null không vào index nên cha tự bị loại); GIN `fts`, `fts_unaccent`,
`codes`, `scopes`, `product_models`, `control_interface`; btree `(doc_id, doc_version)`, `parent_id`.

## 5. Đề xuất hàm `match_doc_chunks_v2`

Tham số (thêm so với v1 in đậm): `query_embedding, query_text, p_domain, p_scopes, p_models, p_control_interface,
p_spec_attributes`, **`p_codes text[]`, `p_chunk_types text[]`**, `vector_k, fts_k`, **`code_k`**, `rrf_k,
spec_boost`, **`type_boost`, `p_include_parents bool = false`, `p_unaccent bool = false`**.

Logic:
1. **Lọc chung** (giống nhau ở mọi nhánh): `is_active`, `domain`; scopes, models, control_interface **rỗng hoặc null
   = không lọc** (sửa L-3/E-05); `chunk_role <> 'parent'` trừ khi `p_include_parents` (D-008).
2. **Nhánh vector**: HNSW cosine, `vector_k`. Hàm đặt `hnsw.iterative_scan = relaxed_order` và `hnsw.ef_search`
   (mệnh đề `SET` của hàm) để bộ lọc không làm hụt kết quả khi bảng lớn; sắp lại theo khoảng cách ở ngoài.
3. **Nhánh FTS**: như v1 (OR các từ, `ts_rank_cd`); dùng `fts_unaccent` + câu hỏi bỏ dấu khi `p_unaccent`.
4. **Nhánh mã** (mới, chỉ chạy khi `p_codes` không rỗng): `codes && p_codes`, xếp theo số mã trùng, `code_k`.
5. **Hợp nhất RRF** 3 danh sách + `spec_boost` (như v1) + `type_boost` khi `chunk_type = any(p_chunk_types)`.
6. **Trả về** thêm: `chunk_key`, `chunk_role`, `chunk_type`, `doc_version`, `printed_page_start/end`,
   `code_score`, `vector_rank`, `keyword_rank`, `code_rank` (cho trace và dò tham số). `vector_score` vẫn tính cho mọi
   dòng (ngưỡng `min_similarity` ở retriever giữ nguyên ý nghĩa).

Các tham số Đ (`p_include_parents`, `p_unaccent`, `p_codes`, `type_boost`) cho phép đo mọi biến thể trên **một bảng,
một lần nạp**. Sau khi chốt, bỏ tham số thừa và cột thừa (vd. `fts` hoặc `fts_unaccent`).

## 6. Việc phía khác đi kèm (ngoài bảng/hàm)

| Phía | Việc | Mức |
|---|---|---|
| Loader (`app/modules/chunking_loader/`) | Đọc `doc_chunks_v2.jsonl` của run; kiểm model theo registry; **embed trước rồi insert trong một transaction** (cha trước, gán `parent_id` theo `parent_key`), xóa bản cũ cùng (`doc_id`, `doc_version`); dry-run; xóa theo `doc_id` | C |
| `doc_ingest/export` | Adapter `doc_chunks_v2.py`: thêm `doc_version`, `chunk_role`, `codes` (trải dải), `printed_page_*`, `source`, `review_status` | C |
| Retriever / repository (website-qa) | Gọi `match_doc_chunks_v2`; trích mã từ câu hỏi **bằng regex** (không cần LLM; mẫu mã đặt trong registry, không riêng một hãng) → `p_codes`; ánh xạ intent → `p_chunk_types` (vd. `troubleshoot.error` → `alarm`); cha lấy qua `fetch_by_ids` như hiện tại | C (gọi hàm), Đ (mã, loại) |
| Registry | Thêm F54 vào coverage `technical_docs` khi đã nạp; đồng bộ danh sách model (L-2) | C |
| SQL lệch (L-1…L-3) | Không sửa bảng v1 (3 dòng thử); v2 là bảng mới. 3 dòng v1 (product_catalog/company_info) chép sang v2 với `source = manual` khi chuyển | C |

## 7. Cách chuyển đổi

1. Tạo `backend/sql/doc_chunks_v2.sql` (idempotent): extension `unaccent`, hàm wrapper, bảng `doc_chunks_v2`,
   index, `match_doc_chunks_v2`. Áp tay theo DR-04 (hỏi trước khi áp), ghi ngày vào LOG website-qa.
2. Nạp F54 (+ F86 Installation) vào v2 bằng loader mới; bảng v1 giữ nguyên trong lúc đo.
3. Chạy `evals/run_retrieval_eval.py` với các biến thể của §5 → chốt tham số và cột.
4. Retriever chuyển sang v2; chép 3 dòng v1; sau đó đổi tên `doc_chunks_v2` → `doc_chunks` hoặc bỏ v1 (quyết khi
   chuyển).

## 8. Biến thể sẽ đo (Bước 4 trên DB thật)

| Biến thể | Tham số | Câu hỏi trả lời |
|---|---|---|
| Có / không tìm cha | `p_include_parents` | Xác nhận D-008 |
| Nhánh mã | `p_codes` rỗng / có | S-02 có cải thiện câu hỏi theo mã |
| Bỏ dấu | `p_unaccent` | S-05 với câu hỏi không dấu |
| Cộng điểm loại | `type_boost` 0 / > 0 | S-04 |
| Iterative scan / `ef_search` | cấu hình hàm | Hụt kết quả khi có bộ lọc |
| `vector_k`, `fts_k`, `rrf_k`, `final_chunk_top_k`, `min_similarity` | Settings | Bộ tham số v2 |

## 9. Quyết định của Toma (2026-11-13)

1. Duyệt các điểm **C** ở §4–§6.
2. Tạo **bảng mới `doc_chunks_v2`** song song; danh sách cột ở §10.
3. Bỏ dấu: **cài `unaccent` trong SQL v2 để đo** (§11); kết quả không có lợi thì không áp dụng (bỏ cột, tắt tham số).
4. Retriever **chỉ dùng chunk `approved`** → §12. Cổng 2b "tạm" (nhãn `verified: false`) **không** tính là đạt:
   F54 chỉ thành `approved` sau khi team xác nhận nhãn.

## 10. Danh sách cột `doc_chunks_v2` (chốt)

| # | Cột | Kiểu, ràng buộc | Lý do |
|---|---|---|---|
| 1 | `id` | `bigint generated always as identity` PK | Khóa dòng; retriever, trace và `parent_id` dùng |
| 2 | `doc_id` | `text not null` | Tài liệu nguồn; lọc, xóa, thay theo tài liệu |
| 3 | `doc_version` | `text not null` | S-01: nhiều phiên bản cùng tài liệu; nạp lại thay đúng phiên bản |
| 4 | `doc_title` | `text not null` | Trích dẫn nguồn cho người dùng (đang nằm trong `metadata`) |
| 5 | `doc_type` | `text not null` | Loại tài liệu (installation_manual, user_guide…); hiển thị, lọc sau này |
| 6 | `lang` | `text not null default 'en'` | Ngôn ngữ nội dung gốc |
| 7 | `chunk_key` | `text not null`; `unique (doc_id, doc_version, chunk_key)` | Khóa trong một phiên bản; loader gán `parent_id` theo khóa này. Không ổn định giữa các lần build (§2) |
| 8 | `chunk_index` | `int not null`; `unique (doc_id, doc_version, chunk_index)` | Thứ tự trong tài liệu; lấy chunk lân cận |
| 9 | `chunk_role` | `text not null check in ('parent','child','standalone')` | D-008: chỉ tìm con/độc lập |
| 10 | `parent_id` | `bigint references doc_chunks_v2(id) on delete cascade`; check `chunk_role <> 'child' or parent_id is not null` | Mở rộng ngữ cảnh sang cha (sửa E-01); xóa cha thì xóa con theo |
| 11 | `chunk_type` | `text not null` | procedure, wiring, parameter, alarm…; cộng điểm theo loại (S-04) |
| 12 | `domain` | `text not null check in ('technical_docs','company_info','product_catalog')` | Lọc bắt buộc theo miền (giữ v1) |
| 13 | `scopes` | `text[] not null default '{}'`, check ⊆ installation/operation/configuration/maintenance; `technical_docs` phải có scope | Lọc theo phạm vi câu hỏi (giữ v1) |
| 14 | `product_models` | `text[] not null default '{}'`; `technical_docs` phải có model; **không** check danh sách | Lọc model; danh sách hợp lệ do loader kiểm theo registry (tránh lệch kiểu ASTRO_*, L-2) |
| 15 | `applies_to_models` | `text[] not null default '{}'` | S-06: model áp dụng cấp chunk (rỗng = theo `product_models`); dùng khi đo xong |
| 16 | `control_interface` | `text[] not null default '{}'` | Lọc theo giao tiếp điều khiển (pulse_train, ethercat) (giữ v1) |
| 17 | `spec_attributes` | `text[] not null default '{}'` | Cộng điểm theo thuộc tính (giữ v1) |
| 18 | `section_id` | `text` | Mã mục (vd. 2.6.4.19) |
| 19 | `section_path` | `text[] not null default '{}'` | Đường dẫn mục; cùng `content_hash` làm khóa so giữa các lần build |
| 20 | `section_title` | `text not null` | Tiêu đề hiển thị trong nguồn |
| 21 | `page_start`, `page_end` | `int` | Trang PDF (mở file, lấy ảnh) |
| 22 | `printed_page_start`, `printed_page_end` | `int` | Số trang in trên sách để trích dẫn cho người dùng |
| 23 | `content` | `text not null` | Nội dung gốc đưa cho LLM trả lời và hiển thị |
| 24 | `summary_vi` | `text` | Tóm tắt tiếng Việt (Bước 3); hiển thị nguồn |
| 25 | `keywords` | `text[] not null default '{}'` | Từ khóa (mã OCR, tiếng Việt) |
| 26 | `codes` | `text[] not null default '{}'`; GIN | S-02: mã chuẩn hóa, trải dải, để khớp chính xác câu hỏi theo mã |
| 27 | `embed_text` | `text not null` | Văn bản được embed và đánh FTS |
| 28 | `embedding` | `vector(1536)`; check `chunk_role = 'parent' or embedding is not null` | Vector của `text-embedding-3-small`; lá bắt buộc, cha được rỗng |
| 29 | `embedding_model` | `text`; check `embedding is null or embedding_model is not null` | S-07: biết khi nào phải embed lại |
| 30 | `token_count` | `int` | Kiểm ngân sách token |
| 31 | `content_hash` | `text not null` | Phát hiện nội dung đổi; khóa so giữa các lần build |
| 32 | `fts` | `tsvector generated always as (to_tsvector('simple', embed_text)) stored`; GIN | FTS như v1 |
| 33 | `fts_unaccent` | `tsvector generated … (to_tsvector('simple', immutable_unaccent(embed_text))) stored`; GIN | S-05, chỉ khi cài `unaccent` (§11); bỏ nếu đo không có lợi |
| 34 | `assets` | `jsonb not null default '[]'` | Ảnh (bucket, path, trang); chỗ cho mô tả ảnh/facts sau này |
| 35 | `metadata` | `jsonb not null default '{}'` | Provenance, `faq_vi`, `flags`, `param_refs`, ghi chú áp dụng T-13 |
| 36 | `source` | `text not null check in ('builder','manual')` | S-07: chunk từ luồng chunking hay viết tay |
| 37 | `review_status` | `text not null default 'draft' check in ('draft','approved')` | D-009: retriever chỉ dùng `approved` (§12) |
| 38 | `is_active` | `boolean not null default true` | Bật/tắt một phiên bản tài liệu |
| 39 | `source_run` | `text` | Run gốc (`f54/eval-k`) để truy ngược |
| 40 | `loaded_at` | `timestamptz not null default now()` | Thời điểm nạp |

Index: HNSW `embedding vector_cosine_ops`; GIN `fts`, `fts_unaccent`, `codes`, `scopes`, `product_models`,
`control_interface`; btree `(doc_id, doc_version)`, `parent_id`, `(domain) where is_active and review_status =
'approved'`.

## 11. Đo câu hỏi không dấu (S-05)

- **Khi nào:** ở Bước 4 trên DB thật (bước 5 của kế hoạch), sau khi đã áp SQL v2 và nạp F54/F86.
- **Chuẩn bị (trong SQL v2):** `create extension if not exists unaccent`; hàm `immutable_unaccent(text)` (bọc
  `unaccent` với từ điển cố định để dùng được trong cột generated); cột `fts_unaccent` + GIN; tham số
  `p_unaccent` của `match_doc_chunks_v2` (bật thì FTS dùng `fts_unaccent` và bỏ dấu câu hỏi).
- **Bộ câu hỏi:** khoảng 20 cặp cùng nội dung, một câu có dấu và một câu không dấu ("cách đấu dây báo lỗi servo
  PNP" / "cach dau day bao loi servo PNP"), nhãn `khong_dau`.
- **Chạy:** 4 tổ hợp {có dấu, không dấu} × {`p_unaccent` tắt, bật}, chế độ retrieval-only; thêm 1 lượt chỉ nhánh
  vector để biết embedding tự xử lý câu không dấu tới đâu; và 1 lượt chế độ pipeline (bước phân tích có thể đã viết
  lại câu hỏi thành có dấu).
- **Chỉ số:** recall@5, MRR theo từng tổ hợp; số câu **có dấu bị tụt hạng** khi bật (bỏ dấu làm trùng từ khác nghĩa:
  "đầu/dầu", "cài/cái" → "dau", "cai").
- **Quyết:** dùng nếu câu không dấu tăng rõ và câu có dấu không giảm; ngược lại bỏ cột `fts_unaccent` và extension
  không dùng tới.

## 12. Quy tắc `review_status = approved`

- Một chunk là `approved` khi: (1) tài liệu đạt cổng 2b và verdict nội dung của chunk là `ok`; (2) với chunk lá có
  làm giàu: phiên bản làm giàu đã duyệt ở cổng 2c. Chunk cha chỉ cần (1). Loader đọc trạng thái từ run
  (`chunk_review.json`, `enrichment_approval.json`), không đoán.
- `match_doc_chunks_v2` có tham số `p_approved_only` (mặc định `true`); retriever đọc từ Settings
  `RETRIEVAL_APPROVED_ONLY` (mặc định `true`); công cụ đánh giá truyền `false` để đo trên chunk nháp.
- Mở rộng ngữ cảnh sang cha cũng chỉ lấy cha `approved` khi bật.
- Cổng 2b đạt nghĩa là `chunk_quality.json`: `gate_passed = true` **và** `provisional = false` (Toma, 2026-11-13).
  Trạng thái tính trong adapter `doc_chunks_v2` của `doc_ingest` (nơi có dữ liệu cổng); loader chỉ kiểm, không tính.
- Hệ quả hiện tại: F54 chưa có chunk `approved` (cổng 2b tạm; cổng 2c v4 không đạt) → chỉ đo được với
  `p_approved_only = false` cho tới khi team xác nhận nhãn và cổng 2c đạt.
