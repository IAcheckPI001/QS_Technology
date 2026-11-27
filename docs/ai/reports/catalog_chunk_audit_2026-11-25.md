# Kiểm duyệt chunk `qs_product_catalogue`: truy ngược luồng sinh chunk (2026-11-25, bản 2)

Thay bản 1 cùng ngày. Bản 1 chỉ đọc nội dung chunk trong DB; bản này truy ngược từ chunk về PDF qua từng bước, đối chiếu **ảnh trang PDF** của run `qs_catalog/20261114-090524`
(24 trang; `QS_Product_Catalogue.pdf`, sha256 `ffff897f…aabf1`) với chunk. **Đã tải file từ link `…/view-pdf?v=1.1…` (2.265.936 byte, PDF 1.7): `sha256` trùng từng ký tự với bản đã chạy** (`ffff897f…aabf1`), nên chunk hiện tại sinh từ đúng bản v1.1; không có bản mới hơn cần nạp lại.
Khung cột/mức quan trọng: `doc_chunks_v2_column_roles_2026-11-25.md`.

## 1. Luồng sinh chunk (truy ngược từ DB về PDF)

| Bước | Việc | Ở đâu | Ai/cách |
|---|---|---|---|
| 0 | PDF catalog 24 trang | link ERP, bản trong run: `QS_Product_Catalogue.pdf` | CRM công bố |
| 1 | Trích chữ: S0 → Docling → chuẩn hóa T-xx → `elements.jsonl`, `raw/p{n}.words.json`, ảnh trang `pages/p001–p024.png` | `data/ingest_runs/qs_catalog/20261114-090524/` | pipeline (tool offline) |
| 2 | **Bỏ qua trích cấu trúc tự động** vì lỗi font/cặp tên–giá trị/bảng icon/`section_path` rỗng (I-47…I-50); thay bằng **dữ liệu biên soạn**: 7 file `products/*.yaml` + `selection_matrix.yaml` (43 hàng × 7 model, mỗi giá trị có `verified`, nhãn `vi`, `origin`) | `backend/app/modules/doc_ingest/curated/` | Claude soạn từ ảnh trang, Toma duyệt từng giá trị |
| 3 | Quyết định mâu thuẫn **C-01…C-13** (Toma chốt 14/11) | `page_value`/`override` trong YAML; `curated_decisions` trong metadata chunk (11 chunk) | Toma |
| 4 | `curate-check`: mọi giá trị `text|recovered` phải có nguyên văn trong chữ trang nguồn (961 chuỗi, ĐẠT, 5 "khác thứ tự"); khóa trùng giữa file model và bảng chọn phải cùng giá trị; sha256 nguồn khớp run | `curated/check.py` | tự động |
| 5 | `curated-build`: YAML → `DraftChunk` (`source=manual`) theo **mục in trên trang** (trang model: trên → `overview`, "THÔNG SỐ KỸ THUẬT" → `spec`; khối "QS - <MODEL> CONTROLLER" p4–5 + khối "MODEL: …" p19–21 → `overview`; bảng chọn: mỗi nhóm hàng của mỗi trang một `table`); dựng `embed_text`; `chunk_review.json`; xuất `doc_chunks_v2.jsonl` | `curated/build.py`, run `qs_catalog/curated-a` | tự động |
| 6 | Nạp vào DB bằng `chunking_loader` (draft, embed từ `embed_text`) | `doc_chunks_v2` | bước riêng |

Kết quả bước 5: 37 chunk (overview 14, spec 7, table 16), 0 lỗi ràng buộc, 0 giá trị chưa duyệt, 0 vượt 800 token, `review_status` 37 `draft`,
**verdict 0 `ok`, 0 `fix`, 37 `pending`** (`chunk_review.json`). `review_status` của chunk `manual` chỉ thành `approved` khi nguồn đã `verified` **và** verdict `ok`.
Vậy cổng duyệt còn lại chính là điền 37 verdict, không cần cổng 2b/2c.

## 2. Đối chiếu từng bước

### Bước 2–4 (biên soạn, quyết định, kiểm): trung thành, có kiểm soát
Đã xem ảnh trang 4, 6, 7, 8 (và 15, 16, 18, 19, 22, 23, 24, 2) và đối chiếu chunk:
- **Trang 8 (F54), 6 (bảng A), 7 (bảng B), 4 (tóm tắt):** chunk P1, P2, T1, T2, P3 khớp chữ in, kể cả ô gộp theo giao tiếp ("Pulse Train: 24/16 · EtherCAT: 16/16"), 4 cột A (F54 một cột; F86, F10T, 10S chia 2 cột con) và cột `ASTRO 6AV/H` có hàng Dimension tách theo hai ô in (220×460×42 cho 6AV, 325×285×42 cho 6AH).
- **Điều bản 1 coi là "mâu thuẫn dữ liệu" thực ra đã có quyết định:** Max PLC Axis ≠ Axis control (C-06: 10S 16 trục điều khiển, 14 trục PLC; F54 4 trục, PLC 0), Max. Spindle ≠ Max. Spindle Simultaneous Control (C-07), "Pitch error" của F54/F86/F10T/10S là **không có** dù trang model in dòng gộp
  "Backlash/Pitch error compensation: Yes" (C-01), 6AH closed loop/1000 lines (C-02, C-03), **10S: RTCP, DWO, TWP đều tùy chọn dù bảng chọn in ✗** (C-09), servo đến 55kW (C-10). Các quyết định này nằm ở `metadata.curated_decisions`; `content` in giá trị đã chốt.
- Khác biệt in ↔ chunk còn lại chỉ do quyết định: bảng trang 6 in ✗ cho DWO/TWP/RTCP của ASTRO-10S nhưng chunk ghi "(Option)" (C-09) — đúng theo quyết định, nhưng người đọc PDF sẽ thấy hai bản khác nhau.
- **Còn mở thật (chưa có quyết định trong LOG):** EtherCAT của F86/F10T/10S: trang model và trang tóm tắt liệt kê "Pulse Train, EtherCAT" là giao tiếp của model, bảng chọn ghi "EtherCAT (Optional)"; "Touch screen" của F10T/10S chỉ in ở bảng.
  PDF còn tự mâu thuẫn ở servo: trang 16 phần Tổng quan ghi 400W~45kW, phần Tính năng ghi 400W~55kW (đã chốt 55kW, C-10) — trang servo chưa được chunk.

**Đối chiếu trang 5, 9–14 (đã xem sau khi tải):** các trường chính (kích thước, màn hình, số trục, I/O link, giao tiếp, hệ điều khiển, encoder/torque/servo, max spindle, look-ahead, kết nối, điện áp) của P1/P2 cho F86, F10T, 10S, 6AH, 6AV, 10i và khối tóm tắt p5 **khớp chữ in, hoặc khác đúng theo quyết định C-xx**. Chưa so từng từ của phần tính năng/giao diện song ngữ (cùng một mẫu lặp lại cho cả 7 model).

**PDF in khác giá trị đã chốt (erratum của catalog, chunk theo quyết định, PDF chưa sửa):**

| Trang | PDF in | Giá trị chunk (đã chốt) | Mã |
|---|---|---|---|
| 8–11 (F54, F86, F10T, 10S) | "Backlash/Pitch error compensation: Yes" | Backlash có, **Pitch error không** | C-01 |
| 12 (6AH) | Control system "Open loop" | **Closed loop** | C-02 |
| 12 (6AH) | Look-Ahead 500 lines | **1000 lines** | C-03 |
| 12 (6AH) | Encoder EtherCAT "Full axis", chép mẫu F86 | theo 6AV: **Absolute** (EtherCAT, MII/MIII) | C-04 |
| 12–14 (6AH, 6AV, 10i) | "USB port: 1", "I/O link: 24/16" | USB và I/O theo giao tiếp (bảng chọn): USB 2 và I/O 16/16 cho EtherCAT/MII-MIII | C-08, C-13 |
| 6 (bảng chọn, 10S) | DWO, TWP, RTCP đều ✗ | **tùy chọn (Option)** | C-09 |
| 16 (servo) | Tổng quan 400W~45kW, Tính năng 400W~55kW | **55kW** (trang servo chưa chunk) | C-10 |
| 19 (trọn bộ F54) | "I/O Link board RLTR" | LOG chỉ ghi "C-11 tên đúng **RBT-01**" (mình **suy ra** là tên board này, chưa xác nhận); chunk P3 vẫn in "RLTR" | C-11 |

Đề xuất gửi bảng này cho bộ phận ra catalog để sửa PDF, nếu không bot (theo giá trị đã chốt) và catalog in (giá trị cũ) sẽ khác nhau khi khách đối chiếu.

### Bước 5 (chia chunk): giữ đúng ranh giới in, nhưng tạo vấn đề cho tìm kiếm
- **Theo mục in trên trang** là quyết định có chủ đích (yêu cầu của Toma: "bám sát PDF"). Hệ quả đã đo: mỗi model có 3 chunk P1/P2/P3 chồng lấn (P3 lặp kích thước, màn hình, trục, I/O của P1; phần riêng của P3 là danh sách thiết bị đi kèm và tùy chọn).
- **Bảng chia theo nhóm hàng × trang** nên có hai bảng (p6: F54|F86|F10T|10S; p7: 6AV/H|10i) với 8 mục trùng tên → hai chunk cùng `section_path`; mỗi chunk bảng chứa nhiều model (cột) nên không lọc được theo model.
- **`page_start`/`page_end` của P3 là hợp của hai trang:** `min(4 hoặc 5, 19/20/21)`–`max(...)` (vd `4–19`), trong khi thật ra chỉ trang 4 (hoặc 5) và trang 19 (hoặc 20, 21). Ghi dải `4–19` gây hiểu nhầm là 16 trang.
- **`vi_keywords` đang tắt:** mỗi giá trị trong YAML có nhãn tiếng Việt (`vi`, ví dụ "tuổi thọ dao", "cảm ứng", "bù bước vít me"); `build.py` chỉ đưa vào `keywords` khi bật cờ, còn lại ghi vào `proposed_keywords_vi` (chưa dùng, **chờ Toma quyết** — STATE doc-ingest C-2). Đây là nguyên nhân gần nhất khiến câu hỏi tiếng Việt về bảng (K10 tuổi thọ dao, K08 cảm ứng, K19 hệ tọa độ) xếp thấp.
- **Không có ảnh:** `curated/` không có tham chiếu ảnh, trong khi các trang model và trang bundle có ảnh sản phẩm và màn hình; chunk có `assets = []`.
- **Chunk `embed_text`** dựng "model · tiêu đề tài liệu · đường dẫn mục · Từ khóa · ---· nội dung": bảng 4 model → tiêu đề có 4 tên model (loãng); `keywords` chỉ là tên model/tên đầy đủ (không có từ tính năng).

## 3. Độ phủ trang PDF (đã xem ảnh trang)

| Trang | Nội dung | Có trong chunk? |
|---|---|---|
| 1, 3 | bìa, giới thiệu (chưa xem p3) | không |
| 2 | **About Us** (QS Technology, từ 11/2018, hỗ trợ kỹ thuật trực tuyến 1:1) | không |
| 4–5 | tóm tắt 7 controller | **có** (P3) |
| 6–7 | bảng chọn model | **có** (T1, T2) |
| 8–14 | trang riêng 7 model | **có** (P1, P2) |
| 15–16 | **QS-Servo** (Pulse Train–EtherCAT; 220VAC; 400W–55kW; encoder 17/20/23 bit, tuyệt đối; chế độ vị trí/tốc độ/mô-men; cổng EtherCAT CN4/CN5) | **không** |
| 17 | chưa xem | không |
| 18 | "QS Controller – hệ sinh thái CNC": controller, trọn bộ servo, board mở rộng | không |
| 19–21 | trọn bộ hệ thống theo model | **có** (gộp vào P3) |
| 22 | **Phụ kiện: board** DAC-12-FCV1, PID V1_10722, IO-LINK-1616, I/O LINK_RLTR_07, I/O LINK_32 (mô tả và số cổng) | **không** |
| 23 | **Phụ kiện: tool setter** (±0,001 mm, 24VDC), MPG pendant (5V, x1/x10/x100, 4–6 trục), **đầu dò 3D có dây và không dây** (±0,001 mm), nguồn xung, cáp | **không** |
| 24 | **Liên hệ**: địa chỉ văn phòng/nhà máy, điện thoại, website, email hỗ trợ | không |

Hệ quả cho khách hàng thật: câu "báo giá đầu dò tâm CNC", hỏi thông tin servo, board I/O, MPG, địa chỉ/điện thoại liên hệ **không có tài liệu trả lời** dù PDF có (RC13 trong bộ câu CRM thật). Ghi nhận C-2 của STATE ("còn thiếu servo, board, phụ kiện") đã đúng; chưa có `company_info` nào.

## 4. Nhóm chunk và phán quyết (dùng để điền `verdict` trong `chunk_review.json`)

| Nhóm | Chunk | Đối chiếu PDF | Phán quyết đề xuất |
|---|---|---|---|
| P1 tổng quan | 7 (id 642, 645, 648, 651, 654, 657, 660) | p8–14 khớp (trừ quyết định C-xx) | **`ok`**; việc còn lại là bổ sung `spec_attributes`, ảnh (không chặn duyệt) |
| P2 thông số | 7 (643, 646, 649, 652, 655, 658, 661) | p8–14 khớp; 6AH theo C-02…C-05 | **`ok`** |
| P3 thẻ tóm tắt + trọn bộ | 7 (644, 647, 650, 653, 656, 659, 662) | p4, p19 khớp chữ in | `fix`: tách phần riêng, sửa dải trang |
| T1 bảng A | 8 (663–670) | p6 khớp (trừ C-09, đã quyết) | `fix`: cấu trúc tìm kiếm (tách theo model/hàng có chữ), tiêu đề duy nhất |
| T2 bảng B | 8 (671–678) | p7 khớp | `fix`: như T1, tách 6AV/6AH |

P1/P2 (14 chunk) đủ điều kiện `ok` ngay; P3/T1/T2 (23 chunk) đúng về nội dung nhưng `fix` về cách chia theo yêu cầu cải thiện tìm kiếm. Việc điền verdict phải do Toma/QS quyết (luật doc-ingest: không gán im lặng); mình chưa ghi gì vào `chunk_review.json`.

## 5. Đề xuất sửa theo bước (chưa làm)

1. **Bước 5 (chia chunk):** thêm chunk theo hàng có chữ cho bảng ("F54: không quản lý tuổi thọ dao (Tool-life management); F86, F10T, 10S: có"), `product_models` đúng một model nếu có thể; tách cột 6AV/H; tiêu đề bảng duy nhất ("… (F54/F86/F10T/10S)"); P3 chỉ giữ phần riêng (thiết bị đi kèm, tùy chọn), bỏ phần lặp; lưu danh sách trang (`4, 19`) thay vì dải.
2. **Bật `vi_keywords`** (quyết định của Toma) để tận dụng nhãn tiếng Việt đã có.
3. **Bước 2 (biên soạn):** soạn thêm trang 15–16 (servo), 22 (board), 23 (phụ kiện), 18, 24 (liên hệ), 2 (About Us) với cùng quy trình có duyệt; ghi quyết định cho mâu thuẫn còn mở (EtherCAT optional, touch).
4. **Ảnh:** thêm tham chiếu ảnh sản phẩm/bundle/phụ kiện để chunk có `assets` (ảnh bundle p19–21 và phụ kiện p22–23 là thông tin chính của các trang này).
5. **Bước 4 (kiểm):** `curate-check` chỉ kiểm giá trị chữ in; ô ✓/✗ và "(Option)" là ảnh/ký hiệu nên **không kiểm được bằng chữ** (nguồn gốc của C-09). Thêm kiểm ngoại tuyến cho ô ký hiệu (so với ảnh trang) hoặc duyệt tay bắt buộc mọi ô ký hiệu.
6. **Cách làm:** theo luật doc-ingest, tạo run mới (không ghi đè `curated-a`), cập nhật `STATE.md`/`LOG.md` của luồng doc-ingest, rồi nạp lại cùng `doc_id` + `doc_version` mới.

## 6. Giới hạn của lần kiểm này

- Đã xem ảnh các trang 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19, 22, 23, 24. **Chưa xem** các trang 1, 3, 17, 20, 21 (bìa, giới thiệu, trang bundle của 6AH/6AV/10i); đối chiếu P1/P2 là theo các trường chính, không từng từ.
- File tải về nằm ở thư mục tạm của phiên (không trong repo): `…\scratchpad\catalog_v11\catalog_v1.1.pdf`; `sha256` trùng bản đã chạy nên không cần dùng thêm.
- Mình chưa sửa YAML, chưa sinh run mới, chưa đổi `review_status` hay verdict của run `curated-a` (xem mục 7: bản nháp để riêng).

## 7. Bản nháp verdict (chờ Toma/QS duyệt)

File: `data/ingest_runs/qs_catalog/review-draft-2026-11-25/chunk_review.draft.json` (thư mục mới; **không** ghi vào `curated-a/build/chunk_review.json`). Đúng schema `ChunkReviewFile`: giữ nguyên `chunk_key`
và `content_hash`, điền `verdict` và `note` (mở đầu bằng "[NHÁP Claude …]"), `reviewer` để trống để người duyệt tự điền. Tổng: **14 `ok`, 23 `fix`, 0 `pending`**.

| `chunk_key` (id DB) | Nhóm | Verdict nháp | Lý do ngắn |
|---|---|---|---|
| C0000, 0003, 0006, 0009, 0012, 0015, 0018 (642, 645, 648, 651, 654, 657, 660) | P1 tổng quan, F54/F86/F10T/10S/6AH/6AV/10i | `ok` | khớp p8–14; giá trị theo C-xx; việc còn lại (spec_attributes, ảnh) không chặn |
| C0001, 0004, 0007, 0010, 0013, 0016, 0019 (643, 646, 649, 652, 655, 658, 661) | P2 thông số | `ok` | khớp p8–14; 6AH theo C-02…C-05 |
| C0002, 0005, 0008, 0011, 0014, 0017, 0020 (644, 647, 650, 653, 656, 659, 662) | P3 thẻ tóm tắt + trọn bộ | `fix` | tách phần riêng, bỏ phần lặp, danh sách trang thay dải |
| C0021–C0028 (663–670) | T1 bảng A (p6) | `fix` | đổi cấu trúc chunk bảng (theo hàng có chữ/theo model), tiêu đề duy nhất |
| C0029–C0036 (671–678) | T2 bảng B (p7) | `fix` | như T1, tách 6AV/6AH |

Cách dùng sau khi duyệt (theo luật doc-ingest): chép verdict đã chốt vào `chunk_review.json` của **run mới** rồi chạy lại `curated-build`; chunk `ok` có nguồn đã `verified` sẽ thành `approved`.
Lưu ý: `fix` ở P3/T1/T2 là yêu cầu đổi cách chia, nên các chunk này cần build lại (đổi `content_hash`) và duyệt lại, không thể chỉ chuyển trạng thái.
