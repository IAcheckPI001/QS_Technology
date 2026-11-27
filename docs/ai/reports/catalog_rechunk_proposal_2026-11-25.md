# Phương án chia lại chunk catalog `qs_product_catalogue` (đề xuất, 2026-11-25)

Căn cứ: `catalog_chunk_audit_2026-11-25.md` (kiểm duyệt ngược luồng), đo catalog (recall/hạng/ctx_precision) và thí nghiệm tách nhánh trong LOG website-qa cùng ngày.
**Trạng thái (2026-11-25): Toma chọn phương án C; mã đã làm và build run `curated-b2` (72 chunk, 453 test doc_ingest đạt); CHƯA nạp DB, chưa đo trước/sau, các mục ở phần 7 chưa trả lời hết (đã dùng mặc định: bật `vi_keywords`, không thêm `spec_attributes` mới, giữ 16 bảng gốc, C-11 để nguyên).** Phần dưới là nội dung đề xuất ban đầu. Toàn bộ dựa trên dữ liệu biên soạn đã có (`curated/selection_matrix.yaml`, `products/*.yaml`), không cần trích lại PDF.

## 1. Vấn đề cần giải quyết

| Vấn đề (nhóm) | Hệ quả đo được |
|---|---|
| T1/T2: mỗi chunk bảng chứa 3–4 model (cột), `product_models` không thu hẹp, `embed_text` có 4 tên model | K10 (tuổi thọ dao F86): chunk đúng hạng 4–5, chunk trang sản phẩm F86 xếp trên dù không chứa đáp án; chunk đúng của câu "mong đợi" chỉ ở hạng 1 ở 8/20 câu |
| T1/T2: ký hiệu ✓/✗/(Option); cột `6AV/H` gộp; tiêu đề mục trùng giữa hai bảng | khó khớp câu hỏi bằng chữ ("có/không hỗ trợ"); hai nguồn cùng tên cho hai nhóm model |
| P3: lặp lại P1, dải trang `4–19` | chunk trùng cạnh tranh; trích dẫn "tr. 4–19" sai |
| `vi_keywords` tắt | nhãn tiếng Việt có sẵn nhưng không vào tìm kiếm |

Ràng buộc đã chốt (Toma 2026-11-14): **`content` bám sát chữ in của PDF, không thêm câu, không dịch**; giá trị khác bản in chỉ theo quyết định C-xx. Vì vậy phương án chỉ thay đổi **cách chia** và **`embed_text`** (phía tìm kiếm), không đổi chữ model đọc để trả lời.

## 2. Các phương án

| | A. Giữ nguyên | B. Thay bảng bằng lát theo model | **C. Thêm lát theo model, giữ bảng so sánh, gọn P3, làm giàu `embed_text` (đề xuất)** |
|---|---|---|---|
| Chunk | 37 | 7+7+7+35 = 56 | 7+7+7+35+16 = **72** |
| Câu một model (vd tuổi thọ dao F86) | chunk bảng loãng hạng 4–5 | chunk lát riêng một model, hạng cao | như B |
| Câu so sánh nhiều model | dùng chunk bảng | mất bảng, phải so từ các lát | giữ bảng: logic so sánh của retriever lấy lát riêng từng model + bảng dùng chung |
| Câu "những model nào hỗ trợ X" | chunk bảng (đã đo K05, K16) | yếu: top 6 không phủ 7 model | giữ bảng cho loại câu này |
| Rủi ro | không đổi | mất khả năng liệt kê | chunk nhiều hơn, có trùng giữa lát và bảng (kiểm bằng đo) |

## 3. Thiết kế phương án C

### 3.1 Lát bảng theo model (mới, 35 chunk)
- Sinh từ `selection_matrix.yaml`: mỗi model, nhóm hàng thành **5 lát theo chủ đề** (nhóm 3 lát to làm loãng nghĩa: bản thử cho thấy lát "tính năng" gom 26 hàng dài 1.042 ký tự):

| Lát | Nhóm hàng của bảng | Số hàng |
|---|---|---|
| Tổng quát | General | 11 |
| Phần cứng | Hardware Specification | 6 |
| Bù và đa trục | Compensation, Multi axis control mode | 5 |
| Vận hành và quản lý dao | Operation, Tool Manager | 9 |
| Điều khiển và lập trình | Control, Builder Supp | 12 |

- `content` (bám PDF): đúng các hàng như in, chỉ lấy **cột của model đó**, giữ ô con theo giao tiếp. Ví dụ F86, lát "Vận hành và quản lý dao":
  ```
  MOTION CONTROLLER / Selection table / Operation + Tool Manager
  | Specification | F86 |
  | MPG Simulation | ✓ | … | Tool-life management | ✓ | … | Look-ahead contour violantions detect | ✗ | …
  ```
  Ghi nhãn và lỗi chính tả như PDF ("violantions"); cột 6AV/6AH vẫn mang tên in "ASTRO 6AV/H" (kèm ghi chú trong `embed_text`).
- Trường: `product_models` = đúng một model; `control_interface` theo model; `section_path` duy nhất ("MOTION CONTROLLER › Selection table › F86 › Vận hành và quản lý dao"); `chunk_type = table`; trang 6 hoặc 7; `curated_decisions` của các hàng liên quan (C-01, C-06…C-09, C-12…); `chunk_role = standalone`.
- **`embed_text` làm giàu (chỉ phía tìm kiếm):** thêm một dòng "Tóm tắt" sinh máy từ giá trị và nhãn `vi` đã có trong YAML, đổi ký hiệu thành chữ: "✓ → có, ✗ → không, (Option) → tùy chọn",
  ví dụ "F54 · Quản lý tuổi thọ dao (Tool-life management): không; Hỗ trợ thay dao tự động (ATC support): có; …". Bản thử: trung bình 780 ký tự thêm cho mỗi lát (tối đa 1.376), vẫn trong ngân sách 800 token của embed.
  Mọi chữ thêm đều sinh từ dữ liệu đã duyệt, không viết tay, nên không thêm sự kiện.

### 3.2 Bảng chọn gốc (giữ 16 chunk, chỉ chỉnh metadata)
- Giữ làm chunk **so sánh/liệt kê** (nhiều model). Đổi `section_path`/`section_title` thành duy nhất ("… Selection table (F54, F86, F10T, 10S) › General" và "… (6AV, 6AH, 10i) › General"); sửa nhãn tiêu đề cụt "Builder Supp" ở `section_path` (giữ nguyên trong nội dung in).
- Thêm tóm tắt chữ (ký hiệu → chữ) vào `embed_text` như 3.1. `content` giữ nguyên nên `content_hash` không đổi.

### 3.3 P3 gọn (7 chunk, sửa)
- Bỏ các dòng đã có ở P1 (kích thước, màn hình, số trục, giao tiếp, I/O, PLC/Macro, open/closed loop). Giữ phần riêng: dòng chỉ có ở trang tóm tắt (RTCP tùy chọn, nút dừng khẩn cấp, tay quay MPG tích hợp, phím nhôm, công tắc xoay override) và khối trọn bộ (servo drive, servo motor, power supply, 4 axis MPG, I/O Link board, Tool Setter, 3D Touch Probe).
- Trang: `page_start` = trang trọn bộ (19–21), `metadata.source_pages = [4, 19]` thay cho dải `4–19`.
- Tên board "RLTR": chờ Toma xác nhận C-11 (RBT-01) trước khi sửa (đang để nguyên như in).

### 3.4 Giữ nguyên
P1 và P2 (14 chunk): `content` không đổi nên `content_hash` không đổi, verdict `ok` đề xuất ở bản nháp vẫn dùng được (cơ chế `review_template` giữ verdict khi hash trùng). Chỉ bổ sung `spec_attributes` và (khi bật cờ) từ khóa tiếng Việt cho `embed_text`.

## 4. Thay đổi mã và dữ liệu (phạm vi)

| Việc | Ở đâu |
|---|---|
| Hàm dựng lát theo model và câu "Tóm tắt" cho `embed_text` | `doc_ingest/curated/build.py` (`_matrix_drafts`, `_embed`), dùng sẵn `vi`, `_cell`, `SPEC_ATTRIBUTE` |
| P3 gọn, `source_pages` | `build.py` (`_product_drafts`) |
| Bật `vi_keywords` | tham số có sẵn của `curated-build` (cần Toma quyết) |
| `spec_attributes` mới cho tính năng bảng (atc, rtcp, tool_life, mpg…) | **từ vựng lấy từ registry chatbot** (`registry_snapshot`): thêm từ phải sửa registry; nếu không thì để trống, chỉ dùng thuộc tính đã có |
| Test | `tests/doc_ingest/test_curated.py`: số lát, nội dung = cột của bảng gốc, `section_path` duy nhất, hash P1/P2 không đổi, ngân sách token |
| Run | **run mới** (`curated-b`), không ghi đè `curated-a`; `curate-check` chạy lại; nạp lại cùng `doc_id`, `doc_version` mới (loader dry-run trước) |
| Tài liệu | `STATE.md`, `LOG.md` của doc-ingest; ghi website-qa |

## 5. Kế hoạch đo (trước/sau, cùng bộ câu)

- **Bộ câu:** `catalog_f54_astro` (20 câu) và 7 câu hợp lệ của `dual_source`; nhãn `acceptable` thêm lát mới (nhãn cũ khớp theo `content_hash`; chunk bảng không đổi `content`, lát mới là chunk mới).
- **Mốc hiện tại (web1/web2:base):** recall@1 0,65–0,70; chunk "mong đợi" ở hạng 1: 0,35–0,40; ctx_precision 0,455–0,465; K10 hạng 4, K19 hạng 9 (core), K16 hạng 2.
- **Tiêu chí đề xuất (Toma duyệt):** recall@5 không giảm; chunk đúng ở hạng 1 tăng từ 13/20 lên ít nhất 16/20; K10, K19 vào top 2; không câu nào tụt quá 2 hạng; chunk bảng vẫn xuất hiện cho K05, K16 (liệt kê model); chạy `--repeat 2` và báo kèm khoảng nhiễu.
- Câu thật liên quan (RC13 đầu dò tâm, K09 trọn bộ) cần trang 23 chưa chunk: đo riêng sau khi biên soạn trang phụ kiện.

## 6. Công sức, chi phí, rủi ro

- **Kỹ sư:** 2–3 ngày công (mã, test, run mới, đo). **Toma/QS:** duyệt 35 lát và 16 bảng đã chỉnh; có thể duyệt mẫu vì lát sinh máy từ dữ liệu đã duyệt, kèm script đối chiếu tự động lát với cột bảng gốc (khoảng 2 giờ).
- **Chi phí API:** nhúng lại 72 chunk, dưới 0,001 USD.
- **Rủi ro:** (1) lát và bảng trùng thông tin → cạnh tranh trong top 6 (kiểm bằng đo, có thể hạ bảng bằng `type_boost`); (2) tăng số chunk nhỏ làm mỗi lượt nạp thêm nhiễu cho câu không nêu model (đo trên K05, K16); (3) câu "Tóm tắt" trong `embed_text` làm nghiêng tìm kiếm sang tiếng Việt (đo K-set song ngữ); (4) mã nguồn `build.py` thuộc contract C2 §15 — sửa phải qua người duyệt.

## 6b. Bối cảnh: vai trò của catalog so với tài liệu từng model (đo trên DB 2026-11-25)

| | **Catalog** `qs_product_catalogue` | **Operation guide** `<model>-operation-*` | **Installation guide** `<model>-installation-*` |
|---|---|---|---|
| Mục đích | giới thiệu và chọn sản phẩm (brochure 24 trang) | vận hành sau mua: giao diện, thao tác, đấu dây, tham số (100–150 trang/model) | lắp đặt phần cứng: kích thước, sơ đồ kết nối, bảng chân cổng |
| Đối tượng | khách tiềm năng, kinh doanh | người dùng, kỹ thuật vận hành | kỹ thuật lắp đặt |
| Phạm vi | 7 controller + servo + board + phụ kiện + công ty; so sánh chéo model | một model | một model |
| Nội dung | định vị, thông số tóm tắt, tính năng, bảng chọn, trọn bộ, phụ kiện, liên hệ | giới thiệu, ngoại hình, kích thước (hình), cấu trúc phần mềm, đấu nối, màn hình, bảng tham số, PLC, đo dao | sơ đồ, bảng PORT/PINS, đầu vào/ra, xung/servo, biến tần, tay quay, RS485, nguồn |
| Loại câu trả lời được | "model nào phù hợp", so sánh, có/không hỗ trợ tính năng (ATC, EtherCAT, RTCP…), trọn bộ, giá/liên hệ | "cách làm/cài đặt/đấu dây/tham số nào" | "đấu chân nào, cổng nào" |
| Domain / intent | `product_catalog` / `lookup.product_*`, `compare.*` | `technical_docs` / `guide.operation`, `guide.configuration`, `troubleshoot.error` | `technical_docs` / `guide.installation` |

**Phủ theo model:** F54 và F86 có cả vận hành và lắp đặt; F10T và 6AVE có cả hai (bản tiếng Việt; lắp đặt 6AVE tiếng Việt); 6AH và 10iV chỉ có vận hành; **10S chỉ có trong catalog (không có tài liệu riêng)**; 6AV (catalog) ứng với tài liệu `6AVE`, 10i (catalog) ứng với tài liệu `10iV` (khác tên, gốc của lỗi `no_docs` đã thấy).

**Chồng lấn nội dung (đếm chunk trong tài liệu kỹ thuật):**
- **Thông số chỉ có ở catalog:** look-ahead, tần số xung 500 KHz, open/closed loop, EtherCAT, Mechatrolink, RTCP: **0 chunk** trong mọi tài liệu từng model. Catalog là nguồn duy nhất cho chọn model và so sánh.
- **Kích thước:** operation guide mục 1.2 (và installation 1.1) chỉ có chú thích hình (khoảng 180 ký tự); con số bằng chữ chỉ có ở catalog.
- **Điện áp 24V, ATC:** có ở cả hai loại (catalog: "Voltage input 24VDC", "ATC support"; guide: mục nguồn và thiết lập thay dao).
- **Chunk giới thiệu trang 1:** operation guide của F54, F86, 6AH, 6AVE, 10iV, F10T đều mở bằng cùng một đoạn "INTRODUCTIONS" khoảng 1.100 ký tự, chỉ đổi tên model, kèm đoạn giới thiệu công ty ("pioneer…Made by Vietnam", cùng ý với trang About Us của catalog và hồ sơ công ty). Đoạn này xuất hiện 2–3 lần mỗi tài liệu (chunk cha, con và bản mở rộng): khoảng 7–10 chunk gần như trùng nhau trong DB. Chunk F10T còn mất dấu tiếng Việt.

**Hệ quả:**
1. Catalog đúng là "tài liệu giới thiệu": việc chia chunk nên tối ưu cho câu hỏi tiền bán hàng (chọn, so sánh, có/không hỗ trợ), không cần giống cấu trúc sách hướng dẫn. Phương án C (lát theo model + bảng so sánh) khớp mục tiêu này; các nhóm P1/P2 và trang bundle/phụ kiện/servo (chưa chunk) quan trọng hơn chi tiết đấu dây.
2. Không cần trộn catalog với tài liệu từng model; ranh giới `product_catalog` và `technical_docs` đang đúng. Câu hỏi hai nguồn (vd "F54 có ATC không và cài thế nào") cần định tuyến tìm cả hai domain (lỗi R-1 đã biết).
3. Chunk giới thiệu lặp 7–10 lần là nhiễu cần dọn ở doc-ingest (giữ một bản, hoặc loại khỏi tìm kiếm, hoặc gom vào `company_info`); không thuộc phương án chia catalog nhưng nên làm cùng đợt kiểm duyệt tài liệu model.
4. Đồng bộ tên model giữa catalog và tài liệu (10i/10iV, 6AV/6AVE, 6AH có catalog nhưng chỉ vận hành) là việc registry/CRM, ảnh hưởng trực tiếp đến định tuyến.

## 7. Cần Toma quyết

1. Chọn phương án C (hoặc B/A).
2. Bật `vi_keywords` và cho phép "Tóm tắt" sinh máy trong `embed_text` (không đổi `content`).
3. Có thêm từ vựng `spec_attributes` vào registry chatbot không.
4. P3 gọn và `source_pages` thay dải trang; xác nhận C-11 (RLTR hay RBT-01).
5. Giữ 16 chunk bảng gốc làm chunk so sánh, hay hạ ưu tiên.
6. Làm cùng đợt hay tách riêng việc biên soạn trang servo (15–16), board (22), phụ kiện (23), liên hệ (24), About Us (2).
