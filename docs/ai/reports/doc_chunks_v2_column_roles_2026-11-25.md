# doc_chunks_v2: thành phần, vai trò từng cột và mức độ quan trọng (2026-11-25)

> **Lưu ý:** mục 1 (số dòng, phân bố vai trò, review_status) là ảnh chụp DB ngày 2026-11-25 và sẽ lệch khi nạp lại hoặc đổi catalog; đếm lại trước khi trích. Phần vai trò cột bám schema `doc_chunks_v2.sql`, chỉ đổi khi schema đổi. Chỉ mục: [STATE.md](../flows/doc-ingest/STATE.md).

Nguồn: schema `backend/sql/doc_chunks_v2.sql` (43 cột), hàm `match_doc_chunks_v2`, `retrieval/retriever.py`, `stages/answer_composer.py`, `sources.py`,
và số đếm trực tiếp trên Supabase (chỉ đọc) ngày 2026-11-25. Dùng làm căn cứ cho bước kiểm duyệt chunk (`review_status`).

## 1. Thành phần hiện có

- **948 dòng, tất cả `is_active`**, 10 tài liệu kỹ thuật (911 chunk) + 1 catalog (37 chunk). (STATE ghi 1.203 chunk: cũ hơn DB, cần đối chiếu.)
- **Tất cả `review_status = draft`, `audience = public`**; 0 chunk `approved`. `source`: `builder` 911, `manual` 37 (catalog).
- **Vai trò chunk:** `standalone` 555, `child` 268, `parent` 125. Cha không có embedding (125/948) và không được tìm; con có cha (268/948 có `parent_id`).
  Trung bình 2,14 con mỗi cha (tối đa 4). Câu trả lời dùng nội dung **cha** khi có (mở rộng từ con).
- **Loại (`chunk_type`):** figure 268 (chunk con gần như chỉ là chú thích hình), overview 149, procedure 128, section 125 (cha), table 116, wiring 96, parameter 45,
  spec 7, dimension 7, pinout 6, alarm 1.
- **Ngôn ngữ:** en 699, vi 212, vi+en 37. **Loại tài liệu:** user_guide 806, installation_manual 105, product_catalogue 37.
- **Phạm vi (`scopes`):** operation 533, installation 223, operation+configuration 115, installation+operation 38, operation+maintenance 2, rỗng 37 (catalog).
- **Ảnh:** 620 chunk có ảnh, tổng 1.142 ảnh. **Chunk ngắn dưới 80 ký tự:** phần lớn có ảnh (thông tin nằm trong ảnh).
- **Kích thước:** `content` trung vị 266, p90 960, tối đa 1.962 ký tự; `token_count` trung vị 158, tối đa 768. `embed_text` TB 518 ký tự so với `content` TB 340.
- **Dấu hiệu chất lượng trong `metadata` (quan trọng cho kiểm duyệt):** 808/911 chunk kỹ thuật có `review_blockers`; mã: `ocr_required` 753 (83% chunk kỹ thuật;
  cờ `ocr_page` 753), `column_count_mismatch` 33, `ambiguous_continuation` 29, `orphan_row` 19, `complex_header` 6, `text_coverage_gap` 3, `header_demotion_unsure` 3,
  `unassigned_cell` 1. Hầu hết chunk của mỗi tài liệu vận hành bị chặn (vd `f54-operation-en` 143/148, `f10t-operation-vi` 143/147); riêng 2 tài liệu lắp đặt F54/F86 chỉ 1 chunk mỗi bộ.

## 2. Vai trò từng cột

Mức độ: **A** = quyết định đúng/sai của kết quả hoặc quyền xem (lỗi là trả sai, mất chunk, hoặc lộ nội dung); **B** = ảnh hưởng chất lượng xếp hạng/hiển thị
(lỗi làm kém đi nhưng vẫn trả lời được); **C** = tham chiếu, vận hành, hoặc chỉ dùng cho kiểm duyệt/đánh giá, không ảnh hưởng truy vấn; **D** = chưa dùng.

### 2.1 Cho tìm kiếm và so sánh (hàm `match_doc_chunks_v2`)

| Cột | Vai trò | Độ phủ | Mức |
|---|---|---|---|
| `embedding` | nhánh vector (cosine, HNSW); chỉ chunk con/độc lập | 823/948 | A |
| `embed_text` | văn bản được nhúng và là nguồn của `fts`: "model · tài liệu · đường dẫn mục", dòng "Từ khóa", rồi nội dung | 948 | A |
| `fts` (tạo từ `embed_text`, cấu hình `simple`) | nhánh từ khóa (OR các từ, `ts_rank_cd`) | 948 | A |
| `product_models` | **lọc cứng** theo model của câu hỏi; so sánh chạy riêng từng model | 948 | A |
| `domain` | **lọc cứng** (`technical_docs`/`product_catalog`/`company_info`) theo định tuyến | 948 | A |
| `is_active`, `audience`, `review_status` | **lọc cứng**: chỉ chunk hoạt động, đúng đối tượng xem (website chỉ `public`), `approved` khi `RETRIEVAL_APPROVED_ONLY` | 948 | A |
| `chunk_role` | loại chunk cha khỏi tìm kiếm; cha chỉ để mở rộng ngữ cảnh | 948 | A |
| `scopes` | cộng điểm 0,003 khi trùng phạm vi (đã đổi từ lọc cứng) | 911 | B |
| `control_interface` | lọc theo giao tiếp (pulse train/EtherCAT/Mechatrolink); rỗng = áp dụng chung | 67 | B |
| `spec_attributes` | cộng điểm 0,005 khi trùng thuộc tính thông số (io, ports, monitor_size…) | 245 | B |
| `codes` | nhánh mã (#12010, CN1, X40…); **tắt ở production** (`use_codes`), có ở eval | 554 | B |
| `chunk_type` | cộng `type_boost`; hiện = 0 (tắt) | 948 | C |
| `parent_id` | mở rộng con → cha sau khi xếp hạng | 268 | A |

Ghi chú cơ chế: xếp hạng gộp bằng RRF theo **hạng** (không theo độ lớn điểm); `min_similarity` (cosine ≥ 0,25) áp ở tầng ứng dụng lên điểm vector; `top_k` cắt 6 chunk con rồi mở rộng cha (tối đa 5 cha).

### 2.2 Cho câu trả lời (đi vào prompt và giao diện)

| Cột | Đi tới đâu | Mức |
|---|---|---|
| `content` (của cha nếu có; cắt 3.000 ký tự) | nội dung **duy nhất** model dùng để trả lời trong `<sources>` | A |
| `section_path` / `section_title` | nhãn mục của nguồn gửi cho model và hiện ở huy hiệu trích dẫn | B |
| `page_start`, `page_end` | trang của nguồn (trang trong file PDF, không phải trang in) | B |
| `assets` | tham chiếu ảnh (bucket, path, trang); backend ký URL cho ảnh của chunk được trích `[S#]` | B |
| `doc_id` | tên tài liệu trong danh sách nguồn | B |
| `id` (thành `chunk_id`) | khóa nguồn `[S#]`, lưu snapshot lượt chat | A |

Không tới model hay giao diện: `doc_title`, `doc_version`, `printed_page_start/end` (đều được hàm trả về nhưng `ChunkMatch`/`ChunkRecord` bỏ). Hệ quả: 737/948 chunk có trang in khác trang file,
nên "tr. N" hiện cho khách là trang file, không khớp số trang in trong sách (chưa kiểm xem QS muốn hiển thị gì).

### 2.3 Cho kiểm duyệt, đánh giá và vận hành (không ảnh hưởng truy vấn)

| Cột | Vai trò | Độ phủ | Mức |
|---|---|---|---|
| `metadata.review_blockers` | mã chặn duyệt (OCR, bảng lỗi…): **chunk còn blocker không nên `approved`** | 808 | A (cho kiểm duyệt) |
| `metadata.flags`, `metadata.review_notes` | cờ và ghi chú trình xây (table_part, table_no_header, ocr_page, curated…) | 872 / 171 | B |
| `metadata.extraction`, `metadata.enrichment` | cách trích (text_layer/OCR) và mức làm giàu | 948 | C |
| `metadata.locations`, `element_ids`, `row_ids`, `figure_labels`, `logical_table_id` | truy vết về trang/phần tử/hàng bảng nguồn, nhãn hình | 911 / 151 / 474 | C |
| `metadata.crm`, `param_codes`, `io_codes`, `applicability_notes`, `faq_vi` | dữ liệu CRM và mã tham số/IO, ghi chú áp dụng, FAQ | 911 / 80 / 82 / 16 / 23 | C |
| `content_hash` + `section_path` | **khóa nhãn đánh giá** (chunk đúng khớp theo cặp này, không theo `id`); đổi khi nạp lại | 948 | A (cho đánh giá) |
| `chunk_key`, `chunk_index`, `doc_id`, `doc_version` | khóa duy nhất, thứ tự trong tài liệu | 948 | C |
| `source`, `source_run`, `loaded_at`, `embedding_model` | nguồn nạp, lần chạy, thời điểm, model nhúng | 948 / 823 | C |
| `keywords` | từ khóa (đã vào `embed_text` nên gián tiếp ảnh hưởng tìm kiếm) | 948 | B |
| `summary_vi` | tóm tắt tiếng Việt, hầu như trống (23/948) | 23 | D |
| `applies_to_models` | model áp dụng thêm: **không chunk nào có giá trị**, hàm không dùng | 0 | D |
| `lang`, `doc_type`, `doc_title`, `token_count`, `section_id`, `printed_page_*` | mô tả/phân loại, chưa dùng khi truy vấn | 948 / 837 / 838 | C |

## 3. Tiêu chí kiểm duyệt gợi ý theo mức

- **Mức A, bắt buộc đạt mới `approved`:** `content` đọc đúng (không mất chữ số/dấu, không chỉ có tiêu đề khi thông tin nằm trong ảnh mà chưa có mô tả); `product_models` đúng sản phẩm (kiểm `10i` so với `10iV`);
  `domain`, `audience` đúng; quan hệ cha–con đúng; không còn `review_blockers` chặn (nhất là `ocr_required`, `column_count_mismatch`, `orphan_row`).
- **Mức B, nên đạt:** `scopes`, `control_interface`, `spec_attributes` đúng; `section_path`/trang đúng; `assets` gắn đúng chunk; `keywords` không gây nhiễu.
- **Mức C/D:** không chặn duyệt; ghi nhận để dọn (`applies_to_models`, `summary_vi` trống).

Phát hiện cần xử lý (chi tiết trong LOG website-qa 2026-11-25): 83% chunk kỹ thuật có `ocr_required`; STATE ghi 1.203 chunk còn DB 948; trang trích dẫn là trang file thay vì trang in; `applies_to_models` rỗng 100%.
