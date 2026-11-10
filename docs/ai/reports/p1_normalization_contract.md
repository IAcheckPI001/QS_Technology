# P-1 — Contract lớp chuẩn hóa (Docling raw → chunk builder)

Trạng thái: **rev 3, C1 đã khóa (2026-11-03)**. D-01, D-02, D-03, D-04 (mô hình
dữ liệu), D-08, D-11 đã chốt
([assessment §6](p1_chunking_impact_assessment.md#6-quyết-định-đang-mở)).
Rev 3 sửa T-01 (biên cột theo khe trắng, vì luật cũ sai trên chính F54) và ghi
các quyết định chi tiết 2a–2d, 3a–3d, 4a–4d, 8a–8d, 11a–11d.

Phần đã có code (schema, profile, S0, T-01…T-11, T-12, T-13, T-14, T-15,
T-16, T-17, T-18, V-01, `NormalizedElement`, review queue, lõi approval) nằm ở
`backend/app/modules/doc_ingest/` (`schemas/`, `profile.py`, `profiles/`, `s0.py`,
`normalize/`, `technical_refs/`, `validate/`, `review/`). Phần còn lại của contract
(T-12/T-13 trên text, V-02…V-04, builder) chưa có code.

Mục tiêu: lớp **nhỏ nhất** đủ để chunk builder và bước trích fact không phải tự
đoán cấu trúc từ output Docling.
- Docling raw giữ nguyên.
- Mọi giá trị chuẩn hóa truy về được nguồn (`raw_ref` + bbox).
- Mọi biến đổi đều ghi log.
- Lớp này **không** sửa nội dung nguồn.

## 0. Nguyên tắc pipeline chung (rev 2)

Pipeline chạy cho mọi PDF được nạp vào, không biết trước tài liệu có lỗi cấu
trúc nào. Rev 1 rút luật từ một tài liệu (F54); rev 2 tách phần dùng chung khỏi
phần riêng của tài liệu hoặc của miền:

1. **Luật T-xx chỉ dùng tín hiệu hình học và cấu trúc.**
   - Ngưỡng là sai số **tương đối** (theo độ rộng cột, chiều rộng trang), không
     dùng số point tuyệt đối rút từ một tài liệu.
   - Luật không được tham chiếu `doc_id`, tên file hay model cụ thể; có test kiểm.
2. **Tri thức miền và ngôn ngữ nằm trong profile cấu hình (§9)**, không nằm
   trong code luật: mẫu mã, cụm từ điều kiện áp dụng, từ khóa caption, danh sách
   model. Profile `default` hoàn toàn chung; thiếu profile riêng thì pipeline
   vẫn chạy, chỉ là gắn cờ nhiều hơn.
3. **Phát hiện thay vì chỉ sửa.**
   - Không liệt kê hết được lỗi parse. Tầng kiểm bất biến V-xx (§8) không phụ
     thuộc loại lỗi: so output với text layer của PDF và với các bất biến cấu trúc.
   - Lỗi chưa biết phải thành mục `review_queue` hoặc cờ trên knowledge unit,
     không thành dữ liệu sai im lặng.
4. **Đo trước khi parse.** Hồ sơ tài liệu S0 (§7) đo từng trang để chọn cấu hình
   (OCR, chế độ bảng) thay vì một cấu hình cố định cho mọi file.
5. **Vòng phản hồi.**
   - Lỗi parse người duyệt tìm thấy được đưa vào corpus golden (như fixture F54).
   - Luật được sửa theo hướng chung và phải đạt trên **toàn bộ** corpus, không
     thêm nhánh cho một file.
6. **Giới hạn đã biết.** Lỗi hợp lệ về hình thức (ô rơi sai cột nhưng cùng kiểu,
   OCR đọc sai một chữ số) không phát hiện tự động hoàn toàn được. Vì vậy duyệt
   bắt buộc theo mức rủi ro (assessment H-8) là yêu cầu cứng.

## 1. Bố cục dữ liệu một lần chạy

```text
data/ingest_runs/{doc_id}/{run_id}/
  manifest.yaml                          bản sao manifest dùng cho lần chạy
  profile.json                           hồ sơ tài liệu S0 + profile cấu hình đã chọn (mục 7, 9)
  raw/p{n}.docling.json                  DoclingDocument theo trang — KHÔNG sửa
  raw/p{n}.words.json                    từ của text layer + bbox (pypdfium2), cho V-01
  raw/p{n}.objects.json                  bitmap (bounds + px) và nét vector (pypdfium2), cho T-09, T-10, T-14
  normalized/elements.jsonl              NormalizedElement (mục 2)
  normalized/tables.jsonl                LogicalTable (mục 3)
  normalized/normalization_log.jsonl     mỗi biến đổi một dòng (mục 5)
  normalized/review_queue.jsonl          mục cần người xử lý (mục 6)
  normalized/validation.jsonl            kết quả kiểm bất biến V-xx (mục 8)
  normalized/images/{element_id}/original.png, preview.png   (`:` trong element_id đổi thành `_`; chỉ khi có PDF)
  run_report.json                        version Docling/pipeline, sha256 PDF, thống kê, gate
```

Chạy lại trên cùng PDF và cùng version pipeline phải cho cùng
`normalized/*` (deterministic; không dùng thời gian hay số ngẫu nhiên trong ID).

## 2. NormalizedElement

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `schema_version` | int | có | `1` |
| `element_id` | str | có | `{doc_id}:p{pdf_page_index:03d}:e{order:03d}` |
| `raw_ref` | `{file, self_ref}` | có | vd. `{"file":"raw/p169.docling.json","self_ref":"#/tables/0"}` |
| `pdf_page_index` | int ≥ 1 | có | trang vật lý |
| `printed_page` | `{value: str\|null, source: "page_labels"\|"furniture_sequence"\|"manifest_override"\|null}` | có | không bao giờ suy từ offset (T-06) |
| `content_layer` | `body` \| `furniture` | có | header/footer = `furniture` |
| `reading_order` | int | có | thứ tự `iterate_items` |
| `source_element_type` | str | có | nhãn Docling **nguyên gốc** (section_header, text, list_item, table, picture, caption, page_header, page_footer…) |
| `normalized_type` | enum | có | `heading`, `label_heading`, `text`, `list_item`, `warning`, `table_segment`, `picture`, `screenshot`, `caption`, `watermark_candidate`, `furniture`, `figure_text` (chữ trong hình, gồm nhãn sát hình T-18: không vào text thân chunk, không làm heading), `toc` (T-16), `unsupported` (T-16) |
| `bbox` | `{x0,y0,x1,y1}` pt, gốc trên-trái | có (trừ khi Docling không có prov) | |
| `text` | str \| null | | **nguyên văn** text layer, không sửa chính tả |
| `lang` | ISO 639-1 \| null | có | theo element (I-16), không theo manifest; `null` cho tới khi có nhận diện ngôn ngữ (không đoán) |
| `section_path` | list[str] | có | theo T-07 |
| `parent_element_id` | str \| null | | picture/table chứa phần tử (caption, `figure_text`); thêm 2026-11-03 |
| `section_path_source` | `numbering` \| `inherited` \| `none` | có | |
| `label_heading` | str \| null | | heading không đánh số gần nhất phía trên ("Note:", "Notes:") |
| `list` | `{indent_x, depth, parent_element_id\|null, marker\|null}` \| null | | T-08 (`depth` 0 = cấp 1); chỉ list_item body; trong code tên `list_info` (model `ListInfo`; `list` trùng builtin Python) |
| `table_ref` | `{logical_table_id, segment_index}` \| null | | với `table_segment` |
| `image` | `{original_path, preview_path, scale, px_w, px_h, crop_bbox, crop_sources, extraction}` \| null | | với `picture`, `screenshot`, `watermark_candidate` (T-14). `extraction` ∈ {`page_render_crop`, `manual_region`} (mở rộng được sau spike F86). `crop_sources` ⊆ {`docling`, `bitmap`, `vector`, `label`} (thêm 2026-11-03). Đường dẫn, `scale`, `px_*` là `null` khi lần chạy không có PDF để render |
| `caption_element_id` | str \| null | | với picture/screenshot/bảng: caption của nó (T-11) |
| `caption_link` | `{source: "docling"\|"rule", rule_id\|null}` \| null | | T-11 |
| `duplicate_of` | str \| null | | T-19: phần tử hình này là bản trùng của phần tử được giữ (thêm 2026-11-08) |
| `param_refs` | list[TextParamRef] | | T-12 trên text: `ParamRef` + `start`, `end` (`text[start:end] == label`) + `role` ∈ {`definition`, `value_option`, `mention`} (thêm 2026-11-09) |
| `applicability_candidates` | list[`ApplicabilityCandidate {status: "not_available"\|"available_only"\|"conditional", note, models[], interfaces[], condition_text, rule_id: "T-13"}`] | | T-13; cùng schema với `Row.applicability_candidates` (§3). Là **ứng viên**, không phải fact: chưa trích, chưa duyệt. `Applicability` của fact (thêm `source: lexicon\|llm\|reviewer`, trạng thái duyệt) thuộc bước trích fact (BL-17) |
| `flags` | list[str] | có | vd. `caption_relinked`, `watermark_candidate`, `figure_text_attached` (T-18), `repeated_image` (T-10: ảnh cùng nội dung lặp ở vị trí khác, giữ là picture), `duplicate_image` (T-19), `list_cross_page`, `list_marker_mixed` (T-08) |
| `review_required` | bool | có | có mục tương ứng trong review_queue |

`warning`: `list_item`/`text` dưới `label_heading` ∈ {Note, Notes, Warning,
Caution, Chú ý, Cảnh báo}, hoặc có tiền tố `DO NOT` / `WARNING`. Warning giữ
`section_path` của section chứa nó; quan hệ với procedure/wiring do builder dựng
từ section + vị trí.

## 3. LogicalTable

Một bảng logic gồm nhiều segment (bảng nối trang). Ví dụ dưới đây dựa trên bảng
5.1 Axis parameters (167 → 168 → 169 t0). Tọa độ `x_min`/`x_max` và `row_id`
**chỉ để minh họa**; giá trị thật do T-01 tính.

```json
{
  "schema_version": 1,
  "logical_table_id": "f54_om:t003",
  "segments": [
    {"element_id": "…:p167:e002", "pdf_page_index": 167, "bbox": {…},
     "num_cols_docling": 4, "header_rows_docling": [0]},
    {"element_id": "…:p168:e002", "pdf_page_index": 168, "bbox": {…},
     "num_cols_docling": 4, "header_rows_docling": [0]},
    {"element_id": "…:p169:e000", "pdf_page_index": 169, "bbox": {…},
     "num_cols_docling": 3, "header_rows_docling": []}
  ],
  "columns": [
    {"index": 0, "header_text": "Parameter", "x_min": 84.0, "x_max": 178.0, "header_source": "detected"},
    {"index": 2, "header_text": "Work range", "x_min": 375.0, "x_max": 465.0, "header_source": "detected"}
  ],
  "rows": [
    {"row_id": "r0", "segment": 0, "is_header": true, "cells": […]},
    {"row_id": "r22", "segment": 1, "is_header": false,
     "cells": [
       {"col": 0, "text": "#4140 - #4147", "bbox": {…}, "raw_cell_ref": "#/tables/0/cells/0",
        "docling_col": 0, "docling_header": true, "assigned_by": "bbox"},
       {"col": 2, "text": "0: Linear 1: Rotary 1 2: Rotary 2", "assigned_by": "bbox", "…": "…"}
     ]}
  ],
  "flags": ["header_flag_demoted:r22", "header_inherited:segment2", "empty_column_restored:segment2:col2"]
}
```

Bất biến:
- Mọi dòng có **đúng** `len(columns)` cell. Ô trống có `text=""`,
  `raw_cell_ref=null`, `assigned_by="empty_fill"`.
- `col` do T-01 gán; `docling_col` / `docling_header` chỉ giữ để truy vết.
- Không cell nguồn nào bị xóa. Cell không gán được cột nằm trong
  `unassigned_cells[] {row_id, text, bbox, raw_cell_ref, reason: outside_columns|column_collision}`
  và có mục `unassigned_cell` (blocking). Cell T-15 gộp vào ô trên nằm trong
  `merged_cell_refs[]` của ô đó. Mỗi cell Docling xuất hiện đúng một lần trong
  `raw_cell_ref` ∪ `merged_cell_refs` ∪ `unassigned_cells` (GT-18, LT-02).
- `columns[].header_source`: `detected` (từ segment đầu), `none` (bảng không có
  header; `header_text=null`, mục `header_missing` chặn fact). Không có header
  được bịa ra. Segment nối trang kế thừa `columns` và được ghi cờ
  `header_inherited:segment{k}`.
- Header nhiều tầng (D-02, 2c): `header_text` ghép bằng `" / "` theo thứ tự dòng,
  cờ `complex_header` + mục `complex_header` chặn chunk của bảng đó. Ô merge, bảng
  xoay, bảng lồng chưa xử lý ở V1.

Định danh (D-02, 2a–2d):
- `logical_table_id = {doc_id}:t{nnn}`, đánh số theo thứ tự xuất hiện (trang, rồi
  y của segment đầu). Id là định danh **của lần chạy**: cùng input thì giống nhau
  (GT-17), input khác (thêm/bớt trang hay bảng phía trước, parser khác) thì có thể
  đổi. Giữ approval (H-6, `review/approval.py::carry_over`): có bản ghi cùng id →
  cùng `(unit_type, content_hash, evidence_hash)` thì giữ, khác thì
  `pending_review`; không có bản ghi cùng id → khớp **duy nhất** theo hash với bản
  ghi chưa dùng thì giữ (`matched_by=hash`), nhiều bên thì `pending_review`, không có
  thì là unit mới. `evidence_hash` không được chứa `logical_table_id`/`row_id`. Hai
  bảng đổi chỗ (id hoán đổi) về duyệt lại.
- `row_id = r{n}` theo thứ tự nguồn **trước** T-15; dòng sau khi gộp giữ id dòng
  đầu, id các dòng bị gộp nằm trong `merged_row_ids` và log T-15. Id không bao giờ
  được dùng lại.
- `Row` còn có `repeated_header` (T-05 bước a), `param_ref` (T-12) và
  `applicability_candidates[]` (T-13, ứng viên, không phải fact).
- V1 lưu `LogicalTable` trong `normalized/tables.jsonl` (offline). DB chỉ nhận
  chunk/fact kèm tham chiếu `(logical_table_id, row_id)`; DDL thuộc C2.

## 4. Tham chiếu parameter (D-01, đã chốt)

```text
ParamRef {
  prefix:       str          # "#", "M"  — namespace riêng: #1920 ≠ M1920
  kind:         "single" | "range" | "list"
  codes:        list[int]    # TƯỜNG MINH, tăng dần, không trùng; nguồn DUY NHẤT để khớp
  range_start:  int | null   # chỉ khi kind = range (mô tả/kiểm nhất quán)
  range_end:    int | null
  label:        str          # nguyên văn: "#8030, #8032 #8034, #8036"
}
```

| Mẫu nguồn | Kết quả |
|---|---|
| `#0104`, `M1920` | `single`, codes `[104]` / `[1920]` |
| `#a - #b` (gạch `-`/`–`/`—`; cùng prefix; `b > a`) | `range`, codes = a…b bước 1 |
| ≥ 2 mã cùng prefix, cách nhau bởi `,` / khoảng trắng / xuống dòng | `list` |

- Mọi mẫu khác → `unparseable` (blocking cho fact):
  - trộn prefix;
  - trộn dải và danh sách;
  - `b ≤ a`;
  - hậu tố lạ.
- Dải dài hơn `MAX_RANGE_LEN = 64` → vẫn parse, gắn cờ `range_too_long`.
- **Kiểm chéo trong bảng logic**: codes của các dòng khác nhau phải rời nhau;
  giao nhau → `param_code_overlap` (blocking). Đã kiểm trên F54 167–171: không
  giao ([assessment, Phụ lục A](p1_chunking_impact_assessment.md#phụ-lục-a--lệnh-xác-minh-chỉ-đọc)).
- Tra cứu:
  - khớp một mã: `codes @> [n]`;
  - câu hỏi chứa dải/danh sách: `codes && […]`;
  - `#3` và `#0003` khớp nhau (lưu số nguyên); hiển thị luôn bằng `label`.
- Giá trị theo từng mã (I-19, vd. `1000/5000/10000` cho 3 mã): giữ nguyên văn +
  cờ `per_code_values`. Chỉ tách khi người duyệt đặt
  `code_semantics ∈ {per_axis, per_item}` kèm `code_labels` cùng độ dài `codes`.

## 5. Biến đổi deterministic

Mỗi lần áp dụng ghi một dòng `normalization_log.jsonl`:

```json
{"rule_id": "T-05", "element_id": "…:p168:e002", "target": "r22",
 "before": {"docling_header": true}, "after": {"is_header": false},
 "reason": "first cell matches param pattern while logical table has header", "deterministic": true}
```

| ID | Biến đổi | Luật | Bằng chứng P-1 |
|---|---|---|---|
| T-01 | Gán cột theo bbox (rev 3) | Gộp khoảng x `[x0, x1]` chồng nhau của các cell **dữ liệu** có tâm nằm trong bbox bảng; mỗi cụm là một cột, biên cột = giữa khe trắng giữa hai cụm, cột ngoài cùng kéo tới mép bbox bảng. Số cụm ≠ số cột Docling (vd. cell tràn qua khe) → dự phòng: trung điểm tâm x của header cell (không có header thì trung vị tâm x theo chỉ số cột Docling, chỉ dùng làm cụm, thứ tự theo x) + `column_count_mismatch` (chặn chunk). Segment nối trang dùng biên kế thừa (T-04). Cell được gán vào cột chứa tâm x của nó; hai cell cùng cột trong một dòng → cell sau vào `unassigned_cells` (`column_collision`). Luật rev 2 (trung điểm tâm header) sai trên chính F54: cột chữ căn trái có tâm lệch sang cột bên cạnh, 18 cell trùng cột ở trang 11, 14, 171 | trang 11 (10/10 dòng đảo), trang 169 t0; khe trắng cho đúng số cột Docling ở 10/10 bảng F54 |
| T-02 | Lấp ô trống | Cột không có cell trong một dòng → cell rỗng tường minh | trang 168 (29/32 dòng), 171 |
| T-03 | Nối bảng qua trang | Segment là phần tử bảng **đầu** trang N, bảng logic mở ở **cuối** trang N-1, và cả bốn điều kiện: (1) biên trái/phải lệch ≤ `continuation_tol` × độ rộng cột hẹp nhất của bảng logic (mặc định 0,15); (2) số cột Docling ≤ số cột bảng logic; (3) không có heading hay caption chen giữa (bỏ qua furniture); (4) segment không có header, hoặc "header" của nó trùng header bảng logic, hoặc bị T-05 nhận là dòng dữ liệu. Kết quả: (1)+(2) đạt → nối; dòng header T-05 không phân loại được vẫn nối nhưng có `header_demotion_unsure` (chặn chunk), không bao giờ nối im lặng. (1) hoặc (2) không đạt: segment không header → bảng mới + `ambiguous_continuation` (chặn chunk); segment có header riêng → bảng mới. Vị trí "đầu trang N, cuối trang N-1": phần tử body không phải furniture và không phải picture không caption (watermark) chen giữa thì đóng bảng logic | 168, 169 t0, 170 t0, 171 t0 |
| T-04 | Kế thừa header + biên cột | Segment nối trang dùng `columns` của bảng logic | 169 t0 (khôi phục cột Work range) |
| T-05 | Nhận header theo tín hiệu | Áp cho dòng mang cờ header Docling khi bảng logic **đã có** header. Thứ tự: (a) trùng nguyên văn header bảng logic → header lặp, giữ `is_header=true` và đánh `repeated_header` (builder bỏ qua); (b) **hình dạng token** của cell cột 0 khớp hình dạng đa số các dòng dữ liệu cùng cột → `is_header=false`; (c) cell cột 0 khớp một mẫu mã trong profile (§9) → `is_header=false`; (d) còn lại → giữ cờ header Docling + `header_demotion_unsure` (chặn chunk của bảng đó). Bước (b) (D-03, 3b): dòng dữ liệu = mọi dòng không phải header của bảng logic cộng segment đang xét; cần ≥ `shape_min_rows` (3) dòng có cột 0 không rỗng, hình dạng phổ biến nhất chiếm ≥ `shape_majority` (60%) và dòng xét có đúng hình dạng đó; cột trộn nhiều hình dạng thì rơi xuống (c)/(d). Không dùng kiểu chữ ở V1 (3c). Hình dạng token: thay chữ số liên tiếp bằng `9`, chữ cái liên tiếp bằng `a`, giữ ký hiệu (vd. `#4140 - #4147` → `#9 - #9`), suy ra **từ chính bảng**, không khai báo trước | 168 r0 (`#4140 - #4147` cùng hình dạng `#9 - #9` với các dòng 167) |
| T-06 | Trang in | Theo thứ tự: (1) `/PageLabels` của PDF (S0); (2) **chuỗi furniture**: trong furniture đã xác nhận (T-17) ở dải trên/dưới, token số nguyên cùng **mẫu** (dải + token liền trước/sau, chữ cái và chữ số dính nhau được tách) có `giá trị − pdf_page_index` bằng nhau trên ≥ `furniture_min_pages` (3) trang; trang có số không khớp offset đó → `null` + `printed_page_conflict`; (3) `printed_page_override` của manifest (chỉ để ghi đè; chưa có manifest). Không có nguồn nào → `null`. Không suy từ offset, không nội suy trang thiếu số. **Sửa 2026-11-03**: bỏ điều kiện "cùng vị trí x" và "trang liên tiếp": OCR gộp hai dòng footer làm x đổi (F86 trang 6, 11: x=34 thay vì 514), một số in sai không được làm mất cả đoạn, và tập trang chọn có thể không liền nhau (fixture F54) | footer `Page \| N` ở 11/11 trang; F54 không có `/PageLabels` |
| T-07 | Section path | Ứng viên: `section_header`/`title` nằm trực tiếp trong body + heading T-17 trả về (không xét con của picture). Heading khớp `^\d+(\.\d+)*\.?\s+<chữ>` hoặc `^<từ khóa phần>\s+\d+[.:]?` (tiêu đề được dính ngay sau `:`/`.` nếu bắt đầu bằng chữ cái, sửa 2026-11-08 cho F54 `PART 1:CONTROLLER OVERVIEW`, I-26; `PART 1.2 X` không khớp; từ khóa trong profile; `default`: `PART`, `CHAPTER`, `Phần`, `Chương`; không phân biệt hoa thường) mở/đóng cấp theo dãy số: giữ section có số là tiền tố thật của số mới (`CHAPTER 2` = (2), `2.1` nằm dưới). Số dính chữ do OCR (`2.9.1AXIS`, chỉ với số nhiều đoạn) → nhận, cờ `heading_spacing`; thiếu section cha → cờ `section_parent_missing`. Tài liệu không đánh số → V-04 báo `section_path_source=none` trên tỷ lệ lớn, chưa suy cấp theo cỡ chữ ở V1; heading khác → `label_heading` (gán cho phần tử sau cho tới heading kế tiếp); trạng thái mang qua trang | mọi heading `level=1`; trang 168–171 không có heading |
| T-08 | List cha–con (**v1**, sửa 2026-11-09; kiểm trên F54, F86 chưa có list con — xem lại khi thêm tài liệu) | Docling trả list phẳng (không lồng, `enumerated` false, `marker` không đáng tin) nên cấp suy từ lề trái `x0`: **lề là tín hiệu chính, glyph là tín hiệu phụ**; không chắc → review, không gán cha im lặng. Xét list_item body (bỏ furniture, phần tử con của picture/table, `watermark_candidate`, `duplicate_image`). Ngăn xếp cấp đang mở trong **khối list**; mọi phần tử body khác list_item (kể cả `text`) ngắt khối. Mục mới ở lề x: (a) lùi lề → bỏ các cấp có lề > x + 3 pt; khớp (±3 pt) một cấp đang mở → cùng cấp đó; không khớp cấp nào → `list_level_ambiguous`; (b) cùng lề (±3 pt) với đỉnh → anh em, cùng cha; (c) thụt sâu hơn đỉnh ≥ `list_indent_min` (18 pt) → con của đỉnh; thụt 3–18 pt và text bắt đầu bằng glyph `list_glyphs` **có khoảng trắng theo sau** (`o M1920` có, `operation` không) → con; thụt 3–18 pt không glyph → `list_level_ambiguous`. Glyph không bao giờ tạo con khi không thụt sâu hơn (tài liệu dùng `- ` cho cấp 1 không bị gán nhầm). Anh em của mục mơ hồ cũng `list_level_ambiguous`. **Qua trang**: phần tử body đầu trang (trước chỉ có furniture) là list_item và phần tử body cuối trang liền trước là list_item → tiếp tục ngăn xếp, cờ `list_cross_page`. Mục đầu khối có glyph, thụt sâu hơn list khác cùng trang ≥ 18 pt → `list_orphan` (lùi về lề cấp 1 sau đó không review thêm). Anh em cùng cha khác marker → cờ `list_marker_mixed` (không review). `list` = `{indent_x = x0, depth (0 = cấp 1), parent_element_id, marker}`; `marker` = glyph đầu text, không có thì marker Docling (rỗng → null). `text` giữ nguyên văn (không cắt glyph). Log `T-08` cho mỗi quan hệ cha–con | trang 19 (x 103 vs 139, glyph `o`), GT-07; trang 66→67 (`o #4142 = 1/2` nối cha cuối trang trước); trang 71 (dòng công thức Docling gắn list_item ở x 88, bullet Wingdings `\uf0f0` ở x 103 → 3 `list_level_ambiguous`) |
| T-09 | Screenshot | `table` có 0 cell và diện tích phủ bởi bitmap nhúng ≥ 0,8 (`screenshot_bitmap_min`) → `screenshot` (crop như picture, giữ caption, không vào bảng logic, không `empty_table`). Bitmap đo từ PDF (`raw/p{n}.objects.json`); ảnh nằm trong Form XObject lấy bounds của form | trang 18 Figure 15 (ảnh nằm trong Form XObject) |
| T-10 | Ứng viên watermark | Bitmap cùng **nội dung** (`hash` sha256 của dữ liệu ảnh trong PDF, lưu ở `objects.json`) và cùng vị trí (± 1 pt) xuất hiện ≥ `furniture_min_pages` (3) trang; picture không caption có ≥ 90% diện tích nằm trong bitmap đó (`watermark_cover_min`) → `watermark_candidate` (không xóa). Picture có caption, hoặc còn bị bitmap không lặp phủ ≥ 50% → giữ picture + `watermark_conflict`. **Sửa 2026-11-03**: (1) điều kiện cũ IoU ≥ 0,9 trượt chính trang 171 vì Docling chỉ khoanh một phần watermark (IoU 0,53); (2) **sửa 2026-11-08 (I-24)**: bỏ tiêu chí "cùng px + cùng cỡ hiển thị" vì F54 dùng một khung 480×272 px, 360×204 pt cho mọi ảnh giao diện khác nội dung (7 screenshot bị nhận nhầm); chỉ "cùng nội dung" cũng chưa đủ vì tài liệu dùng lại nguyên một ảnh giao diện ở nhiều trang (F54 trang 61–64, vị trí khác nhau). Picture không caption nằm trong ảnh cùng nội dung lặp ≥ 3 trang nhưng khác vị trí (logo F86, ảnh dùng lại) giữ là picture, chỉ thêm cờ thông tin `repeated_image`. `objects.json` không có `hash` → T-10 không chạy (log `no_bitmap_hash`), không đoán theo kích thước | 671×427 px mọi trang; trang 106, 132, 142, 164, 171 |
| T-11 | Gắn lại caption | Caption bắt đầu bằng từ khóa bảng (`table_caption_keywords`, `default`: `Table`, `Bảng`) → bảng gần nhất cùng trang; từ khóa hình (phần còn lại của `caption_keywords`: `Figure`, `Fig.`, `Hình`) → picture/screenshot gần nhất **phía trên** cùng trang: đáy hình không thấp hơn đáy caption và hai bên chồng nhau theo chiều ngang (bổ sung 2026-11-03, F86 trang 9: dải hình ở lề phải cùng hàng caption). Áp dụng cả cho caption Docling không gắn vào đâu. Ứng viên watermark không nhận caption. Hai ứng viên cách nhau ≤ 1 pt mà một trong hai là đích Docling đã gắn → giữ liên kết Docling (bổ sung 2026-11-08: Docling sinh cả picture lẫn bảng 0 cell cho cùng một screenshot, F54 trang 64, 81, 85, 96). Không có ứng viên, hoặc hòa mà không có liên kết Docling → `caption_ambiguous`, giữ liên kết Docling. Đổi liên kết → cờ `caption_relinked`, `caption_link.source = rule` | trang 11 (Figure 5 bị gắn vào bảng); F86 trang 17 (caption không có parent) |
| T-12 | Parse parameter | Theo §4 với tập prefix `param_prefixes` của profile (`default` rỗng → không parse; `qs_controller`: `#`, `M`). Bảng là bảng parameter khi ≥ `shape_majority` dòng dữ liệu có cột 0 parse được; khi đó mọi dòng có cột 0 không rỗng được parse, dòng không parse được → `param_unparseable`. **Trên text** (sửa 2026-11-09): chỉ quét prefix có trong `param_text_patterns` của profile (prefix → regex số chữ số; `default` rỗng → không quét; `qs_controller`: `#` 4–5 chữ số, `M` đúng 4 chữ số vì `M100` là M-code, `M8` là chân output). Token đứng riêng (không dính chữ/số trước hoặc sau; `M100H3` không khớp). Token cùng prefix nối bằng `,`/khoảng trắng hoặc gạch ngang được gộp rồi parse theo §4 (dải ngược, trộn dải với danh sách → `param_unparseable`; dải > 64 → `range_too_long`); khác prefix hoặc nối bằng chữ (`and`) → nhiều ref. Vai trò: `definition` (mã đứng đầu phần tử, sau một glyph đầu dòng nếu có, theo sau là `:`), `value_option` (theo sau là `=`), `mention`. Prefix đúng mà số chữ số không khớp → **near-miss** (chỉ báo cáo, không review). Phạm vi: phần tử body `text`, `list_item`, heading, `caption`, `footnote`; không quét furniture, `figure_text`, mục lục, bảng. Kết quả `param_refs: list[TextParamRef]` | 167–171, 19; text F54: 227 ref (98 định nghĩa, 75 giá trị, 54 nhắc tới), phủ 302/302 token; near-miss `M100`, `M8`, `M100H`, `M195` (trang 94, lỗi đánh máy) |
| T-13 | Ứng viên ghi chú áp dụng | Cụm từ điều kiện trong lexicon của profile (`default` gồm tiếng Anh + tiếng Việt, vd. `not available on`, `available on`, `only for`, `not supported`, `không áp dụng`, `chỉ áp dụng`, `không hỗ trợ`) → `applicability` với `status` theo cụm từ, `note` nguyên văn (chuỗi con của text nguồn), `condition_text` = phần sau cụm từ tới `)`/`]`/`;`/hết câu, `models[]` khớp model + alias registry, `interfaces[]` khớp `control_interface` registry (khóa hoặc nhãn). Không khớp gì → `models=[]`, `interfaces=[]`, mục `applicability_model_unmatched` (chặn fact, không chặn chunk); cụm `available_only` không khớp gì được hạ thành `conditional` (vd. "touch controller" không phải model hay interface trong registry). Cụm từ khớp theo ranh giới từ ("available options", "Unavailable on" không khớp); cụm dài thắng cụm ngắn chồng lên nó. Fact mang ghi chú luôn được giữ. Chạy trên ô bảng và (từ 2026-11-09) trên text cùng phạm vi T-12 (`applicability_candidates` của phần tử; F54 text: 0 cụm, mọi cụm nằm trong bảng trang 170–171). Lớp chuẩn hóa chỉ đánh **ứng viên**; câu điều kiện không có trong lexicon được bắt ở bước trích fact (LLM, evidence nguyên văn) | 171 `#0136`, `#4132–#4134` |
| T-15 | Gộp dòng tiếp nối | Trong bảng logic, dòng có cell cột khóa (cột 0) rỗng và các cell khác nằm sát dưới dòng trước (khoảng cách dọc ≤ 1,5 × chiều cao dòng trung vị) → nối text từng cột vào dòng trên, ghi log; không đủ điều kiện → giữ dòng riêng và gắn `orphan_row` | ca mô tả xuống dòng; chưa có trong mẫu F54, cần fixture tổng hợp |
| T-14 | Crop | Vùng crop = hợp của bbox Docling; bounds của mọi bitmap nhúng phủ ≥ 50% bbox đó (`crop_bitmap_min`); **nét vector** có tâm trong bbox và không vượt bbox quá `crop_vector_margin` (36 pt, để loại khung viền trang); **chữ của hình** (`figure_text`, gồm nhãn T-18). Cộng padding 12 pt (`crop_padding`), kẹp trong trang; nguồn mở rộng ghi ở `image.crop_sources`. Hai nguồn vector và chữ của hình thêm 2026-11-03 (F86: bản vẽ vector, nhãn `320 mm` nằm ngoài bbox picture). Render pdfium ở `max(3, native_px_per_pt)` (trần 4) cho `original`; scale 2, rộng ≤ 1600 px cho `preview`. Trang xoay chưa render (chuẩn hóa hướng chưa làm) | trang 9: bbox Docling (89,7–526,4) hẹp hơn bitmap (54,8–561,7) khoảng 35 pt mỗi bên nên cắt mất "4 - M4"; trang 11/18/40 lệch ≤ 2 pt; F86 trang 8, 9 |

| T-16 | Phân loại nhãn Docling + mục lục | Nhãn `table`, `document_index`, `picture`, furniture: có xử lý; `title`, `section_header`, `text`, `list_item`, `caption`, `footnote`: giữ nguyên văn, chuẩn hóa ở BL-07…BL-10. `document_index` (mục lục) → `normalized_type = toc`, giữ nguyên cell, không vào bảng logic, không chunk (dùng sau cho V-04). Nhãn khác (`formula`, `code`, `key_value_region`, `form`, …) → `unsupported_element` (chặn chunk của phần tử), không bị bỏ im lặng. Reader duyệt con của **mọi** phần tử (caption là con của picture/table, text trong hình là con của picture), không chỉ group | F54 trang 5–7: mục lục `document_index` từng bị bỏ im lặng; caption mọi trang từng thiếu (V-01 phát hiện) |

| T-17 | Xác nhận header/footer (2026-11-03, I-21) | Nhãn `page_header`/`page_footer` của Docling chỉ là gợi ý. Theo thứ tự: (a) con của picture (trừ caption) → body, `figure_text`; (b) phần tử trực tiếp trong body, nhãn `page_header`/`page_footer`/`text`, ở dải trên/dưới `furniture_band` (12% chiều cao trang), có khóa (chữ thường, tách chữ cái–chữ số, chữ số → `#`) lặp trên ≥ `furniture_min_pages` (3) trang → furniture (cờ `furniture_repeated`; Docling gắn body → thêm `furniture_promoted`); (c) chuỗi ghép hoàn toàn từ các khóa ở (b) → furniture (`furniture_composed`); (d) khớp toàn chuỗi một regex `furniture_patterns` của profile (mặc định rỗng) → furniture; (e) Docling gắn header/footer, không thuộc (b)–(d), là heading **mạnh** (từ khóa, hoặc số nhiều đoạn; số một đoạn như `320 mm` không đủ) → body, `heading`, cờ `furniture_demoted`, review `furniture_reclassified`; (f) còn lại do Docling gắn → giữ furniture, review `furniture_unconfirmed`. `section_header`/`title` không được đếm lặp (heading lặp như "Notes:" là nội dung). Không xóa phần tử nào | F86 OCR: 5 heading bị gắn `page_header`; footer `QS TECHNOLOGY CO.,LTD PAGE 4` gộp dòng; logo trong ảnh gắn `page_header` |
| T-18 | Nhãn sát hình (2026-11-03) | Chạy trong T-17, sau (b)–(d) (furniture thật thắng) và trước (e)–(f). Phần tử trực tiếp trong body, nhãn `text`/`page_header`/`page_footer`/`section_header`, thỏa đủ: ≤ `figure_label_max_tokens` (4) token; không kết thúc bằng dấu câu câu văn (`.`, `:`, `;`, `?`, `!`); không bắt đầu bằng từ khóa caption; không phải heading mạnh của T-07 (và `section_header` có số thì giữ là heading); không bắt đầu ở lề trái văn bản (± 3 pt; lề = x0 gặp nhiều nhất ở dòng `text`/`section_header`/`list_item` trong body, cần ≥ 3 dòng; thêm 2026-11-08, I-25: F54 `INDEX homing type`, `Model: F54 controller` ở x 85 là nhãn mục); tâm x nằm trong khoảng x của picture và khoảng cách tới bbox picture ≤ `figure_label_gap` (12 pt) → body, `figure_text`, `parent_element_id` = picture gần nhất, cờ `figure_text_attached`. Chỉ log, không review: unit hình được duyệt cả cụm. Chữ trong hình là từ khóa của hình, không vào text thân chunk, không thành fact | F86 trang 8: `320 mm` gắn `page_header` cách hình 3 pt; trang 9: `320 mm` là `text` đè mép hình — Docling không gắn vào picture |
| T-19 | Gộp phần tử hình trùng (2026-11-08, I-27) | Chạy sau T-09, T-10 và trước T-11, T-14. Hai phần tử hình (picture, screenshot; không phải `watermark_candidate`) cùng trang có IoU bbox ≥ `duplicate_iou_min` (0,9) → cùng một ảnh. Giữ: (1) phần tử Docling gắn caption; (2) không thì screenshot; (3) còn hòa thì phần tử đọc trước. Phần tử còn lại **không xóa**: cờ `duplicate_image`, `duplicate_of` = phần tử giữ, không crop, không nhận caption, không vào visual chunk; log `T-19`. Không review (bằng chứng hình học tuyệt đối). Chồng một phần → vẫn là hai hình | F54 trang 64, 81, 85, 96, 98: Docling sinh cả picture lẫn bảng 0 cell cho cùng một ảnh chụp màn hình (IoU 1,0, cùng một bitmap); trang 148 chồng một phần (IoU 0,47) không gộp |

Các biến đổi chạy theo thứ tự T-17 (gồm T-18) → T-16 → T-06 → T-07 → T-09, T-10, T-19,
T-11, T-14 → T-01…T-05 → T-15 → T-08 → T-12, T-13, sau đó chạy kiểm V-xx (§8). Hình chạy trước
bảng (sửa 2026-11-03): screenshot (T-09) không thành bảng rỗng, và caption gắn lại (T-11)
đổi điều kiện đóng bảng của T-03. Golden test kiểm từng biến đổi riêng
([p1_golden_tests.md](p1_golden_tests.md)).

## 6. Review queue

```json
{"item_id": "rq-0007", "element_id": "…:p169:e000", "code": "column_count_mismatch",
 "blocking": true, "blocks": "chunk", "detail": "segment has 3 docling cols, logical table 4",
 "suggested_action": "confirm inherited columns", "raw_ref": {…}}
```

| `code` | Khi nào | Blocking cho |
|---|---|---|
| `column_count_mismatch` | T-01: khe trắng không chia bảng thành đúng số cột Docling, đã dùng biên dự phòng | chunk |
| `unassigned_cell` | Tâm x của cell không thuộc cột nào, hoặc hai cell cùng cột trong một dòng | chunk |
| `unsupported_element` | T-16: nhãn Docling chưa có bộ chuẩn hóa | chunk (phần tử đó) |
| `empty_table` | Bảng Docling 0 cell mà T-09 không nhận là screenshot (không có bitmap phủ ≥ 0,8, hoặc thiếu `objects.json`) | không |
| `furniture_reclassified` | T-17 (e): header/footer của Docling là heading xuất hiện một lần, đã trả về body | không |
| `furniture_unconfirmed` | T-17 (f): header/footer của Docling không lặp, không phải heading; vẫn bỏ khỏi nội dung | không |
| `printed_page_conflict` | T-06: số in trên trang không khớp chuỗi số trang | không |
| `header_missing` | Bảng logic không có dòng header (`header_text=null`) | fact |
| `complex_header` | Bảng có ≥ 2 dòng header (ghép `" / "`) | chunk |
| `ambiguous_continuation` | Bảng không header ở đầu trang ngay sau bảng logic đang mở nhưng không thỏa điều kiện (1) hoặc (2) của T-03 | chunk |
| `header_demotion_unsure` | T-05 bước (d): không trùng header, không cùng hình dạng dữ liệu, không khớp mẫu profile | chunk |
| `orphan_row` | T-15 không gộp được dòng có cột khóa rỗng | chunk |
| `ocr_required` | S0: trang không có text layer hoặc text layer hỏng | chunk (trang đó) |
| `text_coverage_gap` | V-01 dưới ngưỡng | chunk (trang đó) |
| `table_crosscheck_mismatch` | V-02 lệch | chunk (bảng đó) |
| `column_type_inconsistent` | V-03 | chunk (bảng đó) |
| `applicability_model_unmatched` | T-13: điều kiện không khớp model hay interface nào trong registry (vd. "touch controller") | fact |
| `caption_ambiguous` | T-11: caption có từ khóa nhưng không có ứng viên, hoặc có 2 ứng viên cách đều (≤ 1 pt) | chunk (hình) |
| `watermark_conflict` | Ứng viên watermark có caption hoặc chồng lên hình thật | không |
| `param_unparseable` / `range_too_long` / `param_code_overlap` | §4 | fact |
| `applicability_note` | T-13 | fact |
| `list_orphan` | T-08: mục có glyph, thụt sâu hơn list khác cùng trang, đứng đầu khối list (không có cha) | fact |
| `list_level_ambiguous` | T-08: lề không khớp cấp list nào đang mở, hoặc thụt 3–18 pt không glyph (thêm 2026-11-09) | fact |
| `list_param_mismatch` | T-08 v1.1: list cha định nghĩa mã (`M1951:`), con là định nghĩa/giá trị của mã khác cùng prefix (`o M1950 = 0`); thường là lỗi soạn thảo của tài liệu, không đoán mã nào đúng (thêm 2026-11-09) | fact |
| `per_code_values` | §4 | fact |
| `doc_version_mismatch` | Header ≠ manifest | xuất bản (mức document) |
| `source_conflict` | Ghi nhận mâu thuẫn nguồn (người hoặc luật) | fact + xuất bản |

## 7. Hồ sơ tài liệu S0 (chạy trước Docling) — có code

Đo bằng pypdfium2 (`parse/profile_probe.py`, dùng lại `pdf_probe.py`), quyết định ở
`s0.py` (thuần Python), ghi `raw/profile.json` (`DocumentProfile`):

| Trường | Theo | Dùng để | Trạng thái |
|---|---|---|---|
| `text_chars` | trang | Số ký tự không phải khoảng trắng của text layer | có |
| `bad_char_ratio` | trang | Tỷ lệ U+FFFD / ký tự điều khiển | có |
| `text_layer` | trang | `missing` (`text_chars < ocr_min_chars`), `poor` (`bad_char_ratio > text_bad_char_max`), `ok` | có |
| `ocr`, `ocr_applied`, `docling_config` | trang | S0 đề nghị OCR; Docling có chạy OCR thật không; cấu hình Docling thực tế để chạy lại được | có |
| `rotation` | trang | Hiện chỉ ghi nhận; chuẩn hóa hướng chưa làm | đo, chưa dùng |
| `bitmap_area_ratio`, `vector_path_count` | trang | Hiển thị. Đối tượng từng trang (bitmap + px, nét vector) ghi riêng ở `raw/p{n}.objects.json` cho T-09, T-10, T-14. Ảnh trong Form XObject lấy bounds của form (sửa 2026-11-03: trước đó pdfium trả tọa độ cục bộ của form, F54 trang 18 bị ghi ở góc 0,720) | có |
| `page_label`, `page_labels_present` | trang / tài liệu | Nguồn (1) của T-06 | có |
| `lang_guess` | — | Chọn lexicon | chưa có |
| bitmap lặp | — | Ứng viên watermark: T-10 tính từ `objects.json`, không lưu trong S0 | có (T-10) |

Luật (chung, không theo tài liệu): text layer `missing`/`poor` → cần OCR. CLI
`--ocr auto|off|force` (mặc định `auto`): `auto` chỉ OCR trang S0 đề nghị; OCR dùng
RapidOCR backend torch (có sẵn trong `.venv-ingest`; backend mặc định onnxruntime chưa
cài), toàn trang, tiếng Anh. Docling/OCR lỗi → CLI dừng có thông báo, không chạy tiếp
mà thiếu OCR.

Trang cần OCR luôn có `ocr_required` (blocking chunk trang): text OCR không có nguồn độc
lập để V-01 đối chiếu (V-01 ghi `passed=null`, lý do "OCR page"), nên phải được người
duyệt xác nhận. `--ocr off` vẫn gắn cờ (nội dung trang bị thiếu). Ngưỡng tạm:
`ocr_min_chars=20`, `text_bad_char_max=0.1` (D-12).

## 8. Kiểm bất biến V-xx (chạy sau T-xx)

Kiểm **không cần biết loại lỗi**: so output chuẩn hóa với nguồn độc lập (text
layer PDF) và với các bất biến cấu trúc. Mỗi kiểm ghi một dòng
`validation.jsonl` `{check_id, target, score, threshold, passed, detail}`; không
đạt → mục review_queue.

| ID | Kiểm | Cách đo | Bắt được (ví dụ) |
|---|---|---|---|
| V-01 | Độ phủ text (**có code**, `validate/coverage.py`) | Từ text layer của trang (`p{n}.words.json`, pypdfium2), bỏ từ có tâm trong bbox furniture Docling, so multiset với token của phần tử pipeline giữ lại (T-16: có xử lý + chờ S1; cell bảng và mục lục): `coverage = phủ / token trang`, `duplicate = phần thừa / token giữ lại`. Token hóa: tách khoảng trắng, bỏ dấu câu hai đầu, casefold. Trang không có token text layer → `passed=null` (việc của S0). Đến khi có `NormalizedElement`, phía "giữ lại" là phần tử Docling đã phân loại | Nội dung bị bỏ (nhãn chưa hỗ trợ, caption không đọc), đoạn bị nhân đôi, vùng OCR hỏng. F54: 11/11 trang fixture đạt; trang 168–169 lệch nhẹ do Docling tách chữ số mũ (`1 st` vs `1st`) |
| V-02 | Đối chiếu bảng | Lấy từ của text layer trong vùng bảng kèm toạ độ, gom dòng theo y và cột theo biên cột của `LogicalTable`; so text từng ô | Đảo cột, mất cột, ô rơi sang dòng khác (I-01, I-02 dạng mới) |
| V-03 | Bất biến bảng | Mọi dòng đủ số ô; mỗi cột đồng nhất hình dạng token (độ thuần ≥ ngưỡng, bỏ ô rỗng); header không toàn số; không có dòng dữ liệu trùng hệt | Header lọt vào dữ liệu, cột bị trộn |
| V-04 | Cấu trúc trang | Element thiếu bbox; thứ tự đọc nhảy ngược trong cùng cột; tỷ lệ element `section_path_source=none` | Layout nhiều cột đọc sai thứ tự, tài liệu không đánh số mục |

Kết quả V-xx cộng với cờ T-xx thành `confidence` cho element và bảng logic; bước
gán knowledge unit (S4) dùng nó để đặt `risk_tier`. Unit chứa phần tử không đạt
V-xx luôn ở `pending_review`.

V-02 dùng cùng text layer với Docling (cell matching), nên **không** bắt được lỗi
text layer gốc (I-15); nó bắt lỗi gán cấu trúc.

## 9. Profile cấu hình

Profile là dữ liệu, không phải code (D-11). File YAML trong
`backend/app/modules/doc_ingest/profiles/`, nạp bằng `doc_ingest/profile.py`, schema
`schemas/profile.py` (`extra="forbid"`: key lạ bị từ chối). Pipeline chọn profile
theo manifest (`profile: default | qs_controller | …`), mặc định `default`.

| Khóa | `default` | `qs_controller` |
|---|---|---|
| `extends` | — | `default` (key của con thay nguyên giá trị; `thresholds` gộp theo khóa) |
| `code_patterns` | rỗng (T-05 chỉ dùng trùng header + hình dạng token) | `^#\d`, `^M\d{4}`, `^[XY]\d{2,3}$`, `^CN\d+$` |
| `param_prefixes` | rỗng (T-12 không parse mã) | `#`, `M` |
| `param_text_patterns` | rỗng (không quét mã trong text) | `#`: `\d{4,5}`, `M`: `\d{4}` |
| `applicability_lexicon` | cụm EN + VI, mỗi cụm kèm `status` (T-13) | kế thừa |
| `caption_keywords` | `Figure`, `Fig.`, `Hình`, `Table`, `Bảng` | kế thừa |
| `table_caption_keywords` | `Table`, `Bảng` (T-11: caption bảng; còn lại của `caption_keywords` là caption hình) | kế thừa |
| `section_keywords` | `PART`, `CHAPTER`, `Phần`, `Chương` | kế thừa |
| `list_glyphs` | `o`, `-`, `•`, `▪` | kế thừa |
| `vocabulary_file` | `registry_snapshot.json`: `product_models`, `aliases`, `control_interface` | kế thừa |
| `thresholds` | `continuation_tol=0.15`, `shape_majority=0.6`, `shape_min_rows=3`, `row_gap_factor=1.5`, `max_range_len=64`, `text_coverage_min=0.9`, `text_duplicate_max=0.1`, `furniture_band=0.12`, `furniture_min_pages=3`, `figure_label_gap=12`, `figure_label_max_tokens=4`, `crop_bitmap_min=0.5`, `crop_vector_margin=36`, `crop_padding=12`, `screenshot_bitmap_min=0.8`, `watermark_cover_min=0.9`, `duplicate_iou_min=0.9`, `list_indent_min=18` (ngưỡng V-01, T-17, T-18, T-14 là giá trị **tạm**, D-12 chốt trên F54 + F86) | kế thừa |

Ràng buộc:
- Luật T-xx đọc profile qua `Profile`; không luật nào có hằng số miền, không luật
  nào tự mở file YAML (GT-23 / PI-04 quét AST).
- Từ vựng registry (D-11, 11c): `doc_ingest` không import chatbot, nên
  `registry_snapshot.json` là bản chép của
  `chatbot/extraction/registry.py`; `tests/chatbot/test_registry_snapshot.py`
  (venv chính) fail khi hai bên lệch. Registry đổi thì sinh lại snapshot trong cùng
  commit.
- Hash profile (`profile_hash`) chỉ ghi vào `run_report.json` để truy vết, **không**
  nằm trong hash approval (D-11, 11d; sửa rev 2). Approval gắn `content_hash` +
  `evidence_hash` của unit (H-6): đổi profile mà output không đổi thì giữ approval;
  output đổi thì hash unit tự đổi.
- Mọi golden test chạy được với `default`; ca nào chỉ đạt với profile miền ghi rõ
  profile trong test (GT-04 parse mã: `qs_controller`).

## 10. Không thuộc lớp này

Các phần sau thuộc S2/S3/S4 của Ingestion V1:
- phân loại ngữ nghĩa (`pinout_table`, `parameter_table`…);
- trích fact;
- dựng chunk;
- gán knowledge unit.

Lớp chuẩn hóa chỉ đảm bảo đầu vào của các bước đó có cấu trúc đúng và có đủ
provenance.
