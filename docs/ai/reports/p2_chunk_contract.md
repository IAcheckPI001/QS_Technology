# C2 — Contract chunk: từ `NormalizedElement` tới `doc_chunks`

Trạng thái: **đã duyệt** (2026-11-09; §1, §2 sửa theo góp ý, thêm §13). Thuộc BL-15, BL-16 (và phần làm giàu của BL-17).

Contract này quy định chunk builder (`backend/app/modules/doc_ingest/build/`) sinh ra gì, để dữ liệu khớp đúng cách luồng
tra cứu hiện tại lọc, chấm điểm và dùng chunk. Tài liệu liên quan:
- lớp chuẩn hóa: [p1_normalization_contract.md](p1_normalization_contract.md) (C1);
- bảng và hàm tra cứu: [`backend/sql/doc_chunks.sql`](../../../backend/sql/doc_chunks.sql);
- luồng chunking: [flows/doc-ingest/README.md](../flows/doc-ingest/README.md) (trạng thái: [STATE.md](../flows/doc-ingest/STATE.md), nhật ký: [LOG.md](../flows/doc-ingest/LOG.md)).

Builder chỉ sinh **bản nháp** trong thư mục chạy. Contract này không ghi DB và không đổi luồng tra cứu. Phần nạp lên
Supabase (loader staging, BL-90/BL-91) sẽ có contract riêng.

## 1. Luồng tra cứu mà chunk phải phục vụ

**Bảng `doc_chunks` hiện tại là mốc, chưa phải đích cố định.** Bảng được dựng theo chunk F86 viết tay. Luồng tra cứu
(AnalysisStage trích intent, `product_models`, `control_interface`, `spec_attributes` theo enum registry —
`chatbot/extraction/schema_builder.py`) sẽ còn mở rộng sau khi có chunk thật để kiểm thử. Vì vậy:
- `DraftChunk` (§4) là **tập dữ liệu chunk độc lập với bảng**: giữ trường lõi tương ứng cột hiện có **và** các trường ứng viên
  có kiểu rõ ràng (§13), để khi schema đổi không phải build lại hay parse lại;
- adapter `export/doc_chunks_v1.py` chuyển `DraftChunk` thành dòng đúng bảng hiện tại (trường ứng viên gói vào `metadata`);
  schema mới → thêm adapter v2;
- mọi đề xuất đổi bảng phải có bằng chứng từ đánh giá tra cứu offline (Bước 4, Bước 5 — §13).

Phần dưới mô tả luồng tra cứu hiện tại mà chunk phải khớp để làm mốc so sánh.

```
câu hỏi → AnalysisStage (LLM; standalone_query LUÔN tiếng Việt) → handlers.build_retrieval_requests
→ Retriever: embed(standalone_query, text-embedding-3-small, 1536)
→ match_doc_chunks(domain, scopes, models, control_interface, spec_attributes)
     lọc cứng → vector top 20 + FTS top 20 (to_tsvector('simple', embed_text), câu hỏi AND→OR) → RRF k=60
→ giữ vector_score ≥ 0.25 → top 6 → _expand_parents: chunk con → content + assets của CHA (≤ 5 cha)
→ product_docs_ask / chat: sources (section_path, trang, content), cắt theo token budget
```

| Vai trò khi tra cứu | Cột | Hệ quả cho builder |
|---|---|---|
| Lọc cứng | `is_active`, `domain`, `scopes`, `product_models`, `control_interface` | Sai giá trị → chunk không bao giờ được tìm |
| Chấm điểm | `embedding` (từ `embed_text`), `fts` (từ `embed_text`), `spec_attributes` (+0,005) | `embed_text` quyết định chất lượng tìm kiếm |
| Ngữ cảnh gửi LLM | `content`, `assets` của **cha** nếu có `parent_id` | Cha phải chứa trọn văn bản và ảnh của con |
| Trích dẫn | `doc_id`, `section_title`, `section_path`, `page_start` | Phải đúng trang PDF và đường dẫn mục |
| Không dùng khi tra cứu | `chunk_type`, `doc_type`, `lang`, `section_id`, `keywords`, `summary_vi`, `token_count`, `content_hash`, `metadata` | `keywords` và `summary_vi` chỉ có tác dụng **qua `embed_text`** |

Ràng buộc của bảng phải giữ:
- `domain = technical_docs` thì `scopes` không rỗng và `product_models` không rỗng;
- `scopes ⊆ {installation, operation, configuration, maintenance}`;
- `product_models ⊆` registry (`F54`, `F86`, `F86E`, `F10T`, …);
- `section_title`, `content`, `embed_text`, `content_hash` không rỗng;
- `embedding vector(1536)` NOT NULL (chỉ tính khi đánh giá hoặc xuất bản);
- `unique(doc_id, chunk_index)`.

Lỗi đã ghi nhận (E-05, chưa sửa, ngoài phạm vi): nhánh FTS của `match_doc_chunks` dùng `p_models is null`, còn nhánh
vector dùng `cardinality(p_models) = 0`. Khi model là mảng rỗng, nhánh FTS không trả dòng nào.

## 2. Đầu vào, đầu ra

`build` là **giai đoạn thứ hai** của `doc_ingest`, tách khỏi giai đoạn trích xuất:

```
Giai đoạn 1 — trích xuất (đã có; chậm vì Docling/OCR)
  PDF → normalized/elements.jsonl, tables.jsonl, review_queue.jsonl, normalized/images/, run_report.json
Giai đoạn 2 — build chunk (mới; nhanh, chạy lại nhiều lần khi chỉnh luật chunk)
  đọc output giai đoạn 1 + manifest (§3) → chia cha/con, dựng content/keywords/embed_text → kiểm chất lượng
```

Đầu vào: thư mục chạy đã chuẩn hóa `data/ingest_runs/{doc}/{run_id}/` + manifest. Không parse lại PDF.

Đầu ra (bản nháp, không ghi DB):

| File | Ai tạo | Để làm gì |
|---|---|---|
| `build/chunks.jsonl` | `build` (Bước 2) | Sản phẩm chính: mỗi dòng một `DraftChunk` (§4). Loader sau này đọc file này (qua adapter) để nạp DB |
| `build/chunk_quality.json` | `build` (Bước 2b) | Kết quả kiểm tự động (CQ, độ phủ, ranh giới, so với CSV F86) → quyết định đạt cổng (§10) |
| `report/chunks.html` | `build` | Trang duyệt tay: mỗi chunk một thẻ (nội dung, ảnh, cha/con, cờ) |
| `build/chunk_review.json` | người duyệt | Nhận xét từng chunk (`ok`/`fix` + ghi chú) |
| `build/enrichment.jsonl` | `enrich` (Bước 3, LLM) | Tóm tắt/câu hỏi/từ khóa tiếng Việt theo `content_hash`; tách file để build lại không mất và không trả tiền LLM lại (§8) |

| `build/doc_chunks_v1.jsonl` | `build` | Cùng chunk qua adapter bảng hiện tại: dạng dòng sẽ nạp (để xem, không nạp) |
| `build/figure_ocr.jsonl` | `figure-ocr` (tùy chọn, `.venv-ingest`) | Nhãn OCR trên ảnh crop của hình ở trang có text layer (§8.1); `build` đọc nếu có |

Lệnh:
- `cli build --run-dir <run> [--labels {doc}.chunks.json] [--compare-csv <csv>]`: chạy trên run có sẵn (venv nào cũng
  được; đếm token chỉ có ở venv chính vì cần tiktoken);
- `cli build … --carry-review <run cũ>/build/chunk_review.json --carry-chunks <run cũ>/build/chunks.jsonl` (2026-11-11):
  khi tạo `chunk_review.json` mới, chép `verdict/note/reviewer` của chunk cũ khớp (`content_hash`, `section_path`)
  — không khớp theo `chunk_key` vì key đánh số theo thứ tự và dịch khi số chunk đổi. Chunk mới/đã đổi → `pending`; mục cũ
  `pending` hoặc stale không được chép; file review đã có thì không ghi đè;
- `cli run`: gọi `build` ở cuối khi tìm được manifest (`--no-build` để bỏ);
- `cli figure-ocr --run-dir <run> [--limit N]`: OCR nhãn trong hình, chạy tiếp được khi bị dừng; chạy lại `build`.
- `cli enrich --run-dir <run> [--sample N | --limit N] [--dry-run] [--model M]` (2026-11-13, Bước 3, venv chính): làm
  giàu tiếng Việt cho chunk **lá** chưa có bản ghi (cùng `content_hash` + `prompt_version`; chunk trùng nội dung dùng
  chung một bản ghi) → `build/enrichment.jsonl` (append-only, chạy tiếp được). Từ chối khi `chunk_quality.json` không
  đạt cổng 2b (đạt "tạm" được chạy). `--dry-run` chỉ ước tính token/chi phí. Key/model đọc từ env `OPENAI_API_KEY`,
  `OPENAI_MODEL` (rơi về `backend/.env`); `doc_ingest` không import `app.core.config`. Chạy lại `build` để dùng.

## 3. Manifest tài liệu

File `backend/app/modules/doc_ingest/manifests/{doc}.yaml`, schema `DocManifest` (`extra="forbid"`):

| Trường | Ví dụ F54 | Ý nghĩa |
|---|---|---|
| `doc_id` | `f54_operation_v02` | Theo quy ước CSV hiện có: `{model}_{loại}_{phiên bản}` |
| `doc_type` | `user_guide` | `user_guide`, `installation_manual` (giữ từ vựng CSV F86) |
| `doc_title` | `Operation Manual (English Version)` | Dùng trong `embed_text`, `metadata` |
| `doc_version` | `V.02` | Từ tên file. Footer F54 ghi `V.01`: người duyệt xác nhận (`doc_version_mismatch` ở BL-90) |
| `product_models` | `[F54]` | Bắt buộc, ⊆ registry |
| `lang` | `en` | Ngôn ngữ của `content` |
| `default_scopes` | `[operation]` | Scope khi không có luật nào khớp |
| `scope_rules` | `[{match: "(?i)wiring\|connection\|install", scopes: [installation]}, …]` | Regex trên `section_path`, luật đầu tiên khớp thắng |
| `storage_bucket` | `f54-docs` | Bucket ảnh khi xuất bản |
| `exclude_pages`, `exclude_sections`, `exclude_reason` | `[1, 2]`, `[]`, "bìa và lời cảm ơn…" | (2026-11-13, duyệt: Toma) Trang (`pdf_page_index`) / mục (tiền tố tiêu đề một cấp của `section_path`) không có nội dung kỹ thuật → phần tử không vào chunk, độ phủ đếm lý do `manifest_excluded` |

Manifest của đợt này: `f54.yaml`, `f86_installation.yaml` (`f86_installation_2024-04-25`), `f86_operation.yaml`
(`f86_user_guide_2024-09-14`, chỉ làm bản nháp so sánh).

## 4. `DraftChunk` — map từng cột

`DraftChunk` = các trường lõi tương ứng cột `doc_chunks` (trừ `id`, `embedding`, `fts`) + `chunk_key`, `parent_key` + các
trường ứng viên có kiểu (§13). Adapter `export/doc_chunks_v1.py` ra dòng đúng bảng hiện tại: trường ứng viên vào `metadata`
(§9); khi nạp, loader đổi `parent_key` → `parent_id`.

| Cột | Nguồn | Quy tắc |
|---|---|---|
| `chunk_key` | builder | `{doc_id}:B{chunk_index:04d}` (B = builder, phân biệt chunk viết tay `I-04`) |
| `parent_key` | builder | `chunk_key` của cửa sổ cha, hoặc `null` (§5) |
| `domain` | cố định | `technical_docs` |
| `scopes` | manifest + luật | `scope_rules` theo `section_path` → nếu không khớp thì `default_scopes`. Ghi đè theo loại: `parameter` → thêm `configuration`; `alarm` → thêm `maintenance`. **I-46 (2026-11-13, thử nghiệm sau checkpoint CP-I46, chờ chốt bằng đo):** cộng thêm scope theo nội dung — luật `chunking.scope_content_rules` của profile (regex tiêu đề các cấp từ `scope_title_min_level` = 2 trở xuống + label, regex nội dung, loại chunk); **chỉ thêm, không bớt**; một chunk mang nhiều scope khi đúng |
| `product_models` | manifest | Cả tài liệu. Ghi chú áp dụng (T-13) giữ nguyên văn trong `content`, không lọc |
| `control_interface` | registry snapshot | Khớp từ/nhãn (`pulse_train`: "Pulse Train", "xung"; `ethercat`; `mechatrolink`) trong `content` + `section_path`; không khớp → `[]` (= áp dụng chung) |
| `spec_attributes` | registry snapshot | Khớp nhãn (`dimension`, `io`, `ports`, `spindle`, `max_axis`, …) trong tiêu đề mục/caption; dùng để cộng điểm, không lọc |
| `chunk_type` | builder | §6 |
| `is_active` | cố định | `true` (bản nháp; chỉ có hiệu lực khi xuất bản) |
| `doc_id`, `doc_type`, `lang` | manifest | — |
| `section_id` | T-07 | Số của heading đánh số cuối trong `section_path` (`2.3.2.4`); không có → `null` |
| `section_path` | T-07 | Nguyên văn `NormalizedElement.section_path` |
| `section_title` | T-07 + label heading | Heading cuối; với con thêm ` › {label heading}` (vd. `2.3.2.4 Homing switch wiring diagram › Parameter status description`). Không có heading → `doc_title` |
| `page_start`, `page_end` | `pdf_page_index` | Trang PDF nhỏ nhất/lớn nhất của các phần tử. Trang in để trong `metadata` |
| `chunk_index` | builder | Theo thứ tự đọc; cha đứng ngay trước các con |
| `assets` | T-14 | §7 |
| `metadata` | builder | §9 |
| `content` | phần tử | §6; nguyên văn, ≤ 2.500 ký tự |
| `summary_vi` | LLM (Bước 3) | `null` cho tới khi làm giàu |
| `keywords` | deterministic + LLM | §8 |
| `embed_text` | builder | §8 |
| `token_count` | tiktoken `cl100k_base` | Đếm trên `embed_text` |
| `content_hash` | builder | `sha256(content)` (hex) |

## 5. Cha–con

- **Cha = cửa sổ ngữ cảnh.** Gồm các phần tử liên tiếp **trong cùng một mục** (`section_path` giống nhau), ≤ 2.500 ký tự.
  Cha không dùng để khớp khi tra cứu, chỉ để mở rộng ngữ cảnh khi một con khớp (D-008, 2026-11-13).
  `content` của cha = nối nguyên văn các con theo thứ tự đọc, cộng phần nối (heading, đoạn ngắn không thuộc con nào).
  `assets` của cha = hợp `assets` của các con. `chunk_type = section`.
- **Con = đơn vị khớp.** Một thủ tục, một nhóm parameter, một hình, một nhóm đoạn văn (§6).
- **Một cấp.** Không có cháu. Phân cấp mục nằm ở `section_path`.
- Mục dài hơn 2.500 ký tự → nhiều cửa sổ cha liên tiếp. Một con không bao giờ bị cắt qua hai cha.
- Cửa sổ chỉ có **một** con → không tạo cha; con đứng độc lập (`parent_key = null`).
- Chunk bảng là chunk độc lập (§6).
- Bất biến: `content` của con là chuỗi con của `content` cha; `assets` con ⊆ `assets` cha; `parent_key` resolve được,
  không chu trình.

## 6. Loại chunk và cách dựng `content`

Phần tử **không** vào chunk:
- furniture, `figure_text` (chỉ vào `keywords`), `toc`;
- `watermark_candidate`, `duplicate_image`;
- `unsupported` (đã có review chặn chunk).

| `chunk_type` | Đơn vị | `content` |
|---|---|---|
| `procedure` | Label heading kiểu "How to…", "Step 1:", "Stage 1:", "Bước 1:" + các bước tới phần tử không phải bước | **Nguyên khối**, không tách từng bước. Dài hơn 2.500 ký tự → tách ở ranh giới bước; mỗi phần lặp tiêu đề kèm `(phần i/n, bước a–b)`. Ảnh của bước gắn vào phần chứa bước |
| `parameter` | Định nghĩa mã (T-12 `definition`) + các con T-08 (`value_option`); định nghĩa liên tiếp cùng khối được gộp tới ~1.200 ký tự | Label heading + list lồng (§6.1) |
| `alarm` | Ghi chú xử lý lỗi sau thủ tục ("Note: At Stage…", "The cause is…") hoặc mục alarm | Nguyên văn; `metadata.related_chunk_keys` trỏ về thủ tục (CQ-04) |
| `table` | Nhóm dòng của bảng logic (T-01…T-05, T-15) | Header + dòng dạng markdown, ≤ 2.500 ký tự **và** `embed_text` của phần ≤ `embed_max_tokens` − `embed_enrich_reserve` (800 − 150, chừa chỗ cho tóm tắt và câu hỏi của Bước 3; I-38, 2026-11-11), chia ở ranh giới dòng, lặp header ở mọi phần (CQ-01…CQ-03, CQ-11); cụm T-13 nguyên văn. Bảng parameter → `chunk_type = parameter` |
| `figure` / `wiring` / `pinout` / `dimension` | Picture/screenshot (không phải trùng, không phải watermark) | Caption nguyên văn + câu dẫn hoặc ghi chú liền kề trong cùng mục (≤ ~600 ký tự). Chữ trong hình không vào `content` |
| `overview`, `spec` | Đoạn văn | Đoạn liên tiếp cùng mục gộp tới ~1.200 ký tự. Khối dài hơn 2.500 ký tự có đầu phần (`block_part_patterns`: "Case n", "Example n", "Ví dụ n", "Trường hợp n") → chia ở đầu phần (R-12) |
| `section` | Cửa sổ cha (§5) | Nối nguyên văn các con |

- Loại ngữ nghĩa (`wiring`, `pinout`, `dimension`, `spec`, `alarm`) theo luật từ khóa trên tiêu đề mục/caption trong profile
  (`chunk_type_rules`). Không khớp thì dùng loại cấu trúc (`figure`, `overview`).
- Caption **không** bắt đầu bằng từ khóa caption (vd. Docling gắn `caption` cho "Stage 3…", "Stage 9:" ở F54 trang 89–90)
  được coi là nhãn bước hoặc văn bản, không phải chú thích hình.

### 6.1 Render nội dung
- `text` của phần tử giữ **nguyên văn** (gồm glyph `o`, lỗi chính tả gốc như `stauts`, `(NC` thiếu `)`). Ngoại lệ khi
  render (I-39, 2026-11-12): ký tự vùng Private Use (U+E000–U+F8FF, vd. ``) đầu dòng là bullet của font PDF →
  render thành `- `; `text` của phần tử không đổi.
- List: mỗi mục một dòng; cấp 1 bắt đầu bằng `- `, cấp sâu hơn thụt 4 khoảng trắng mỗi cấp (theo `list_info.depth`).
- Heading và label heading đứng riêng một dòng.
- Bảng: `| h1 | h2 |` + `|---|---|` + dòng; ô có xuống dòng nối bằng khoảng trắng.
- Không thêm câu tự viết vào `content`. Ngoại lệ: dòng tiêu đề lặp `(phần i/n …)` của thủ tục/bảng/khối bị tách, và
  phần dẫn chung của khối bị tách theo R-12 (lặp nguyên văn).

## 7. `assets`

```json
{"bucket": "<manifest.storage_bucket>", "path": "<doc_id>/<element_id với : → _>.png",
 "page": <pdf_page_index>, "printed_page": <trang in hoặc null>}
```

- Lấy từ `image.original_path` (T-14). Chỉ upload khi xuất bản.
- Hình không có ảnh render (chạy không kèm PDF) → chunk vẫn sinh, cờ `asset_missing`.
- Khung chữ (T-20 `text_frame`) **không** là asset (2026-11-13, I-44): ảnh chỉ lặp lại chữ đã tách vào `content`; khối
  chỉ có khung chữ cũng không thành chunk hình.
- Theo schema `ChunkAsset` của chatbot (`extra="ignore"`). `printed_page` là số nguyên; trang in không phải số → `null`.

## 8. `keywords` và `embed_text`

**`keywords`**, theo thứ tự và bỏ trùng:
1. Deterministic:
   - mã T-12 trong chunk (nguyên văn label: `M1920`, `#4140 - #4147`);
   - token khớp `code_patterns` (`X40`, `CN3`);
   - model của manifest;
   - `section_id`;
   - nhãn hình đã lọc (§8.1).
2. Thuật ngữ tiếng Anh từ tiêu đề mục/caption.
3. Từ khóa tiếng Việt do LLM sinh (Bước 3).

**`embed_text`**, cùng mẫu với chunk F86 viết tay:

```
{models} · {doc_title} · {section_path nối bằng " › "}
Tóm tắt: {summary_vi}                       ← bỏ dòng khi chưa làm giàu
Câu hỏi thường gặp:                          ← bỏ khối khi chưa làm giàu
- {faq_vi 1}
- {faq_vi 2}
Từ khóa: {keywords nối ", "}
---
{content}
```

- ≤ 800 token (tiktoken). Vượt thì chỉ cắt phần content **trong `embed_text`** ở ranh giới câu; `content` giữ đủ.
- Ngưỡng 800 là ngưỡng tự đặt của contract (model `text-embedding-3-small` nhận 8.191 token); kích thước tối ưu cho
  điểm khớp đo ở Bước 4. Chunk **lá** nên ≤ 800 − `embed_enrich_reserve` (150, chỗ cho Bước 3): vượt → cờ
  `embed_over_budget` (CQ-12). Chunk **cha** không được embed/tìm (D-008, 2026-11-13): `embed_text` của cha vẫn dựng
  cho schema/export nhưng không gắn `embed_truncated`/`embed_over_budget`; loader không embed cha.
- Chunk cha **không** làm giàu, **không** embed (D-008, làm rõ 2026-11-13): `summary_vi`, `faq_vi` để trống,
  `enrichment_status = none`; `embed_text` của cha chỉ giữ cho schema/export. Cha chỉ được đọc `content` theo
  `parent_id` để trả ngữ cảnh khi một con khớp; nội dung cha = nối nguyên văn các con nên không mất gì khi chỉ tìm
  trên chunk lá.

**Làm giàu (Bước 3, 2026-11-13).** LLM trả JSON `summary_vi` (1–2 câu, ≤ 220 ký tự), `faq_vi` (2–3 câu hỏi, ≤ 90 ký
tự, kết thúc "?"), `keywords_vi` (≤ 6); prompt trong `enrich/prompt.py` (`PROMPT_VERSION`). Kiểm tự động: tóm tắt rỗng
hoặc sai số câu hỏi → không ghi; mã kỹ thuật trong tóm tắt/câu hỏi không có trong `content` + model + section path →
cờ `enrich_code_mismatch`. `build` ghép làm giàu vào `embed_text` chunk lá, `enrichment_status = draft`; từ khóa VI
luôn giữ (trừ chỗ vào `max_keywords`). Làm giàu **không bao giờ đẩy `content` ra khỏi `embed_text`**: vượt
`embed_max_tokens` thì bớt câu hỏi cuối, rồi từ khóa VI, rồi tóm tắt, cờ `enrich_trimmed`. Chunk lá đã làm giàu
dùng giới hạn 800 (phần dự trữ 150 đã dùng) cho `embed_over_budget`.
Bảng thuật ngữ (`profile.glossary`, qs_controller; bổ sung dần): mỗi dòng `en` → `vi` (cách người dùng QS gọi; `vi`
rỗng = giữ tiếng Anh, không tự dịch) được chèn vào prompt. `prompt_version` của bản ghi = phiên bản prompt + dấu bảng
thuật ngữ (vd. `v2+ga40bffb5`): sửa prompt hoặc bảng → `cli enrich` làm lại các chunk (bản ghi cũ vẫn dùng tới khi có
bản mới; `--only-enriched` chỉ làm lại chunk đã có bản ghi). Trước khi ghi: bỏ từ khóa VI chứa mã kỹ thuật; tóm tắt
mở bằng "Đoạn này…" → cờ kiểm `summary_preamble` (không chặn).

**Ngôn ngữ.** `content` giữ ngôn ngữ gốc của tài liệu (không dịch). Lớp tìm kiếm thống nhất bằng tiếng Việt (khớp
`standalone_query`): mọi chunk **lá** (con, độc lập), kể cả tài liệu tiếng Việt, có `summary_vi`, câu hỏi thường gặp
và từ khóa tiếng Việt trong `embed_text` (chunk cha không, D-008). Câu trả lời do LLM viết theo ngôn ngữ người dùng. Tài liệu tiếng Việt dạng scan chỉ được chunk sau
khi sửa I-29 (OCR mất dấu).

### 8.1 Nhãn trong hình
- Nguồn: `figure_text` (text layer hoặc OCR) và OCR bổ sung trên vùng crop cho trang có text layer (RapidOCR có sẵn).
  Lý do: chữ nằm trong bitmap không có trong text layer (F54 trang 9: 0 nhãn).
- Lọc giữ: mã theo `code_patterns`, tên cổng/chân (chữ in hoa + số, ký hiệu như `FG`, `D+`), giá trị có đơn vị
  (`320 mm`, `24V`, `AC-220V`), nhãn T-18. Bỏ mảnh 1 ký tự, ký hiệu rời, chuỗi không có chữ hay số.
- Chỉ vào `keywords` và `metadata.figure_labels` (kèm bbox và nguồn), **không** vào `content`.
- Nhãn OCR crop (`source = crop_ocr`) chỉ vào `keywords`/`embed_text` khi khớp toàn chuỗi một mẫu
  `figure_label_trusted_patterns` của profile (qs_controller: chân PUL/DIR/EDM, X/Y, A/B/Z±, AI/AO, G/M-code, GND/PE/FG,
  điện áp) hoặc mọi token của nó có trong từ vựng text layer của tài liệu (chữ trang không OCR, ô bảng). Nhãn khác giữ
  trong `figure_labels` với `verified = false` (2026-11-12, I-40b, duyệt: Toma). Lý do: điểm tin cậy RapidOCR không
  phân biệt được nhãn sai (F54 B0045: `FUL2-` 0,991, `QFF54` 0,986).
- Nhãn nguồn OCR (`ocr`, `crop_ocr`) chỉ vào `keywords`/`embed_text` của chunk có loại trong
  `chunking.figure_label_keyword_types` (mặc định `wiring`, `pinout`, `dimension`); loại khác (ảnh tổng quan, ảnh màn
  hình trong thủ tục…) giữ nhãn trong `figure_labels` (2026-11-13, duyệt: Toma). Lý do: F54 B0002 (ảnh mặt trước/sau)
  mang 34 mã chân làm vector lệch và tranh suất top-k với chunk đấu dây thật. Nhãn `text_layer` không đổi. Đo lại ở
  Bước 4.
- Số đo và sơ đồ chân dùng để trả lời phải lấy từ văn bản/bảng có thật, hoặc fact `spec` `human_verified_figure` do người
  duyệt chép từ bản vẽ (V1.1, sau duyệt thêm khối "Thông số đã duyệt" vào `content`). Không lấy từ OCR, không lấy từ
  vision LLM.

## 9. `metadata`

| Khóa | Ý nghĩa |
|---|---|
| `chunk_key`, `parent_key` | §4, §5 |
| `doc_title`, `doc_version` | Từ manifest |
| `element_ids` | Phần tử nguồn theo thứ tự đọc (CQ-05) |
| `printed_page_start`, `printed_page_end` | Trang in (T-06), có thể `null` |
| `extraction` | `text_layer` \| `ocr` \| `mixed` (theo S0 của các trang) |
| `logical_table_id`, `row_ids` | Chunk bảng |
| `param_codes` | Mã T-12 (prefix + codes) |
| `applicability_notes` | Cụm T-13 nguyên văn |
| `figure_labels` | Nhãn hình đã lọc + bbox + nguồn |
| `related_chunk_keys` | `alarm` ↔ `procedure` (CQ-04) |
| `review_blockers` | Mã review chặn chunk của phần tử nguồn (vd. `caption_ambiguous`). Không rỗng → không được xuất bản |
| `review_notes` | Mã review chặn fact (thông tin cho người duyệt) |
| `enrichment` | `{status: none\|draft\|approved, model, created_at}` |
| Trường ứng viên §13 | `chunk_role`, `source`, `io_codes`, `applies_to_models`, … do adapter v1 gói vào đây |

## 10. Kiểm chất lượng (Bước 2b) và cổng

| Kiểm | Điều kiện |
|---|---|
| CQ-01…CQ-08 | Theo [p1_golden_tests.md](p1_golden_tests.md) §4 |
| CQ-09 (mới) | `content` con ⊂ `content` cha; `assets` con ⊆ `assets` cha |
| CQ-10 (mới) | Không cắt giữa bước, giữa dòng bảng, giữa định nghĩa parameter và các giá trị của nó; hình có caption + asset |
| CQ-11 (2026-11-11, I-38) | Chunk bảng nằm trọn trong `embed_text`: chunk bảng nhiều dòng có cờ `embed_truncated` là không đạt. Phần chỉ có một dòng mà vẫn vượt giới hạn chỉ ghi chú (không cắt trong dòng). Chỉ đáng tin khi build có tiktoken; không có thì kết quả cổng là tạm |
| CQ-12 (2026-11-13, I-43, D-008) | Chunk lá nằm trong ngân sách `embed_text` (800 − 150): lá vượt mang cờ `embed_over_budget`; phần bảng nhiều dòng vượt là không đạt (luật chia bảng I-38 bảo đảm), lá khác vượt (khối nguyên vẹn, phần bảng một dòng) chỉ ghi chú. Chunk cha không tính. Cần tiktoken như CQ-11 |
| Độ phủ | Mọi phần tử cần chunk nằm trong **đúng một** chunk con hoặc chunk độc lập; 100% ký tự giữ lại; 0 lặp ngoài cha–con |
| Ranh giới | So với `expected_chunks` trong nhãn mẫu: precision/recall ≥ 0,9, đúng `chunk_type` |
| So với F86 viết tay | Báo cáo (không làm cổng): chunk viết tay không được phủ, chunk builder không khớp |
| Duyệt tay | `build/chunk_review.json` không còn `fix` mở |

Chưa đạt cổng thì không chạy làm giàu LLM (Bước 3). Đạt "tạm" (nhãn `verified: false`) được chạy (quyết định Toma
2026-11-13; kết quả khóa theo `content_hash` nên chunk đổi sau khi sửa nhãn chỉ phải làm lại phần đổi).

**Cổng 2c — làm giàu (`chunk_quality.json` → `enrichment`, 2026-11-13):**
- Tự động (CQ-13, `auto_passed`): mọi chunk lá `enrichment_status ≠ none`; 0 `enrich_code_mismatch`; 0 chunk lá có làm
  giàu mà `content` bị cắt khỏi `embed_text`.
- Mẫu duyệt tay: `cli enrich-sample --size 30` chọn mọi chunk có cờ kiểm làm giàu + phân tầng theo loại (bỏ chunk thí
  điểm), đánh dấu `enrichment_verdict = pending` trong `chunk_review.json` (lọc cờ `mau_2c` trên `report/chunks.html`).
  Mỗi chunk kiểm 5 điểm: đúng sự thật (sai → `enrichment_severe`), câu hỏi trả lời được từ content, thuật ngữ đúng cách
  gọi ở QS, từ khóa sát chủ đề, tóm tắt đúng trọng tâm. Verdict gắn `enrichment_version`; làm giàu đổi phiên bản →
  verdict hết hạn.
- Đạt: tự động đạt, 0 mẫu chờ, 0 lỗi nặng, ≥ 90% mẫu `ok`. `cli enrich-approve --reviewer …` ghi
  `build/enrichment_approval.json` (một phiên bản cho mọi lá) → build: lá có bản ghi cùng phiên bản mang `approved`.
- Khóa làm giàu = (`content_hash`, `section_path`): cùng nội dung ở mục khác nhau làm giàu riêng (F54: thủ tục
  "vào màn hình PARAMETER, đặt giá trị" lặp ở 13 mục tham số từng dùng chung tóm tắt của mục "JOG RAPID (G00)").

## 11. Ví dụ — F54 mục 2.3.2.4 "Homing switch wiring diagram" (trang PDF 18–19, ~1.800 ký tự)

| chunk_key | Loại | Cha | Nội dung | Assets |
|---|---|---|---|---|
| `f54_operation_v02:B0101` | `section` | — | Toàn văn mục | Figure 14, Figure 15 |
| `…:B0102` | `wiring` | B0101 | "Homing switch wiring diagram for NPN, PNP signal" + caption Figure 14 | Figure 14 |
| `…:B0103` | `procedure` | B0101 | "Note: After connecting the homing sensor…" + Step 1–3 + caption Figure 15 | Figure 15 |
| `…:B0104` | `procedure` | B0101 | "How to configure the parameter from 0 to 1:" + 5 bước | — |
| `…:B0105` | `parameter` | B0101 | "Parameter stauts description:" + M1920–M1923 kèm giá trị 0/1 | — |

`content` của B0105:

```
Parameter stauts description:
- M1920: Homing sensor status configuration parameter for X axis
    o M1920 = 0 : Normally closed sensor (NC)
    o M1920 = 1 : Normally open sensor (NO)
- M1921: Homing sensor status configuration parameter for Y axis
    o M1921 = 0 : Normally closed sensor (NC
    o M1921 = 1 : Normally open sensor (NO)
… (M1922, M1923)
```

Các cột khác của B0105:
- `scopes = [operation, configuration]`, `product_models = [F54]`, `section_id = 2.3.2.4`;
- `page_start = page_end = 19`, `printed_page_start = 12`;
- `keywords = [M1920, M1921, M1922, M1923, F54, 2.3.2.4, …]`;
- `metadata.param_codes = [M1920, M1921, M1922, M1923]`.

Chunk thủ tục dài, F54 M100 Stage 1–10 (trang 88–90, ≈ 1.500 ký tự):
- 1 `procedure` độc lập;
- 1 `alarm` độc lập ("Note: At Stage (4,5)…", ≈ 2.400 ký tự), `related_chunk_keys` trỏ lẫn nhau;
- mục ≈ 3.900 ký tự nên không có cửa sổ cha chung.

## 12. Ngoài phạm vi C2
- Nạp lên Supabase, version tài liệu, thay chunk F86 viết tay (BL-90, BL-91; sẽ hỏi lại).
- Sửa `match_doc_chunks` (E-05).
- Vision LLM cho hình.
- Trích fact (BL-17 phần fact).
- Tài liệu scan tiếng Việt (chờ I-28, I-29, I-30).
- Đổi schema `doc_chunks`, mở rộng AnalysisStage (§13: chỉ đề xuất kèm bằng chứng; migration là thay đổi riêng ở module
  chatbot).

## 13. Ứng viên mở rộng schema (chờ đánh giá)

Trường ứng viên trong `DraftChunk` (có kiểu, không phải dict tự do): `chunk_role` (`parent` | `child` | `standalone`),
`source` (`builder` | `manual`), `doc_version`, `extraction`, `printed_page_start/end`, `param_codes`, `io_codes`,
`applicability_notes`, `applies_to_models`, `figure_labels`, `related_chunk_keys`, `review_blockers`.

Khoảng trống của bảng hiện tại (đọc `backend/sql/doc_chunks.sql` và registry, 2026-11-09):

| # | Khoảng trống | Hệ quả | Ứng viên | Đo ở Bước 4 |
|---|---|---|---|---|
| S-01 | Không có phiên bản tài liệu; khóa `unique(doc_id, chunk_index)`; `parent_id` là id tự tăng | Không thay được bộ chunk của một tài liệu một cách nguyên tử; loader phải tự đổi key → id | `doc_version`, `chunk_key` unique, bảng (hoặc cột) quản lý bản đang active | — (vận hành) |
| S-02 | Mã kỹ thuật (`#4140`, `M1920`, `CN3`) chỉ có trong `embed_text`; parser `simple` tách `#4140` thành `4140` | Câu hỏi theo mã chỉ dựa vào FTS xấp xỉ | Cột `codes text[]` + GIN, khớp chính xác; phía Analysis cần entity `codes` | biến thể khớp mã |
| S-03 | Chunk cha cũng được embed và tìm trực tiếp | Cha và con cùng chiếm chỗ top 6 | `chunk_role`; chỉ tìm con/độc lập, cha chỉ để mở rộng — **đã quyết D-008 (2026-11-13)**, phía SQL/retriever chưa làm | biến thể không tìm cha (xác nhận D-008) |
| S-04 | `chunk_type` không dùng khi tra cứu | Câu hỏi "thông số", "đấu dây", "lỗi" không được ưu tiên đúng loại | Boost theo intent → `chunk_type` (giống `spec_boost`) | biến thể boost loại |
| S-05 | FTS `simple` không bỏ dấu | Câu hỏi không dấu không khớp phần tiếng Việt | `unaccent` trong cột `fts` và câu hỏi | biến thể bỏ dấu |
| S-06 | `product_models` cấp tài liệu; ghi chú áp dụng (T-13) chỉ nằm trong `content` | Chunk sai model vẫn qua lọc | `applies_to_models` cấp chunk | đếm chunk có ghi chú |
| S-07 | Không có `source`, trạng thái duyệt, model embedding | Lẫn chunk tay và chunk builder; không biết khi nào cần embed lại | `source`, `review_status`, `embedding_model` | — (vận hành) |

Kết quả và đề xuất cuối nằm ở `p2_doc_chunks_schema_review.md` (Bước 5, sau đánh giá tra cứu offline).

## 14. Ghi chú triển khai v1 (BL-16, 2026-11-09)

Quy tắc được làm rõ khi chạy trên F54 và F86 Installation (không đổi ý của các mục trên):

| # | Quy tắc | Lý do |
|---|---|---|
| R-01 | Đơn vị = khối `label_heading` liên tiếp trong cùng mục; bảng là khối riêng | `label_heading` T-07 đã đánh dấu đúng các khối "Note:", "How to…", "Parameter … description:" |
| R-02 | Chuỗi ≥ 2 khối có label heading dạng bước ("Stage 1:", "Stage 2:" …) gộp thành **một** thủ tục, kèm khối dẫn ngắn ngay trước (vd. "Automatic tool setting process (M100)" + hình). Khối không có nhãn bước nhưng tự nó là thủ tục và có dòng bước (bước đầu là text thường) đứng ngay trước ≥ 1 khối bước → cùng một thủ tục (2026-11-11). Khi phân loại khối, label heading dạng bước cũng được đếm là một bước: khối nhãn "Step 1:" có thêm dòng "Step 2: …" viết liền trong text là `procedure` (2026-11-11, I-35). Chuỗi khối bước đánh số lại (Step 1 sau Step k) → thủ tục mới; câu dẫn ngắn (text, ≤ `procedure_lead_max` = 160) cuối khối bước trước, cùng hình/caption ngay trước nó nằm cùng trang câu dẫn nhưng khác trang mở khối bước trước, thuộc thủ tục mới; khối hình/tổng quan ngắn kết thúc bằng câu dẫn ngắn ngay trước chuỗi bước gộp vào thủ tục đầu (2026-11-12, I-42) | F54 trang 88–90: mỗi Stage là một label heading riêng. F54 3.9.2, 4.11.2: "Step 1:" ở trang đầu là `text`, thủ tục từng tách tại Step 3 |
| R-03 | Một khối liền mạch (vd. ghi chú xử lý lỗi) giữ nguyên tới `parent_max`; `child_soft_max` chỉ dùng để **gộp** đơn vị ngắn và tách nhóm parameter | Không cắt một ghi chú/thủ tục chỉ vì vượt 1.200 ký tự |
| R-04 | Khối chỉ có heading/label heading gộp vào khối sau (trước bảng: thành dòng dẫn của bảng); mục chỉ có heading không sinh chunk (`heading_only`, không tính bỏ sót). Thêm 2026-11-11 (I-37): (a) khối ngay trước bảng gồm heading/label heading + **một** dòng `text` kết thúc bằng ":" và ≤ `table_lead_max` (80) ký tự ("1.1 Overview / Specification:") → dòng dẫn của bảng; (b) khối chỉ có heading/label heading và hình **không caption** → gộp vào khối sau cùng mục (tiêu đề thành dòng đầu, ảnh vào `assets`), hết khối thì vào khối trước; đứng ngay trước bảng, hoặc là nội dung duy nhất của mục (F86 "2.2 INPUT LOW DIAGRAM", I-33), thì giữ là chunk hình | Heading nằm trong `section_path` của con. F54 PART 3–4: heading + ảnh "Description images" từng thành chunk hình chỉ có tiêu đề mục (21 chunk) |
| R-05 | Tiêu đề lặp `(phần i/n, bước a–b)` chỉ thêm ở phần 2…n của thủ tục bị tách; phần bảng 2…n lặp caption/dòng dẫn kèm `(phần i/n)` và header. Chia phần bảng (2026-11-11, I-38): chi phí một dòng = token của dòng + token các mã của dòng trong "Từ khóa:"; số phần là ít nhất có thể trong ngân sách, rồi chi phí được cân giữa các phần (không còn phần đuôi một dòng). Dòng nhóm (bảng nhiều cột, dòng chỉ một ô có chữ, không mang mã parameter) đi cùng dòng ngay sau nó; nhóm bị chia qua hai phần thì phần sau lặp lại dòng nhóm ngay dưới header (dòng lặp không tính vào `row_ids`) | Phần 1 đã có tiêu đề gốc. F54 bảng 5.1: 33–36 dòng mỗi phần, `embed_text` 1.261–1.291 token, chỉ 17–18 dòng đầu vào embedding; phần 3/3 chỉ có 1 dòng |
| R-06 | Hình không có chữ nào trong khối: ảnh gắn vào đơn vị trước (hoặc sau) cùng mục, cờ `assets_attached_to_neighbor` | Không sinh chunk rỗng |
| R-07 | Review chặn chunk gắn vào chunk theo `element_id`, `target` và **review cấp trang** (`{doc}:p005`, vd. `ocr_required`, `text_coverage_gap`) | Review cấp trang không có element |
| R-08 | `applies_to_models` = model trong ứng viên T-13 `available_only`; `not_available` không suy ra model áp dụng | Không suy diễn |
| R-09 | Nhãn ranh giới chunk ở file riêng `fixtures/eval/{doc}.chunks.json` (không thêm vào nhãn BL-34) | Thêm trang vào nhãn BL-34 sẽ đổi kết quả chấm T-12/T-08 |
| R-10 | Loại ngữ nghĩa `wiring`/`pinout`/… cũng gán cho đoạn văn/bảng theo tiêu đề mục; CQ-06 chỉ bắt buộc ảnh với `figure` hoặc chunk có ảnh | Bảng cổng là `pinout` nhưng không có ảnh |
| R-11 | Cờ chunk: `toc_like` (≥ 50% dòng có dấu dẫn mục lục), `replacement_char`, `ocr_page`, `asset_missing`, `embed_truncated`, `procedure_split`, `table_part`, `block_split`, `block_part_oversize` (R-12), `embed_over_budget` (CQ-12; chỉ chunk lá) | Hiện trong trang duyệt để người duyệt lọc |
| R-12 | Khối (không phải thủ tục/parameter/bảng) dài hơn `parent_max` có đầu phần (`chunking.block_part_patterns`) → chia **chỉ ở đầu phần**: đầu phần liền nhau là một đầu nhóm, hình ngay trước đầu phần đi theo nhóm đó; mỗi phần ≤ `parent_max` ký tự và `embed_text` ≤ `embed_max_tokens` − `embed_enrich_reserve`, các phần cân nhau. Phần 2…n mở bằng `"{tiêu đề} (phần i/n)"` + phần dẫn chung (phần tử trước đầu phần đầu tiên, nếu ≤ `block_lead_max` = 300 ký tự). Nhóm một mình vượt giới hạn → chia theo phần tử trong nhóm, không trộn với nhóm khác, cờ `block_part_oversize`. Không có đầu phần → chia theo phần tử như cũ. Phần của khối không gộp lại ở bước gộp overview | I-39 (2026-11-12, duyệt: Toma): retriever không kéo chunk láng giềng, mỗi phần phải tự đủ nghĩa (F54 mục 2.6.4.7: Case 3 tách khỏi kết luận) |
| R-13 | Đoạn/ghi chú ngắn (`overview`) ngay sau chunk hình cùng mục gộp vào chunk hình khi tổng chữ ≤ `figure_text_max` (600); không gộp phần của khối bị tách (`block_split`), không gộp bảng | I-45 (2026-11-13, duyệt: Toma): F54 2.2 (Figure 6 nguồn cấp + "Note:") từng thành cha 97 token với 2 con 67/83 token, vector từng con quá mỏng; F54 2.4.1 cũng gộp |
