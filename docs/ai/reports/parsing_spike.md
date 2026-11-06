# P-1 Parsing Spike — F54 Operation Manual

Trạng thái: **bản nháp chờ người duyệt ký**. Cột "Claude" là đánh giá sơ bộ từ ảnh
overlay/crop; cột "Người duyệt" phải được điền trước khi khóa contract C1 (P0).

**Sửa đổi sau khi đối chiếu JSON Docling thô** (P-1 assessment):
- Trang 168 **không có header lặp lại**. Docling gắn cờ `column_header` cho dòng
  dữ liệu đầu `#4140 - #4147 | Axis type`.
- Cell trống bị bỏ ở trang 168 là **lành tính** (chỉ số cột vẫn đúng); khác với
  trang 169, nơi cả cột bị xóa.
- List cha–con trang 19 có cùng `level`.
- Bbox picture trang 9 hẹp hơn bitmap thật.

**Rev 2 (pipeline chung, 2026-11-02)**: các quyết định mục 1 (regex trang trong
manifest), mục 3.2 (sai số 6 pt) và mục 3.3 (danh sách mẫu mã) là luật rút từ
F54. Contract rev 2 thay bằng tín hiệu chung + profile cấu hình
([contract §0](p1_normalization_contract.md#0-nguyên-tắc-pipeline-chung-rev-2));
báo cáo này giữ nguyên làm bằng chứng spike.

Đánh giá tác động, contract chuẩn hóa và golden test:
- [p1_chunking_impact_assessment.md](p1_chunking_impact_assessment.md);
- [p1_normalization_contract.md](p1_normalization_contract.md);
- [p1_golden_tests.md](p1_golden_tests.md);
- [p1_implementation_backlog.md](p1_implementation_backlog.md).

## Phạm vi và cấu hình

| Mục | Giá trị |
|---|---|
| PDF | `F54_Operation Manual (English Version)_V.02.pdf` (171 trang vật lý) |
| Trang (pdf_page_index) | 9, 11, 14, 18, **19**, 40, 167–171 (thêm 19: trang có mẫu `M1920 = 0 : NC`) |
| Docling | 2.145.0 · docling-core 2.105.0 · pypdfium2 5.14.0 (venv `.venv-ingest`, CPU) |
| Pipeline | `do_ocr=False`, TableFormer `accurate`, `do_cell_matching=True`, `images_scale=2.0` |
| Crop | Docling (scale 2) + render lại bằng pdfium ở scale 2/3/4, crop `tight` và `pad` (12 pt) |
| Thời gian | 96 s cho 11 trang (2–12 s/trang; lần đầu thêm ~3 phút tải model) |
| Tool | `python -m app.modules.doc_ingest.spike.run_spike` (venv ingest, thư mục `backend`) |
| Output | `docs/ai/doc_ingest_spike/output/f54/` (gitignored): `index.html`, `p*_overlay.png`, `p*_tables.html`, `p*_pictures/`, `summary.json` |

**F86 chưa chạy**: PDF F86 (Installation + Operation Manual) đã có trong
`docs/ai/doc_ingest_spike/source/` (cập nhật 2026-11-02) nhưng chưa có output spike. Cần chạy lại với PDF F86 trước khi khóa
C1, đặc biệt để kiểm sơ đồ dạng **vector** (F54 không có trường hợp nào).

## Checklist theo trang

Ký hiệu: ✅ đạt · ⚠️ đạt nếu có luật sửa · ❌ sai, cần luật bắt buộc.

| Trang (in) | Nội dung | Bảng | Picture / caption | Claude | Người duyệt |
|---|---|---|---|---|---|
| 9 (2) | Dimension drawing | — | ✅ phát hiện; caption "Figure 3" gắn đúng; số đo 212/220/140/90/25/4-M4 đọc rõ ở scale 3–4 nhưng **chỉ có trong bitmap**, không có trong text layer; ⚠️ bbox Docling (x 89,7–526,4) hẹp hơn bitmap nhúng (x 54,8–561,7) nên crop theo bbox cắt một phần "4 - M4" | ⚠️ | |
| 11 (4) | Connector layout + bảng CN1–CN10 | ❌ **đảo cột** ở 10/10 dòng dữ liệu: header `Port \| Functions` nhưng dòng ra `Power supply \| CN1` | ⚠️ caption "Figure 5" bị gắn vào **bảng**, picture không có caption | ❌ | |
| 14 (7) | Bảng địa chỉ input X40–X57 + ghi chú | ✅ 17×3, header đúng | — ; 5 ghi chú ra `list_item` nguyên văn | ✅ | |
| 18 (11) | Sơ đồ NPN/PNP + bước cấu hình | ❌ ảnh chụp màn hình (Figure 15) bị nhận là `table` 0×0 | ✅ Figure 14 gắn đúng | ❌ | |
| 19 (12) | `M1920 = 0/1 : NC/NO` | — | — ; mỗi dòng giá trị là `list_item` riêng, có tiền tố glyph `o `; mô tả parameter ở bullet cha | ⚠️ | |
| 40 (33) | Sơ đồ output CN5 + Note + bảng Y40–Y45 | ✅ 7×3; cột Function là **tiếng Việt** | ✅ Figure 45 gắn đúng | ✅ | |
| 167 (160) | Bảng parameter (đầu) | ✅ 22×4, header đúng, dải `#0000 - #0007` nằm trọn một ô | — | ✅ | |
| 168 (161) | Bảng parameter (nối trang) | ❌ 32 dòng × 4 cột nhưng **không có header thật**: Docling gắn cờ `column_header` cho dòng dữ liệu đầu `#4140 - #4147 \| Axis type`; ⚠️ 29/32 dòng thiếu cell vì ô Work range trống thật (chỉ số cột các cell còn lại vẫn đúng) | — | ❌ | |
| 169 (162) | Bảng nối trang + bảng Spindle | ❌ bảng nối trang ra **3 cột** thay vì 4: cả cột "Work range" trống bị xóa khỏi cấu trúc (`num_cols=3`), giá trị Default rơi vào vị trí cột 3; ⚠️ không có header | — | ❌ | |
| 170 (163) | Bảng nối trang + bảng mới | ⚠️ bảng nối trang không có header | — | ⚠️ | |
| 171 (164) | Bảng nối trang (cuối) | ⚠️ không header; ô Work range trống giữ đúng chỗ | ❌ **watermark logo** bị nhận là `picture` | ⚠️ | |

## Phát hiện và quyết định đề xuất cho C1 / S1–S3

### 1. Số trang in (`printed_page`)
- PDF **không có `/PageLabels`** (kiểm cả 171 trang).
- Header/footer nằm ở lớp `FURNITURE`; `iterate_items()` mặc định chỉ trả `BODY`,
  nên phải gọi với `included_content_layers={BODY, FURNITURE}`.
- Footer có dạng `Page | N` ở mọi trang đã kiểm (pdf 9 → 2, pdf 169 → 162).
- **Quyết định**: `printed_page` = regex footer khai báo trong manifest
  (`printed_page_pattern: "Page\\s*\\|\\s*(\\d+)"`); không khớp → `null`. Không suy
  từ offset dù mẫu này đang lệch đều 7.

### 2. Phiên bản tài liệu
- Header ghi `Operation Manual (English Version)_V.01`, tên file ghi `V.02`.
- **Quyết định**: `doc_version` lấy từ manifest; S1 đọc header, nếu khác manifest thì
  ghi cờ `doc_version_mismatch` vào `parse_report.json` để người duyệt xác nhận.

### 3. Bảng: chỉ số cột của TableFormer không tin được
- Trang 11: `start_col_offset_idx` sai trong khi `bbox` của cell đúng (cell "CN1" có
  `l=127` nhưng `col=1`). Lỗi giữ nguyên ở cả 4 cấu hình (accurate/fast ×
  cell_matching on/off).
- Trang 169: cột trống toàn bộ bị bỏ, làm lệch cột của mọi dòng.
- Trang 168: cờ `column_header` gắn vào **dòng dữ liệu** đầu tiên. Cờ header của
  Docling sai theo cả hai chiều (thiếu ở 169–171, thừa ở 168), nên không dùng
  làm căn cứ duy nhất.
- Trang 168, 171: Docling bỏ cell của ô **trống thật** nhưng vẫn giữ đúng chỉ số
  cột của các cell còn lại. Lành tính khi lấp ô trống tường minh, khác với trang
  169 nơi cả cột bị xóa.
- **Quyết định** (S1, bắt buộc):
  1. Dựng `TableGrid` từ **bbox của cell**: gán cell vào cột theo khoảng x của cột
     header (hoặc theo cụm x nếu không có header), không theo `col` của Docling.
  2. Bảng không có hàng header và nằm đầu trang → coi là **nối trang** nếu bảng cuối
     trang trước có cùng biên x (sai số ≤ 6 pt); kế thừa header + khoảng x các cột.
  3. Dòng mang cờ header nhưng ô cột đầu khớp mẫu mã (`#…`, `M…`, `X/Y…`, `CN…`)
     trong khi bảng logic đã có header → hạ thành dòng dữ liệu (T-05).
  4. Cờ review: `column_order_repaired`, `empty_column_restored`,
     `header_inherited`, `header_flag_demoted`, `column_count_mismatch`.
  5. Test S1 bắt buộc có ca trang 11, 168 và 169.

### 4. Ảnh chụp màn hình bị nhận là bảng
- Trang 18: Figure 15 (màn hình USER của bộ điều khiển) ra `table` 0×0, phủ bởi ảnh
  bitmap.
- **Quyết định** (S2): `table` có 0 cell và vùng phủ bitmap ≥ 0,8 →
  `semantic_type=screenshot`, xử lý như picture (crop + asset), giữ caption.

### 5. Watermark
- Ảnh bitmap 242×154 pt (671×427 px) xuất hiện trên **mọi trang**; trang 171 Docling
  nhận nó là `picture`.
- **Quyết định** (S1): bitmap cùng kích thước xuất hiện ≥ 3 trang → `noise`; picture
  không caption mà bbox trùng watermark → `noise`. Watermark chồng lên các hình thật
  (trang 9) không ảnh hưởng tới độ đọc số đo.

### 6. Caption
- Gắn đúng ở trang 9, 18, 40. Sai ở trang 11 (caption "Figure 5" bị gắn vào bảng).
- **Quyết định** (S1): caption bắt đầu `Figure` gắn vào picture gần nhất phía trên
  (cùng trang); `Table` gắn vào bảng. Gắn lại khác với Docling → cờ `caption_relinked`.

### 7. Độ phân giải và crop ảnh
- Mọi hình F54 trong mẫu là **bitmap nhúng** (`bitmap_overlap` ≈ 1, 0 path vector),
  độ phân giải gốc 2,2–3,06 px/pt.
- Scale 3 đã chạm độ phân giải gốc; scale 4 chỉ phóng to (crop 1 hình ≈ 100 KB ở
  scale 4, 65 KB ở scale 3).
- Crop `tight` theo bbox Docling **cắt mất nhãn ở mép** (trang 9). Nguyên nhân:
  bbox picture hẹp hơn bitmap nhúng khoảng 35 pt mỗi bên. Trang 11, 18, 40 chỉ
  lệch ≤ 2 pt.
- **Quyết định**: vùng crop = hợp của bbox Docling với bounds các bitmap nhúng phủ
  ≥ 50% bbox, cộng padding 12 pt; `original` = render pdfium ở
  `max(3, native_px_per_pt)` (trần 4); `preview` = scale 2, rộng tối đa 1600 px. Đường
  `page_render_crop` (pdfium) dùng cho **mọi** hình, không chỉ fallback, vì cho kết
  quả giống crop Docling nhưng chủ động được scale và padding. Kết luận cho sơ đồ
  vector còn chờ F86.

### 8. Section path
- Docling gán mọi `section_header` `level = 1`; các nhãn như `Note:`, `Notes:`,
  `How to configure the parameter from 0 to 1:`, `Parameter stauts description:`
  cũng là `section_header`.
- **Quyết định** (S1): `section_path` dựng từ mẫu đánh số (`PART n`, `n.n`, `n.n.n`)
  và mang trạng thái **qua các trang** (bảng ở trang 168–171 không có heading);
  header không đánh số → `label_heading` của element, không vào path.

### 9. Mã parameter và giá trị (cập nhật C2/B1)
- Dạng mã gặp thực tế:
  - đơn: `#0104`, `M1920`;
  - dải: `#0000 - #0007`, `#12200 - #12207`;
  - **danh sách**: `#8030, #8032 #8034, #8036` (dấu phẩy và khoảng trắng, xuống dòng).
- `parse_param_ref` phải trả **tập mã** (đơn | dải | danh sách). Đã chốt ở D-01
  ([contract §4](p1_normalization_contract.md#4-tham-chiếu-parameter-d-01-đã-chốt)):
  khớp **chỉ** qua `param_codes int[]` tường minh; `param_range_start/end` chỉ để
  mô tả.
- Danh sách mã có thể đi với **giá trị theo từng mã**: `#8150, #8152 #8154 →
  1000/5000/10000` (trang 168). Giữ nguyên văn + cờ `per_code_values`.
- Dạng giá trị:
  - `0:Disable - 1:Enable`;
  - nhiều dòng `0: Disable 1: 0→10V 2: 0→±10V`;
  - khoảng `0 → 10`, `0 – 999999`;
  - mặc định có chú thích `5 (= 50%)`.
- Mô tả có **điều kiện áp dụng**: `(Not available on F54 controller)`,
  `(Available on touch controller)`.
- **Quyết định**: thêm cột `applicability_note` cho fact + cờ review
  `applicability_note`. Câu trả lời không được nói parameter "có trên F54" khi note
  ghi "Not available on F54".

### 10. Text fact (trang 19)
- Mỗi dòng `M1920 = 0 : Normally closed sensor (NC)` là một `list_item`. Text có
  tiền tố glyph `o ` của bullet con; bullet cha `M1920: Homing sensor status
  configuration parameter for X axis` chứa mô tả.
- Docling gán **cùng `level=2`** cho cha và con. Chỉ phân biệt được bằng thụt lề x
  (103 pt so với 139 pt) và glyph `o` → cần T-08.
- Text layer gốc thiếu `)` ở `(NC` của M1921–M1923.
- **Quyết định** (S3): regex cho phép tiền tố bullet; gộp bullet con vào
  `value_options` của mã ở bullet cha (cùng trang, liên tiếp). `text_span.quote`
  lấy **nguyên văn** kể cả lỗi chính tả; nhãn chuẩn hóa (nếu sửa) do người duyệt
  ghi riêng.

### 11. Ngôn ngữ
- Trang 40: cột Function của bảng output là tiếng Việt trong manual tiếng Anh.
- **Quyết định**: `ElementRecord.lang` theo từng element (heuristic dấu tiếng Việt,
  dùng lại `guess_reply_language` nếu phù hợp), không chỉ theo manifest.

## Trường ElementRecord xác nhận có thật

| Trường | Nguồn | Ghi chú |
|---|---|---|
| `pdf_page_index` | `prov[0].page_no` | |
| `printed_page` | footer FURNITURE + regex manifest | không có `/PageLabels` |
| `source_element_type` | `label` (section_header, text, list_item, table, picture, caption, page_header, page_footer) | không thấy `formula`, `footnote` trong mẫu |
| `bbox` | `prov[0].bbox.to_top_left_origin` (pt) | |
| `reading_order` | thứ tự `iterate_items` | |
| `text` | `TextItem.text` | nguyên văn text layer |
| `table` | dựng lại từ `table_cells[].bbox` (không dùng `grid`) | xem mục 3 |
| `caption_element_id` | `captions` của Docling + luật mục 6 | |
| `image` | crop pdfium (mục 7) | |
| `content_layer` | `body` / `furniture` | mới, để tách header/footer |
| `level` của heading | **không dùng** | luôn = 1 |

## Việc còn lại trước khi khóa C1

1. Chạy lại spike với PDF F86 (đặt vào `docs/ai/doc_ingest_spike/source/`): connector
   map, một trang pinout, bảng `#0000-#0007`, một wiring diagram.
2. Người duyệt điền cột "Người duyệt" ở bảng checklist và xác nhận các quyết định
   mục 1–11.
3. Cập nhật plan (C1/C2/B1) theo mục 3, 4, 9 trước khi viết schema.
