# P-1 — Đánh giá tác động lên chunking và ingestion

Phạm vi: đánh giá kết quả Parsing Spike F54 ([parsing_spike.md](parsing_spike.md)),
xác minh hành vi chunking hiện có bằng code và baseline F86, đề xuất lớp chuẩn hóa,
quality gate, mô hình Human-in-the-loop (HITL) và quyết định GO/HOLD.

Tài liệu đi kèm:
- [p1_normalization_contract.md](p1_normalization_contract.md);
- [p1_golden_tests.md](p1_golden_tests.md);
- [p1_implementation_backlog.md](p1_implementation_backlog.md).

Bước này **không** đổi code, SQL, dữ liệu hay runtime. Mọi số liệu dưới đây lấy
từ JSON Docling thô (`docs/ai/doc_ingest_spike/output/f54/p*.json`, gitignored)
hoặc từ repo, bằng các lệnh chỉ đọc ở [Phụ lục A](#phụ-lục-a--lệnh-xác-minh-chỉ-đọc).
Báo cáo spike **không** được coi là bằng chứng dữ liệu đã đúng.

## Phân định phạm vi

| # | Phạm vi | Trạng thái |
|---|---|---|
| 1 | P-1 assessment (tài liệu này) | Đang thực hiện; chỉ tạo tài liệu |
| 2 | Ingestion V1: pipeline offline → gói xuất bản đã duyệt | Đề xuất ở [backlog](p1_implementation_backlog.md); duyệt riêng |
| 3 | Production integration: staging Supabase, runtime, SSE, chatbot | Chưa lên kế hoạch; chỉ bắt đầu sau khi V1 đạt nghiệm thu |

Những thứ đã có từ lượt chạy spike là **công cụ đo**, không phải pipeline V1:
- `backend/app/modules/doc_ingest/spike/`;
- `backend/requirements-ingest.txt`;
- venv `.venv-ingest`;
- các mục trong `.gitignore`.

## 1. Đánh giá tác động

Mức độ:
- **P0**: có thể sinh chunk hoặc fact **sai kỹ thuật mà không báo**;
- **P1**: thiếu nội dung, trích dẫn sai, nhiễu khi truy xuất, hoặc mất hình;
- **P2**: chất lượng hoặc hiệu năng.

Loại vấn đề:
- **NGUỒN**: chất lượng tài liệu nguồn;
- **PARSE**: phân tích và chuẩn hóa;
- **CHUNK**: xây chunk;
- **FACT**: trích dữ liệu có cấu trúc;
- **ASSET**: trích và truy xuất hình.

Ảnh hưởng tới: T = text retrieval, F = tra cứu fact có cấu trúc, A = truy xuất
hình, C = trích dẫn.

| ID | Vấn đề (bằng chứng) | Loại | Stage | Sai kỹ thuật? | Ảnh hưởng | Mức | Phải xử lý trước |
|---|---|---|---|---|---|---|---|
| I-01 | Trang 11: `start_col_offset_idx` sai trong khi bbox đúng; 10/10 dòng dữ liệu bị đảo `Port`↔`Functions`. Lỗi giữ nguyên ở cả 4 cấu hình TableFormer | PARSE | S1 bảng | **Có**: CN↔chức năng đảo; connector catalog (alias "tay quay"→CN3) dựng từ bảng này sẽ sai | T F C | **P0** | C1 |
| I-02 | Trang 169 bảng đầu: **cả cột** "Work range" trống bị xóa khỏi cấu trúc (`num_cols=3`); giá trị Default rơi vào vị trí cột 3 | PARSE | S1 bảng | **Có**: ghép header 4 cột thì Default bị đọc thành Work range | F T | **P0** | C1 |
| I-02b | Trang 168: 29/32 dòng thiếu cell vì ô Work range **trống thật**; chỉ số cột của các cell còn lại **đúng** | PARSE (lành tính) | S1 bảng | Không, nếu lấp ô trống tường minh | — | P2 | sinh chunk |
| I-03 | Cờ header của Docling sai **cả hai chiều**: trang 168 gắn `column_header` cho dòng dữ liệu `#4140 - #4147 \| Axis type`; trang 169/170/171 bảng nối trang không có header | PARSE | S1 bảng | **Có**: một dòng parameter thành header, mất dòng dữ liệu, sai nhãn cột | F T | **P0** | C1 |
| I-04 | Bảng nối trang không lặp header (169 t0, 170 t0, 171 t0) | NGUỒN + PARSE | S1 → S4 | **Có**, nếu chunk dòng thiếu header (không biết "0" là Default hay Work range) | T F | **P0** | sinh chunk |
| I-05 | Mã dạng danh sách `#8030, #8032 #8034, #8036` (trang 169), `#8150, #8152 #8154` (168); F86 cũng có (`#8150, #8152, #8154`) | NGUỒN / contract | C2, S3, B1 | **Có**: lưu thành dải 8030–8036 sẽ khớp nhầm `#8033` | F | **P0** | C1 (đã chốt D-01) |
| I-06 | Ghi chú áp dụng: `#0136 OPK.DISA (Not available on F54 controller)`, `#4132–#4134 (Available on touch controller)`; F86 cũng có `availability_note` | NGUỒN | S3, B4 | **Có**: trả lời parameter "có trên F54" | F T | **P0** | trích fact (field ở C1) |
| I-07 | Trang 19: list cha `M1920: …X axis` và list con `o M1920 = 0 : …` cùng `level=2`; chỉ phân biệt bằng thụt lề x (103 vs 139 pt) và glyph `o` | PARSE | S1 list → S3 | **Có**: `value_options` gắn nhầm parameter khi ghép theo thứ tự | F | **P0** | C1 (field) / trích fact. **Xử lý 2026-11-09** bằng T-08 v1: 4 cha × 2 con đúng (GT-07); toàn F54 103 con, 0 mồ côi |
| I-08 | Trang 18: ảnh chụp màn hình (Figure 15) ra `table` 0×0, phủ bởi bitmap | PARSE | S1/S2 | Không; mất hình + caption | A C | P1 | sinh chunk. **Xử lý 2026-11-03** (T-09): `screenshot` có caption; ảnh nằm trong Form XObject, bounds bitmap trước đó đo sai |
| I-09 | Watermark 242×154 pt (671×427 px) xuất hiện mọi trang; trang 171 nhận là `picture` | NGUỒN + PARSE | S1 | Không; asset rác có thể bị trả về như "hình minh họa" | A | P1 | sinh chunk. **Xử lý 2026-11-03** (T-10, điều kiện sửa thành phủ picture ≥ 0,9): trang 171 → `watermark_candidate`, không xóa |
| I-10 | Trang 11: caption "Figure 5" gắn vào **bảng**, picture không có caption | PARSE | S1 | Không; visual chunk mất tiêu đề | A C | P1 | sinh chunk. **Xử lý 2026-11-03** (T-11): caption chuyển sang picture, cờ `caption_relinked` |
| I-11 | Trang 9: bbox picture của Docling (x 89,7–526,4) hẹp hơn bitmap nhúng (x 54,8–561,7) khoảng 35 pt mỗi bên; crop theo bbox cắt mất nhãn "4 - M4". Số đo 212/220/140/90/25 **chỉ có trong bitmap**, không có trong text layer | ASSET + FACT | S1 ảnh, S3 | Có thể: bản vẽ mất nhãn; fact kích thước F54 **chỉ** tạo được bằng `human_verified_figure` | A F | P1 | xuất asset; fact `spec`. **Crop xử lý 2026-11-03** (T-14): vùng crop phủ bitmap, ảnh render có "4 - M4"; fact kích thước vẫn chỉ qua `human_verified_figure` |
| I-12 | Mọi `section_header` có `level=1`; nhãn "Note:", "Notes:", "Parameter stauts description:" cũng là section_header | PARSE | S1 section | Không; breadcrumb, embedding, trích dẫn sai | T C | P1 | C1 (ngữ nghĩa field) |
| I-13 | Không có `/PageLabels`; trang in chỉ đọc được từ footer `Page \| N` (lớp FURNITURE) | NGUỒN | S1 | Không; trích dẫn trang | C | P1 | C1 |
| I-14 | Header ghi `…_V.01`, tên file ghi `V.02` | NGUỒN | quality gate | Không xác định được version nào đúng | C | P1 | xuất bản (mức document) |
| I-15 | Text layer lỗi: `(NC` thiếu `)` ở M1921–M1923; "stauts", "federate" | NGUỒN | S3 evidence | Không, nếu evidence giữ nguyên văn | F C | P2 | chính sách |
| I-16 | Trang 40: cột Function bảng Y40–Y45 là tiếng Việt trong manual tiếng Anh | NGUỒN | S1 lang | Không | T | P2 | C1 (field rẻ) |
| I-17 | Hình F54 trong mẫu đều là bitmap nhúng, độ phân giải gốc 2,2–3,06 px/pt | NGUỒN | S1 ảnh | Không | A | P2 | — |
| I-18 | F86 Operation Manual đã chạy trang 1–17 qua CLI (2026-11-03, không phải spike đầy đủ BL-13); sơ đồ vector chưa đánh giá | thiếu dữ liệu | S1 ảnh | Chưa rõ | A | P1 | duyệt S1 phần hình |
| I-20 | F86 Operation Manual **không có text layer** (0 ký tự ở mọi trang đo; chữ vẽ bằng bitmap/path). Không OCR thì Docling chỉ nhận picture, mất toàn bộ heading, caption, text; báo cáo trước S0 ra 0 review (rỗng nhưng trông sạch) | NGUỒN | S0 | **Có**: tài liệu không có nội dung | T F A C | **P0** | xử lý bằng S0 + OCR (BL-24); mọi trang `ocr_required` |
| I-21 | Trang OCR: heading đầu trang bị Docling gắn `page_header` → coi là furniture, rơi khỏi nội dung (F86 trang 7 `1.1 APPERANCE`, 8 `1.2 DIMENSION`, 11 `CHAPTER 2.`, 12 `2.1 POWER SUPPLY`, 17 `2.3.3 6-WIRE-NPN TYPE`). V-01 không bắt được vì trang OCR không có nguồn độc lập | PARSE | S1 furniture (T-06/T-07) | **Có**: mất heading, section path sai | T C | **P0** | **Xử lý 2026-11-03** bằng T-17: 5/5 heading trả về body (`furniture_reclassified`, không chặn), section path đúng; `QS TECHNOLOGY CO.,LTD`, `PAGE n` xác nhận furniture tự động |
| I-22 | Bảng vẽ bằng hình (F86 trang 15 `2.2.3 F86 CONTROLLER INPUT CONNECTION TABLE`) được nhận là picture; TableFormer không chạy nên không có cấu trúc bảng | NGUỒN + PARSE | S2 / bảng | **Có**: mất bảng I/O | F T | P1 | trích fact F86 |
| I-23 | Lỗi OCR: số trang mục lục sai (`2.8.1 PNP WIRING .. 37` so với 31), dính chữ (`2.9.1AXIS`), footer `PAGEO`/`PAGE3`, heading rác từ sơ đồ (`i-    ns    dpn`), chữ trên sơ đồ OCR thành 60–90 text/trang (con của picture) | PARSE (OCR) | S0, T-06, T-07 | **Có** nếu không duyệt | T C | P1 | xuất bản (đã chặn bằng `ocr_required`). 2026-11-03: chữ trong hình → `figure_text` (không vào text thân, không làm heading); `PAGEO` → trang in `null` + `furniture_unconfirmed`; `PAGE3` đọc đúng |
| I-24 | F54 chạy đủ 171 trang (2026-11-03, run `20261103-144432`): ảnh chụp màn hình giao diện cùng kích thước 480×272 px, hiển thị cùng cỡ 360×204 pt trên 29 trang (và 226×128 pt trên 18–23 trang) bị T-10 coi là "bitmap lặp". Kết quả: 7/15 `watermark_candidate` là screenshot thật (trang 64, 81, 85, 96, 98, 136, 137) và 7/8 `watermark_conflict` là screenshot có caption. 8 watermark thật (671×427 px, trang 7, 27, 57, 106, 132, 142, 164, 171) đúng (đếm lại 2026-11-08; bản ghi trước tính nhầm 106, 132, 142 là screenshot) | LUẬT (T-10) | S1 hình | **Có**: ứng viên watermark bị loại khỏi visual chunk → mất ảnh giao diện | A | **P0** | sinh chunk (hình). **Xử lý 2026-11-08**: T-10 nhận lặp bằng cùng `hash` nội dung + cùng vị trí; F54 còn 8 `watermark_candidate` đều là watermark thật, 7 screenshot trở lại picture, `watermark_conflict` 8 → 1 (trang 160, mảnh nhỏ trong watermark chồng ảnh khác) |
| I-25 | T-18 gắn nhầm nhãn mục ngắn đứng ngay trên hình: F54 trang 80 `INDEX homing type` (nhãn mục giống `DOG ON/DOG OFF homing type` cùng trang) → `figure_text`, mất `label_heading` cho phần sau. `Model: F54 controller` (7 trang) đứng trên screenshot cũng bị gắn — chấp nhận được vì là tiêu đề màn hình | LUẬT (T-18) | S1 hình | Có: nhãn mục bị mất | C | P1 | sinh chunk. **Xử lý 2026-11-08**: T-18 không gắn dòng bắt đầu ở lề trái văn bản; F54 8 nhãn → `label_heading`; F86 7 nhãn hình vẫn gắn |
| I-26 | `PART 1:CONTROLLER OVERVIEW` (F54 trang 8, không có khoảng trắng sau `:`) không khớp mẫu heading từ khóa → `label_heading`; chương 1.1–1.3 thiếu cha `PART 1` (các PART 2–5 đúng) | LUẬT (T-07) | S1 section | Có: section path chương 1 thiếu cấp PART | C | P1 | sinh chunk. **Xử lý 2026-11-08**: mẫu từ khóa cho phép tiêu đề dính sau `:`; 1.1–1.3 nằm dưới `PART 1:CONTROLLER OVERVIEW`, `section_parent_missing` 16 → 13 |
| I-27 | Docling sinh **hai** phần tử cho cùng một ảnh chụp màn hình: một `picture` và một `table` 0 cell trùng bbox (F54 trang 64, 81, 85, 96, 98). T-09 biến bảng thành `screenshot`, nên mỗi ảnh có hai phần tử hình và hai ảnh crop; caption gắn vào screenshot (T-11 giữ liên kết Docling khi hòa) | PARSE | S1 hình | Có: visual chunk / unit hình bị nhân đôi | A | P1 | sinh chunk (hình). **Xử lý 2026-11-08** bằng T-19: 5 picture trùng → `duplicate_image` + `duplicate_of` trỏ về screenshot (giữ caption), không crop; ảnh render 247 → 242; trang 148 (chồng một phần) giữ nguyên; caption, review, hash bảng, V-01 không đổi |
| I-28 | F10T (tài liệu scan, bố cục bảng hai cột: ảnh giao diện bên trái, hướng dẫn "Bước 1…" bên phải): Docling nhận **cả khung trang** là một `picture` (vd. trang 64: 35–577 × 50–746 pt), nên hướng dẫn thân bị xếp thành `figure_text` và mất khỏi chunk. 17 trang có picture ≥ 50% trang chứa câu văn; chữ trong hình 53.932 ký tự so với chữ thân 20.916 | PARSE | S1 hình | **Có**: mất nội dung hướng dẫn | C | **P0** (cho tài liệu dạng này) | sinh chunk. Phát hiện bằng tín hiệu `picture_swallows_text` (B1) và nhãn mẫu (nội dung thân 0/4). Chưa sửa: cần quyết định hướng (tách picture theo bitmap thật, hoặc trả câu văn trong picture lớn về body) |
| I-29 | OCR chạy RapidOCR ngôn ngữ `en` cho tài liệu tiếng Việt (F10T, tên file ghi "English Version" nhưng nội dung tiếng Việt): mất dấu (`CHẾ ĐỘ MDI` → `CH Đ MDI`, `Đầu tiên nhấn` → `Đu tiên nhn`), OCR đọc `0` thành `o` (`#1401o`) | PARSE (cấu hình OCR) | S0, OCR | **Có**: nội dung sai chính tả, mã bị loại | C | **P0** (cho tài liệu tiếng Việt scan) | sinh chunk (đã chặn bằng `ocr_required`). Phát hiện bằng `ocr_lang_mismatch`, `near_miss_high`. Chưa sửa: cần chọn mô hình OCR tiếng Việt (có thể là dependency mới → phải hỏi) |
| I-30 | T-12 trên text nhận `M0100` trong `"M0100.txt"` (F10T trang 90, tên chương trình macro = M-code 4 chữ số có số 0 đầu) là parameter: 3 FP | LUẬT (T-12 text) | S1 mã | Có thể: fact parameter M100 giả | F | P1 | trích fact. Phát hiện bằng nhãn mẫu (precision OCR 0,5). Chưa sửa: đề xuất loại token theo sau là phần mở rộng tệp (`.txt`) hoặc `M` có số 0 đầu trong profile `qs_controller` — cần duyệt |
| I-31 | F86 Installation trang 2 là mục lục (dòng có dấu dẫn `.....` / `……` và số trang) nhưng T-16 không nhận: dòng đầu thành `heading`, các dòng còn lại thành `text`, `section_path` của cả trang là "PART 1 - OVERVIEW OF CONTROLLER ......3". Builder sinh 1 chunk overview 1.730 ký tự, gắn cờ `toc_like` (ghi nhận 2026-11-09 khi chạy BL-16) | LUẬT (T-16) | S1 nhãn | **Có**: chunk rác, `section_title` rác | C | P1 | xuất bản (chunk mang cờ `toc_like`, người duyệt loại). Chưa sửa: đề xuất T-16 nhận trang có ≥ 50% dòng kết thúc bằng dấu dẫn + số |
| I-32 | F86 Installation bảng cổng `t001`: ô mô tả lệch dòng. Phần "D- : Reverse differential signal - FG : …" của CN2 nằm ở dòng CN3; "range : 420mA …" (nguyên văn trích xuất) của CN3 nằm ở dòng CN4 (xem `tables.jsonl` r4–r6). Chỉ 3 dòng có review `orphan_row`, các dòng lệch này không có review | PARSE/LUẬT (Docling cell + T-02/T-15) | S1 bảng | **Có**: chunk `pinout` gán mô tả cho sai cổng | C | **P0** (cho bảng cổng) | sinh chunk. Phát hiện khi so với chunk viết tay. Chưa sửa: cần so với PDF, xem lại ghép dòng khi ô mô tả nhiều dòng |
| I-33 | Chunk hình không có caption chỉ có tiêu đề mục làm `content` (F86 Installation: 12/24 chunk lá, vd. "2.2 INPUT LOW DIAGRAM"); chunk viết tay tương ứng có mô tả chân/dây do người viết. Độ chứa token so với chunk tay 0,04–0,17 | C2 (giới hạn nguyên văn) | build | Có thể: embedding yếu, khó tìm | R | P1 | tra cứu. Hướng: nhãn OCR trên ảnh crop vào từ khóa (lệnh `figure-ocr`), tóm tắt tiếng Việt Bước 3 từ tiêu đề + nhãn; số liệu chân/dây chỉ từ fact người duyệt (§8.1) |
| I-34 | Bảng cổng được chia theo nhóm dòng ≤ 2.500 ký tự (F86: 4 phần ~2.200 ký tự); chunk viết tay chia theo từng cổng (CN1, CN5, …) | C2 (độ hạt bảng) | build | Có thể: câu hỏi về một cổng nhận chunk dài, xếp hạng kém | R | P2 | tra cứu. Đề xuất đo ở Bước 4: nhóm dòng nhỏ hơn (≤ 1.200) cho bảng `pinout` |
| I-35 | Luật loại ngữ nghĩa theo tiêu đề còn thô: F54 2.3.3 (ảnh thiết bị) thành `wiring` vì câu "wiring diagram below"; F86 2.1 ghi chú vị trí cổng thành `wiring` theo tiêu đề mục; F86 2.8 "POWER CONNECTION" thành `figure`. Đúng loại trên nhãn nháp: F54 0,9, F86 0,71 | LUẬT (profile `chunk_type_rules`) | build | Không (retrieval không dùng `chunk_type`; ảnh hưởng nếu làm S-04) | R | P2 | chỉ khi dùng `chunk_type` để lọc/boost (C2 §13 S-04). **Một phần 2026-11-11**: label heading dạng bước được đếm là một bước, nên khối "Step 1:" + dòng "Step 2: …" là `procedure` (F54 4.2.1, 4.2.3, 4.5.3, 3.5); các ca theo tiêu đề còn nguyên |
| I-36 | I-28 xảy ra cả trên trang **có text layer** của F54: Docling nhận khung cột "Instructions" (bố cục hai cột "Description images \| Instructions", PART 3–4) là `picture`; chữ text-layer bên trong thành `figure_text` và bị loại khỏi chunk. 39 đoạn hướng dẫn (~3.000 ký tự) trên 23 trang PDF (101, 108, 115–121, 123, 126, 128, 135, 138–140, 143–146, 152, 153, 158). Chunk mất Step: B0212, B0228, B0244, B0245, B0246, B0250, B0255, B0258, B0273, B0294, B0302, B0304, B0310 (+ 5 cha). Độ phủ vẫn báo 1,0 vì `figure_text` thuộc nhóm loại trừ | PARSE (Docling layout) + LUẬT (`figure_text`) | S1 picture, build | **Có**: thủ tục thiếu bước, câu bị cắt | C | P0 | sinh chunk. Phát hiện khi duyệt tay cổng 2b (2026-11-10). **Xử lý 2026-11-11 (trang text layer)**: luật T-20 "khung chữ" (contract P1) trả chữ của khung về text thân; tiêu đề khung giữ là chữ trong hình, caption bước thành text theo thứ tự đọc. Run `f54/eval-c`: 22 khung, 84 phần tử; đúng 13 mục đổi, mọi mục có đủ Step (vd. 4.3.3 Step 1–4, 3.3.4 Step 1–5); CQ-01…CQ-10 đạt, BL-34 vẫn đạt; F86 Installation/Operation, F10T: 0 khung. Trang OCR (I-28) chưa áp dụng |
| I-37 | Chunk gần rỗng trên F54: tiêu đề khung "Model: F54 controller" (8 chunk cùng hash), "Instructions / Model: F54" (2), heading + nhãn "1.1 Overview / Specification:" (B0004, tách khỏi bảng B0005), trang bìa (B0001), 1 dòng mục lục lọt (B0003). Ảnh khung "Description images" thành chunk hình chỉ có tiêu đề mục, tách khỏi chunk "Instructions" cùng mục (13 chunk; liên quan I-33) | LUẬT (chunker: R-04, R-06; T-16) | build | Có thể: chunk không mang thông tin chiếm chỗ top-k | R | P1 | tra cứu. Đề xuất: gộp nhãn khung/ảnh vào chunk hướng dẫn cùng mục; label heading trước bảng thành dòng dẫn của bảng; không sinh chunk cho trang bìa và dòng mục lục. **Xử lý 2026-11-11** (run `f54/eval-d`): T-20 gắn nhãn khung không được gom vào hình (21 cặp "Instructions / Model: …", 9 dòng model trên hình); T-16 nhận dòng và tiêu đề mục lục ngoài `document_index`; R-04 thêm dòng dẫn ":" trước bảng và khối tiêu đề + hình không caption gộp vào khối cùng mục; R-02 nối khối thủ tục không nhãn với chuỗi bước. 34/34 chunk `fix` của I-37 không còn; F54 342 → 296 chunk. Trang bìa gộp vào chunk lời giới thiệu (mang `ocr_required`). Còn lại: I-42 |
| I-38 | Bảng tham số 5.1, 5.2 chia theo 2.500 ký tự nhưng vượt `embed_max_tokens` 800 (B0318 797, B0319 779, B0321 771 token sau khi cắt) → đuôi bảng không vào `embed_text`; phần 3/3 của 5.1 chỉ còn 1 dòng (B0320) | LUẬT (chunker bảng) | build | **Có**: mã ở cuối phần không tìm được qua vector/FTS | R | P1 | tra cứu. Đề xuất: chia phần bảng theo token của `embed_text` và cân số dòng giữa các phần. **Xử lý 2026-11-11** (run `f54/eval-e`): chia phần theo ngân sách `embed_max_tokens` − `embed_enrich_reserve` (800 − 150) ở ranh giới dòng, cân chi phí giữa các phần, CQ-11 chặn cổng khi chunk bảng còn bị cắt. Bảng 5.1: 5 phần 13–15 dòng (545–569 token); 5.2: 2 phần; 5.3: 2 phần; 0 chunk `embed_truncated`. F86 Installation bảng cổng 2.1: 3 → 6 phần (392–529 token) |
| I-39 | `block_split` cắt giữa ví dụ tính tỷ số bánh răng điện tử (B0121 → B0122, mục 2.6.4.7): kết luận tách khỏi công thức; bullet là glyph `` | LUẬT (chunker) + PARSE (glyph) | build | Có thể: chunk kết luận thiếu ngữ cảnh | R | P1 | tra cứu. Đề xuất: tách theo nhãn "Case"/"Example" thay vì theo phần tử; chuẩn hóa glyph bullet vùng Private Use. **Xử lý 2026-11-12** (run `f54/eval-f`, C2 R-12): khối dài có đầu phần chỉ chia ở đầu phần, phần sau lặp tiêu đề `(phần i/n)` + công thức dẫn; glyph Private Use đầu dòng render thành `- `. Mục 2.6.4.7: 2 phần (Case 1–2: 551 token; Case 3 + kết luận: 410 token). Liên kết khi tra cứu: retriever không kéo chunk láng giềng nên mỗi phần phải tự đủ nghĩa; mở rộng láng giềng ở retriever chỉ cân nhắc nếu Bước 4 cho thấy cần |
| I-40 | Ghi nhận khi duyệt tay F54 (không chặn cổng): (a) hình + caption Figure 52 (trang 44) thuộc mục 2.4.3 bị xếp sau mục 2.4.4 (B0076, thứ tự đọc); (b) nhãn OCR sai vào `keywords` (B0049: `DR4-`, `DIH2`, `FUL2-`); (c) 29 chunk thủ tục chung lặp nguyên văn ở nhiều mục (4 nhóm hash); (d) lỗi của PDF gốc giữ nguyên văn: số mục `3.3.4`, `3.3.5`, `3.9.1`, `3.9.2` (đúng: 4.x), chữ tiếng Việt trong bản tiếng Anh (16 chunk), `M1951`/`M1950` (B0204), `#12103` (B0168) | PARSE / LUẬT / NGUỒN | build | Có thể: trích dẫn sai mục, fact sai mã | R F | P2 | (a), (b): sửa luật; (c): khử trùng khi index (đo ở Bước 4 cùng S-03); (d): cần cơ chế đính chính (errata) cấp manifest — chưa có trong C2. **(a), (b) xử lý 2026-11-12** (run `f54/eval-g`): (a) T-07 dời hình nằm trên heading đầu trang nhưng bị xếp sau về mục trước (cờ `reading_order_fixed`; F54 chỉ Figure 52 bị dời, F86 0); (b) nhãn OCR crop chỉ vào từ khóa khi có trong từ vựng tài liệu hoặc khớp mẫu chân của profile (duyệt: Toma): F54 175/1.500 nhãn bị loại (79 khác nhau, gồm `DR4-`, `FUL2-`, `PL14+`, `QFF54`), giữ `PUL1+`, `DIR1+`, `GND`, `X0`; 45 chunk đổi từ khóa. Còn (c), (d) |
| I-41 | Hệ quả của số mục in sai (I-40d) lên `section_path`: mục `3.3.4`, `3.3.5`, `3.9.2` của F54 không nằm dưới `PART 4`, và mục **`4.3.6 Copy and Paste` có số đúng** cũng thành gốc (`["4.3.6 Copy and Paste"]`, thiếu `PART 4 > 4.3 Program screen`) vì ngăn xếp mục đã bị 3.3.x làm lệch. Phát hiện khi duyệt tay `f54/eval-c` (2026-11-11), các chunk B0249–B0258, B0307–B0309 | NGUỒN + LUẬT (T-07) | S1 section, build | Có thể: breadcrumb và trích dẫn sai mục, chunk mất ngữ cảnh "Program screen" | C R | P2 | sinh chunk. Đề xuất: T-07 khôi phục cha theo tiền tố số khi mục sau nối tiếp được nhánh cũ (4.3.6 → 4.3); số in sai đi cùng cơ chế đính chính cấp manifest (BL-08, I-40d) |
| I-42 | F54 mục 4.4.3 (trang 129–130) có **hai thủ tục liền nhau** (tìm tâm 4 điểm, 3 điểm), mỗi thủ tục một câu dẫn và đánh số lại từ Step 1. Sau khi nhãn khung "Instructions" thành chữ của hình (I-37), không còn gì ngăn hai thủ tục: câu dẫn thứ nhất thành chunk hình gần rỗng cùng tiêu đề mục (B0245), câu dẫn thứ hai dính vào cuối Step 2 và hai thủ tục thành một chunk (B0246). Trước I-37 nhãn "Instructions" vô tình làm ranh giới | LUẬT (T-20 nhãn khung + R-02) | build | Có thể: câu hỏi về cách 3 điểm nhận chunk lẫn cả hai cách; chunk hình gần rỗng | R | P2 | tra cứu. Phát hiện khi đối chiếu `eval-c` ↔ `eval-d` (2026-11-11); giữ nguyên theo quyết định duyệt, 2 chunk ghi `fix`. Đề xuất: nhãn khung mở khối mới khi phần tử sau nó không phải bước; khối không nhãn chỉ có một câu ngắn ngay trước chuỗi bước gộp làm câu dẫn của thủ tục; tách thủ tục khi số bước quay lại 1. **Xử lý 2026-11-12** (run `f54/eval-g`, C2 R-02): tách thủ tục khi bước quay về 1, câu dẫn + sơ đồ cùng trang đi theo thủ tục mới, khối tiêu đề + sơ đồ + câu dẫn gộp vào thủ tục đầu. 4.4.3: hai thủ tục (4 điểm: trang 129, 218 token; 3 điểm: trang 130, 226 token) |
| I-43 | Chunk không phải bảng có `embed_text` vượt ngân sách 800 − 150 dành cho Bước 3 (F54 `eval-f`: B0020 690, B0036 797 token); luật ngân sách token (I-38, R-12) mới áp cho bảng và khối có đầu phần. Ghi nhận 2026-11-12 khi lập kế hoạch I-39 | LUẬT (chunker) | build | **Có thể** sau Bước 3: tóm tắt + câu hỏi thêm vào đầu `embed_text` đẩy đuôi `content` ra ngoài 800 token | R | P2 | trước Bước 3. Đề xuất: áp ngân sách token cho mọi khối khi quyết định tách, hoặc CQ cảnh báo chunk > 650 token. **Mô tả lại và xử lý 2026-11-13** (run `f54/eval-h`, D-008, duyệt: Toma): đo lại thì cả 3 chunk vượt là **chunk cha** (B0036 800, B0115 712, B0020 690), mọi chunk lá ≤ 584 token; ngưỡng 800 là tự đặt (C2 §8). Quyết định chỉ tìm trên chunk con/độc lập, cha chỉ mở rộng ngữ cảnh → ngân sách áp cho lá (CQ-12, cờ `embed_over_budget`), cha không gắn cờ cắt, không tách cửa sổ. Phía SQL/retriever chưa làm |
| I-44 | Khung chữ "Instructions" (T-20 `text_frame`, 22 hình F54) vẫn là asset dù chữ đã tách vào `content`; T-20 bỏ sót khung trang 153 (chỉ có caption bước) | LUẬT (build + T-20) | build | Có: ảnh thừa khi hiển thị câu trả lời | R | P2 | xuất bản. **Xử lý 2026-11-13** (run `f54/eval-j`, duyệt: Toma): hình `text_frame` không là asset, không làm khối thành chunk hình; T-20 nhận khung có tiêu đề khung mà chỉ còn caption bước. F54 asset lá 234 → 208 (23 khung + 3 ảnh bìa bị loại theo manifest) |
| I-45 | Hình + ghi chú ngắn cùng mục bị tách thành 2 chunk vụn (F54 2.2: B0008 67 token + B0009 83 token dưới cha 97 token; 2.4.1) | LUẬT (chunker) | build | Có thể: vector từng con quá mỏng | R | P2 | tra cứu. **Xử lý 2026-11-13** (run `f54/eval-j`, C2 R-13): ghi chú ngắn ngay sau chunk hình cùng mục gộp vào chunk hình khi tổng ≤ 600 ký tự; F54 2 mục đổi, F86 0 |
| I-19 | Danh sách mã có **giá trị theo từng mã**: `#8150, #8152 #8154 → 1000/5000/10000`, mô tả `(1st, 2nd, 3rd)` (trang 168) | NGUỒN | S3, B4 | **Có thể**: trả lời "default #8152 = 1000/5000/10000", hoặc LLM tự chọn sai phần tử | F | P1 | trích fact |
| E-01 | `load_csv.py:186` luôn ghi `parent_id = None`; 42 `parent_key` của CSV F86 không vào DB → `Retriever._expand_parents` không bao giờ mở rộng | CHUNK (code hiện tại) | loader | Không; thiếu ngữ cảnh | T | P1 | xuất bản (sửa ở loader mới; **không** sửa production ở P-1) |
| E-02 | `answer_composer.py:96` cắt `hit.content[:3000]` theo ký tự, có thể cắt giữa dòng bảng. F86 hiện tối đa 1419 ký tự nên chưa xảy ra | CHUNK / runtime | B4 | Có thể mất dòng bảng | T F | P1 | sinh chunk (assertion CQ-03) |
| E-03 | F86: port table đánh số connector lệch 1 so với Figure 2.1 và các sơ đồ (ghi trong `source_note`) | NGUỒN | catalog / fact | **Có**: connector sai | F | **P0** cho fact F86 | trích fact F86 |
| E-04 | 55/92 chunk F86 có `extraction=ocr+vision`; nhiều `source_note` ghi "Cách nối chân đọc từ hình vẽ" | baseline | regression | — | F | P1 | không dùng làm nguồn fact (chỉ `human_verified_figure` sau review) |
| E-05 | `match_doc_chunks` (`backend/sql/doc_chunks.sql`): nhánh vector coi `p_models` rỗng là không lọc (`coalesce(cardinality(p_models), 0) = 0`), nhánh FTS dùng `p_models is null` → khi Retriever truyền mảng rỗng, nhánh FTS không trả dòng nào (ghi nhận 2026-11-09 khi đọc luồng tra cứu cho C2) | CHUNK (SQL hiện tại) | retrieval | Có thể: mất điểm FTS cho câu hỏi không lọc model | T | P2 | tra cứu. Chưa sửa: sửa riêng ở module chatbot (SQL + test), không gộp vào BL-16 |

**Kết luận mục 1**: I-01, I-02, I-03, I-04, I-05, I-06, I-07 và E-03 có thể sinh
dữ liệu kỹ thuật sai mà **không** có tín hiệu nào. Đưa thẳng output Docling vào
bất kỳ chunker nào là không chấp nhận được.

## 2. Hành vi chunking hiện tại (xác minh mã nguồn)

| Khía cạnh | Code hiện có | Baseline F86 (`doc_chunks_f86.csv`, 92 chunk biên soạn tay) | Kết quả với ca F54 |
|---|---|---|---|
| Pipeline PDF → chunk | **Không tồn tại**. `doc_ingest/` chỉ có `spike/` | Biên soạn ngoài repo, nạp bằng `chunking_loader/load_csv.py` (không chunk) | Không có gì để chạy; mọi hành vi dưới đây là của module khác hoặc của dữ liệu tay |
| Phân cấp section | — | `section_path` độ sâu 1–4; `metadata.parent_key` (42 chunk, 16 cha, resolve đủ) | DB **mất** quan hệ cha–con (E-01) |
| Bảng / bảng nối trang | `learning_ai/chunking/chunk_builder.py` không render bảng; `_pack` gom các dòng `rows:i` của `ParameterConfigContent` thành `parameter_id = value`, **không có header** | Dạng `addr \| name \| values \| default`, dòng `Format:` một lần mỗi chunk; không có bảng markdown | Không có cơ chế nối trang, lặp header hay lấp ô trống |
| List cha–con | Không có | Người biên soạn tự gộp | I-07 không được xử lý |
| Warning / procedure | `learning_ai`: `_warnings_for` / `_header` lặp cảnh báo DANGER ở mọi chunk, bước cùng phase không bị cắt (pattern **đáng dùng lại**) | Không có `chunk_type` warning; warning nhúng trong procedure/pinout (≥ 15 chunk có Note/Warning) | Warning không truy xuất độc lập được |
| Tham chiếu parameter | `learning_ai`: `ParameterSetting.parameter_id: str` (mã đơn) | Nguyên văn, có dải và danh sách; `availability_note` ở 2 chunk | Không có parse hay kiểm giao mã |
| Hình / caption / asset | Không có | 146 asset, **tất cả là ảnh cả trang** `{bucket, path, page, printed_page}`; 8 chunk không có asset | Không có asset cấp hình; không nhận diện watermark/screenshot |
| Độ dài | `learning_ai`: `DEFAULT_MAX_CHARS=1800`, cờ `oversize` | content ≤ 1419 ký tự; `embed_text` tối đa 719 token, 7 chunk > 600 | — |
| Trang | — | `page_start` là trang vật lý; `metadata.printed_page_start` riêng (lệch ở 65/92 chunk) | Đã tách hai hệ số trang; F54 cũng cần như vậy |

**Chỗ sẽ sinh chunk thiếu hoặc gây hiểu nhầm nếu dùng cách hiện tại cho F54**:
1. Gom dòng parameter kiểu `learning_ai` (`#8010 = 3`) sẽ mất cột Work range và nhãn
   cột. Với bảng nối trang 169 (I-02), "0" bị gán nhầm cột.
2. Nhúng warning vào procedure như baseline F86: câu hỏi "lưu ý khi đấu output F54"
   không truy xuất được 3 ghi chú trang 40 một cách độc lập.
3. Asset cả trang (baseline) cho trang 18 trả về cả sơ đồ NPN/PNP lẫn màn hình USER;
   không có hình riêng cho Figure 15 vì Docling coi nó là bảng.
4. Không có `parent_id` trong DB nên chunk con (vd. một dòng parameter) không kéo
   được ngữ cảnh section/bảng cha.

## 3. Lớp chuẩn hóa tối thiểu

Chi tiết contract ở [p1_normalization_contract.md](p1_normalization_contract.md).
Tóm tắt:
- **Raw** (Docling JSON) giữ nguyên, không sửa. **Normalized** là một tầng riêng;
  mỗi giá trị chuẩn hóa truy về được `raw_ref` + bbox.
- 15 biến đổi deterministic T-01…T-15, mỗi lần áp ghi một dòng log.
- Các trường hợp không quyết định được bằng luật đi vào `review_queue` (có cờ
  `blocking`).
- **Rev 2 (pipeline chung)**: pipeline chạy cho mọi PDF, không biết trước lỗi.
  Thêm hồ sơ tài liệu S0 (đo trước khi parse), kiểm bất biến V-01…V-04 (phát hiện
  lỗi không cần biết loại lỗi) và profile cấu hình (tri thức miền/ngôn ngữ nằm
  ngoài code luật). Luật dùng sai số tương đối, không tham chiếu tài liệu cụ thể
  ([contract §0, §7–§9](p1_normalization_contract.md#0-nguyên-tắc-pipeline-chung-rev-2)).
- `LogicalTable` (D-02) giải quyết đảo cột, mất cột, bảng nối trang **về cấu
  trúc**. Nội dung đúng hay sai vẫn phụ thuộc vào luật T-xx và kiểm V-xx. Lỗi
  hợp lệ về hình thức (ô sai cột nhưng cùng kiểu) chỉ bắt được bằng V-02 hoặc
  người duyệt.

| Yêu cầu | Biến đổi | Deterministic? | Khi nào cần người |
|---|---|---|---|
| Dựng lại TableGrid | T-01 (gán cột theo tâm x), T-02 (lấp ô trống tường minh) | Có | Số cột không khớp sau T-01 |
| Bảng nối trang, cột trống | T-03 (nối theo biên x tương đối + số cột + không có heading chen giữa), T-04 (kế thừa header), T-05 (nhận header theo trùng header / hình dạng token / mẫu profile), T-15 (gộp dòng tiếp nối) | Có | Nối mơ hồ; T-05 không đủ tín hiệu; dòng mồ côi |
| List cha–con | T-08 v1 (lề trái là tín hiệu chính, glyph phụ; nối qua trang; có code 2026-11-09) | Có | `list_orphan` (con không tìm được cha), `list_level_ambiguous` (lề không khớp cấp nào) |
| Screenshot | T-09 (bảng 0 cell + phủ bitmap ≥ 0,8) | Có | — |
| Watermark | T-10 (bitmap cùng kích thước ≥ 3 trang, không caption) → **ứng viên** | Có (gắn cờ) | Ứng viên có caption hoặc chồng lên hình thật |
| Caption | T-11 (từ khóa hình → picture gần nhất phía trên; từ khóa bảng → bảng; từ khóa trong profile) | Có | 2 ứng viên |
| Section path | T-07 (đánh số `n.n.n` hoặc từ khóa phần trong profile, mang qua trang) | Có | — |
| Tham chiếu parameter | T-12 (`single` / `range` / `list`, contract D-01), T-13 (ứng viên ghi chú áp dụng theo lexicon profile) | Có | `unparseable`, `range_too_long`, `param_code_overlap`, có ghi chú áp dụng |
| Trang in | T-06 (`/PageLabels` → chuỗi số tăng dần trong furniture → manifest ghi đè) | Có | Không có nguồn (để `null`, không cần người) |
| Crop | T-14 (hợp bbox Docling với bounds bitmap nhúng + padding 12 pt) | Có | — |
| Lỗi chưa biết | S0 (đo trang, chọn OCR), V-01…V-04 (độ phủ text, đối chiếu bảng, bất biến bảng, cấu trúc trang) | Có | Mọi kiểm không đạt |

## 4. Quality gate tài liệu (theo document và knowledge unit)

Mô hình: parse được **không** có nghĩa là được truy vấn; tạo chunk được **không**
có nghĩa là active. Gate có hai mức.

**Mức document**: chỉ hai điều kiện chặn toàn bộ tài liệu.

| Trường hợp | Xử lý |
|---|---|
| Nguồn chưa xác minh | Manifest bắt buộc có `source_origin` (người cung cấp, ngày, sha256) + `source_verified_by`. Thiếu → document `blocked`: vẫn parse/chunk ở dạng nháp, không unit nào xuất bản được |
| Version mâu thuẫn (I-14) | Manifest có `doc_version` + `version_evidence` (header, tên file, người xác nhận). Lệch mà chưa xác nhận → `blocked` cho xuất bản. Không tự chọn version |

**Mức knowledge unit**: unit = bảng logic, procedure, nhóm connector, hình +
caption, hoặc section text. Mọi vấn đề khác xử lý ở mức này.

| Trường hợp | Xử lý |
|---|---|
| Lỗi trích xuất chưa giải quyết (cờ blocking trong review_queue) | Unit ở `pending_review`, không xuất bản được |
| Mâu thuẫn kỹ thuật (E-03, các `source_note`) | Tạo `conflict_group` liên kết các bên; **mọi bên** bị giữ tới khi người có thẩm quyền chọn `this_supersedes` / `keep_both` (kèm điều kiện) / `reject_this` / `false_positive` (ngữ nghĩa `ConflictStatus` trong `learning_ai/schemas/knowledge_record.py`) |
| Lỗi do parser | Sửa ở **luật** rồi chạy lại; không sửa tay (sẽ mất khi parse lại). Lý do reject: `parse_error` |
| Lỗi nguồn (chính tả, sai số trong tài liệu) | Annotation có ký tên, **giữ nguyên văn gốc**; không sửa nguồn âm thầm. Lý do reject: `source_error` khi không sửa được |

### Mô hình HITL: điều kiện bắt buộc

| # | Điều kiện | Rủi ro nếu bỏ |
|---|---|---|
| H-1 | Luật P0 (T-01…T-05, T-08, T-12) đạt golden test **trước** khi sinh chunk nháp | Review biến thành nhập liệu tay; sửa tay mất khi parse lại |
| H-2 | Duyệt và xuất bản theo **knowledge unit**, nguyên khối | Xuất bản nửa bảng → câu trả lời thiếu mà trông như đầy đủ |
| H-3 | Hai trục trạng thái: version document (`staging/active/superseded`) × unit (`draft → pending_review → approved/rejected`, `conflict`). Chỉ phục vụ khi document `active` **và** unit `approved` | Kiến trúc rev 2 (bật `is_active` toàn document) không xuất bản từng phần được |
| H-4 | Phụ thuộc khi xuất bản: procedure/wiring cần warning liên kết đã approved; fact cần unit chứa evidence đã approved | Trả hướng dẫn đấu dây thiếu cảnh báo an toàn |
| H-5 | Conflict giữ mọi bên | Xuất bản đúng bên sai |
| H-6 | Approval gắn `unit_content_hash + evidence_hash`; chạy lại không đổi thì giữ, đổi thì về `pending_review` | Mỗi lần đổi parser phải duyệt lại toàn bộ |
| H-7 | Sửa của admin = annotation có ký tên, bản gốc giữ nguyên; chunk sửa phải embed lại trước khi xuất bản | Mất truy vết |
| H-8 | Duyệt theo mức rủi ro: pinout/wiring/parameter/warning/fact từ hình/unit có cờ → từng unit; text không cờ → hàng loạt theo section. v1 không có tự xuất bản | Khối lượng review không khả thi, hoặc xuất bản không người chịu trách nhiệm |
| H-9 | Thao tác duyệt có xác thực + audit. Chưa có auth admin → v1 dùng gói CSV + CLI có `--reviewer` | Mở API xuất bản tri thức khi chưa có auth |

Hành vi chatbot với nội dung chưa duyệt (khi tới phạm vi 3): không bao giờ lộ ra.
Câu hỏi chỉ khớp nội dung pending đi đường `no_docs` như hiện tại.

## 5. Kiểm chứng chất lượng chunk

Đặc tả đầy đủ ở [p1_golden_tests.md](p1_golden_tests.md):
- GT-01…GT-16 (ca F54 thật);
- CQ-01…CQ-08 (assertion trên chunk);
- khóa sha256 baseline F86 (`a8629f58…02aa`), không ghi đè.

## 6. Quyết định đang mở

| ID | Câu hỏi | Đề xuất | Chặn |
|---|---|---|---|
| D-01 | Biểu diễn mã parameter | **Đã chốt**: khớp chỉ qua `param_codes int[]` tường minh; `param_kind`; `param_range_*` chỉ mô tả; `code_semantics`/`code_labels` do người duyệt đặt; một fact cho mỗi dòng nguồn ([contract §4](p1_normalization_contract.md#4-tham-chiếu-parameter-d-01-đã-chốt)) | — (chờ xác nhận cuối) |
| D-02 | Lưu bảng | **Đã chốt (2026-11-03)**: `LogicalTable` + segments, chunk/fact tham chiếu `logical_table_id` + `row_id`. 2a id `{doc_id}:t{nnn}` theo thứ tự xuất hiện, là định danh của lần chạy; approval giữ theo id, id đổi thì khớp duy nhất theo hash nội dung (`carry_over`, HA-05b); 2b `row_id` theo thứ tự nguồn trước T-15, dòng gộp giữ id dòng đầu; 2c header nhiều tầng ghép `" / "` + `complex_header` chặn chunk, ô merge/bảng xoay/lồng ngoài V1; 2d V1 lưu file `normalized/tables.jsonl`, DB nhận tham chiếu (C2). T-01 đổi sang biên cột theo khe trắng (rev 3, [contract §5](p1_normalization_contract.md#5-biến-đổi-deterministic)) | — |
| D-03 | Luật header | **Đã chốt (2026-11-03)**: T-05 theo thứ tự (a) trùng header → header lặp, (b) hình dạng token, (c) mẫu mã profile, (d) giữ cờ + `header_demotion_unsure` chặn chunk (3a). 3b bước (b) cần ≥ 3 dòng dữ liệu và hình dạng phổ biến nhất ≥ 60%; 3c không dùng kiểu chữ ở V1; 3d `continuation_tol=0.15` là giá trị ban đầu, D-12 chỉnh lại | — |
| D-04 | Fact có ghi chú áp dụng | **Đã chốt phần mô hình dữ liệu (2026-11-03)**: fact luôn được giữ; 4a `status ∈ not_available\|available_only\|conditional`; 4b `models[]` (registry), `interfaces[]` (`control_interface` registry), `condition_text` nguyên văn; điều kiện không khớp registry ("touch controller") → `conditional` + `applicability_model_unmatched`; 4c chunk/fact `not_available` vẫn mang model bị loại trừ trong `product_models` để filter không loại nó, câu trả lời đọc `applicability`; 4d chưa khớp registry thì chặn **xuất bản fact**, không chặn chunk. Phần phát hiện: lexicon profile (đã có, sinh `applicability_candidates` — ứng viên, không phải fact) + LLM ở bước trích fact (BL-17) | trích fact (phần LLM) |
| D-08 | Mô hình HITL | **Đã chốt (2026-11-03)**: 8a unit + hai trục trạng thái + xuất bản theo unit (H-1…H-9); 8b V1 giữ trạng thái trong gói offline (CSV review + CLI `--reviewer`), DB chỉ nhận unit đã duyệt (`unit_id`, `is_active` theo dòng); 8c text không cờ được duyệt hàng loạt theo section, unit rủi ro cao hoặc có cờ duyệt từng unit; 8d embed sau khi duyệt, lúc publish, chỉ chunk có hash mới. Lõi trạng thái/approval đã có code (`doc_ingest/review/approval.py`) | — |
| D-05 | F54: V.01 hay V.02 | Hỏi team sản phẩm | xuất bản F54 (phạm vi 3) |
| D-06 | F86: số connector theo port table hay theo hình | Người có thẩm quyền chọn | fact F86 |
| D-07 | Spike F86 (sơ đồ vector) | Bắt buộc trước khi duyệt S1 phần hình | S1 phần hình |
| D-09 | Ai là reviewer có thẩm quyền, ai giải quyết conflict | Team chỉ định | xuất bản unit |
| D-10 | Giá trị theo từng mã trong danh sách (I-19) | V1 giữ nguyên văn + cờ `per_code_values`; tách giá trị theo mã chỉ khi người duyệt đặt `code_labels` | trích fact |
| D-11 | Profile cấu hình | **Đã chốt (2026-11-03)**: 11a YAML (PyYAML đã pin); 11b chọn theo manifest, mặc định `default`; 11c từ vựng registry = `profiles/registry_snapshot.json` + test đồng bộ ở venv chính; 11d hash profile **không** nằm trong hash approval (sửa rev 2), chỉ ghi `run_report.json` ([contract §9](p1_normalization_contract.md#9-profile-cấu-hình)) | — |
| D-12 | Ngưỡng kiểm V-xx và S0 | Ngưỡng ban đầu đặt trên corpus F54 + F86, ghi vào profile; V-01/V-02 không đạt luôn blocking cho chunk của trang/bảng đó. Giá trị tạm đang dùng (2026-11-03): S0 `ocr_min_chars=20`, `text_bad_char_max=0.1`; V-01 `text_coverage_min=0.9`, `text_duplicate_max=0.1`; F54 11 trang fixture + trang 5–10 đều đạt, trang thấp nhất 95,7% phủ / 8,2% trùng (chữ số mũ). F86 Operation không có text layer nên V-01 không áp dụng được (I-20) | sinh chunk |

**C1 đã khóa (2026-11-03)**: D-01, D-02, D-03, D-04 (mô hình dữ liệu), D-08, D-11
đã chốt. Còn mở: D-12 (chặn sinh chunk), D-05, D-06, D-07, D-09, D-10 và phần LLM
của D-04 (chặn các bước sau).

## 7. GO / HOLD

"GO" là khuyến nghị cho lúc bắt đầu Ingestion V1, không phải hành động của bước P-1.

| Hạng mục | Quyết định | Điều kiện |
|---|---|---|
| Khóa contract C1 | **ĐÃ KHÓA (2026-11-03)** | Các quyết định đã chốt; `extraction_method` của ảnh để dạng mở rộng được. Spike F86 (BL-13) vẫn là ca kiểm tính chung đầu tiên trước khi sinh chunk |
| Triển khai S1/S2 (chuẩn hóa deterministic) | **GO** (trong V1) | Chỉ nội bộ `doc_ingest`, chạy với golden test, không ghi DB |
| Sinh baseline chunk (nháp) | **HOLD → GO sau H-1** | T-01…T-05, T-08, T-12 đạt GT-01…GT-04, GT-07 với profile `default`; V-01…V-03 chạy được (GT-19…GT-22); có CQ-01…CQ-08; D-12 |
| Trích fact có cấu trúc (nháp) | **HOLD → GO sau H-1 + D-04 + D-10** | Mọi fact vào `pending_review`; fact F86 dính E-03 vào conflict group |
| Xuất bản unit / activation production | **HOLD** | Thuộc phạm vi 3: schema unit, CLI review có audit, staging DB, eval C0, D-05, D-09 |

## Phụ lục A — Lệnh xác minh (chỉ đọc)

Chạy từ repository root; JSON spike cần chạy lại tool spike trước (output không
được commit).

```bash
# sha256 baseline và PDF nguồn
sha256sum backend/app/modules/chunking_loader/documents/doc_chunks_f86.csv \
  "docs/ai/doc_ingest_spike/source/F54_Operation Manual (English Version)_V.02.pdf"
# → a8629f5878fc1d4f16c2706d7b0440a46fe9ecfe098e0b7ec525f16c878f02aa  (CSV, commit 0d6070e)
# → 7cd0e69c1e94d41649fd361a47bd089279897b085f8c2b0b93c99dc1591bce21  (PDF F54)
```

```python
# Trang 168/169/011: số cột, dòng thiếu cell, cell mang cờ header
import json
for p, i in [("168", 0), ("169", 0), ("011", 0)]:
    t = json.load(open(f"p{p}.json", encoding="utf-8"))["tables"][i]; d = t["data"]
    rows = {}
    for c in d["table_cells"]:
        rows.setdefault(c["start_row_offset_idx"], []).append(c)
    print(p, d["num_cols"], len(rows),
          sum(len(cs) < d["num_cols"] for cs in rows.values()),
          [c["text"] for c in d["table_cells"] if c["column_header"]][:4])
# 168: 4 cột, 32 dòng, 29 dòng thiếu cell, header = ['#4140 - #4147','Axis type',...]
# 169: 3 cột, 17 dòng, 0 dòng thiếu cell, không header
# 011: 2 cột, 11 dòng, header = ['Port','Functions']
```

```python
# Đảo cột: so thứ tự theo col index với thứ tự theo bbox.l trong từng dòng
# → p011: 10/11 dòng lệch; các bảng khác 0
```

```python
# Kiểm giao param_codes trong 3 bảng logic (axis 167→169t0, spindle 169t1→170t0,
# general 170t1→171t0) → axis 70 dòng, spindle 20, general 21: không giao
```

```python
# Baseline F86: parent_key, độ dài, extraction (pandas + tiktoken cl100k_base)
# → 42 chunk có parent_key (16 cha, resolve đủ); content tối đa 1419 ký tự;
#   embed_text tối đa 719 token, 7 chunk > 600; extraction: ocr+vision 55,
#   text_layer+vision 27, text_layer 10; 146 asset đều là ảnh cả trang
```

Dòng code đã đối chiếu:
- `backend/app/modules/chunking_loader/load_csv.py:186` (`"parent_id": None`);
- `backend/app/modules/chatbot/stages/answer_composer.py:96` (`hit.content[:source_char_limit]`, mặc định 3000);
- `backend/app/modules/chatbot/repositories/doc_chunk_repository.py:31` (`_FETCH_SQL` lọc `is_active`);
- `backend/app/modules/chatbot/retrieval/retriever.py` `_expand_parents` (thay chunk con bằng nội dung chunk cha);
- `backend/app/modules/learning_ai/chunking/chunk_builder.py` (`_pack`, `_warnings_for`, `DEFAULT_MAX_CHARS`);
- `backend/app/modules/learning_ai/review/lifecycle.py` (`TRANSITIONS`, `approval_gate`).
