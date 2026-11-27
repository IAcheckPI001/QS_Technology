# Kế hoạch đối chiếu kiểm duyệt chunk `fix` của `crm-1.0-a` (2026-11-25)

Đầu vào: 372 chunk lá có verdict `fix` ([danh sách](p4_crm_chunk_review_2026-11-21.md)). Verdict do `Codex PDF comparison` ghi, chưa người xác nhận.
Số liệu bên dưới tính từ 10 file `chunk_review.json` và `chunks.jsonl` của run (2026-11-25).

## 1. Mục tiêu và phạm vi

- Biến 372 verdict tự động thành verdict cuối đã được xác nhận độc lập: `fix_confirmed`, `false_positive`, `fix_minor` (dùng được, cần ghi chú), `unsure`.
- Gán mỗi chunk lỗi vào một nguyên nhân gốc (I-xx) và một hành động xử lý, để sửa **ở luật pipeline hoặc nguồn**, không sửa tay từng chunk.
- Đo độ chính xác của bộ duyệt tự động (bao nhiêu `fix` là đúng) để quyết định có tin 343 chunk `ok` và 24 `pending` hay không.
- Ngoài phạm vi: sửa chunk, đổi `review_status`, nạp DB. Bước đó chờ I-53 và kết quả kế hoạch này.

## 2. Đặc điểm tập 372 chunk (để định cỡ công việc)

| Chỉ số | Giá trị |
|---|---|
| Nội dung trùng hash | 313 hash khác nhau; 37 nhóm trùng gồm 96 chunk → kiểm 1 lần mỗi nhóm, tiết kiệm 59 lượt |
| Loại chunk | figure 180, overview 52, table 47, wiring 45, procedure 32, parameter 10, pinout 3, dimension 2, alarm 1 |
| Có ảnh đính kèm | 258 chunk |
| Số trang PDF khác nhau | 445 cặp (tài liệu, trang); 243 chunk một trang, 129 chunk hai trang trở lên |
| Độ dài nội dung | trung vị 158 ký tự, lớn nhất 2.244; tổng khoảng 121 nghìn ký tự |
| Ghi chú nói "chỉ còn tiêu đề/caption/nhãn" | khoảng 79 chunk |
| Theo tài liệu (lá `fix`) | f10t-operation-vi 100; f54-operation-en 65; 6ave-operation-en 55; 6ah-operation-en 54; 10iv-operation-en 50; f86-operation-en 30; 4 bản Installation 3–6 mỗi bản |

## 3. Nguyên tắc đối chiếu

1. **Nguồn sự thật là trang PDF gốc** (ảnh trang hoặc text layer), không phải ghi chú của bộ duyệt tự động.
2. **Người duyệt thứ hai độc lập**: không dùng lại cùng bộ duyệt tự động. Ưu tiên người (Toma hoặc người được chỉ định); có thể thêm một model khác chạy song song để so lệch, nhưng kết luận cuối do người xác nhận.
3. **Rủi ro quyết định mức kiểm**: chunk có thể làm chat trả sai số liệu, mã, chân cắm, thủ tục thì kiểm 100%; chunk chỉ là nhãn/hình thì lấy mẫu.
4. **Không sửa trực tiếp `chunk_review.json`** (file chính thức của Toma). Ghi kết quả vào file riêng (mục 5), Toma quyết định gộp.
5. **Ghi nguyên nhân gốc**: một nguyên nhân gốc được xác nhận trên mẫu thì áp cho cả lớp, không kiểm lặp lại từng chunk cùng lớp.

## 4. Các bước

### Bước 0 — Chuẩn bị (khoảng 0,5 ngày)
- Chụp bản đóng băng 10 file `chunk_review.json` (kèm hash) vào `data/ingest_runs/_summary/recheck-2026-11-25/` để đối chiếu về sau.
- Sinh `fix_recheck.csv` từ script (không sửa pipeline): mỗi dòng một chunk lá `fix`, cột: `doc, chunk_key, chunk_type, page_start, page_end, auto_note, content_hash, dup_group, risk_class, sample_flag`, cùng các cột để trống cho người duyệt (mục 5).
- Chuẩn bị ảnh trang đối chiếu: render đúng trang `page_start–page_end` của PDF nguồn cho từng chunk (445 trang); xác định đường dẫn PDF theo manifest, chưa có trong repo (gitignored).
- Gộp 37 nhóm trùng thành một dòng kiểm với danh sách chunk thành viên.

### Bước 1 — Phân lớp rủi ro (script + 0,5 ngày soát)
| Lớp | Điều kiện | Mức kiểm | Số chunk (ước) |
|---|---|---|---|
| R1 | `procedure`, `parameter`, `alarm`, `dimension` | 100%, so từng bước, mã, giá trị | 45 |
| R2 | `table`, `pinout`, `wiring` | 100%, so từng hàng/chân/dây/mã | 95 |
| R3 | `overview` | lấy mẫu 25%, tối thiểu 5 mỗi tài liệu | 52 |
| R4 | `figure` | lấy mẫu 20%, tối thiểu 5 mỗi tài liệu; riêng nhóm "chỉ có caption" chờ quyết định chính sách hình (mục 7) | 180 |
| RL | `f10t-operation-vi` (mọi loại) | kiểm 15 chunk mẫu để xác nhận I-29, sau đó coi cả lớp là `rule_fix` (OCR tiếng Anh trên tài liệu Việt) | 100 (chồng lên các lớp trên) |

Chunk thuộc RL không đếm lại ở các lớp trên; số chính xác lấy từ script. Quy tắc mở rộng mẫu: nếu trong mẫu của một lớp × tài liệu có từ 2 chunk `false_positive` trở lên (tức dưới khoảng 90% xác nhận), kiểm 100% lớp đó.

### Bước 2 — Đối chiếu từng chunk (khoảng 1,5–2 ngày người; ước lượng)
Cho mỗi chunk trong mẫu hoặc lớp 100%:
1. Mở ảnh trang PDF tương ứng và nội dung chunk cạnh nhau.
2. So: chữ/mã/số, hàng-cột bảng, nhãn chân/dây, thứ tự bước thủ tục, hình đính kèm có đúng trang không.
3. Ghi một trong bốn kết luận cuối (mục 5), mức nghiêm trọng, nguyên nhân gốc, hành động.
4. Với `false_positive`: ghi lý do ngắn (ví dụ "chữ 10I/l chỉ là kiểu chữ dễ nhầm, ngữ cảnh đủ") để chỉnh bộ duyệt tự động.

Ước lượng công sức: R1+R2 khoảng 140 chunk × 3 phút ≈ 7 giờ; R3+R4 mẫu khoảng 60–70 chunk × 2 phút ≈ 2 giờ; RL 15 chunk ≈ 0,5 giờ; cộng bước soát và tổng hợp. Chỉ là ước tính, chưa đo.

### Bước 3 — Gán nguyên nhân gốc và hành động
Mỗi chunk `fix_confirmed` gắn:
- **Nguyên nhân gốc** theo mã sẵn có: I-51 (bản scan), I-55 (text layer hỏng), I-56 (bảng cổng), I-57/I-58 (ảnh/chữ trong ảnh), I-59 (ảnh nuốt chữ), I-60 (chunk hình gộp trang), I-29 (OCR ngôn ngữ). Nguyên nhân mới thì mở ID tiếp theo.
- **Hành động**: `rule_fix` (sửa luật rồi chạy lại), `re_ocr`, `manual_curate` (biên soạn như `curated/`), `exclude_pages` (trang không cần), `drop_chunk` (chunk chỉ có nhãn, không có giá trị tra cứu), `merge` (gộp với chunk lân cận).
- Tổng hợp thành bảng nguyên nhân × hành động × số chunk để Toma duyệt thứ tự sửa (liên hệ thứ tự I-55 → I-59 → I-54 → I-57 → I-58 → I-56 → I-60).

### Bước 4 — Hiệu chỉnh bộ duyệt tự động và đóng vòng
- Tính độ chính xác bộ duyệt tự động: tỷ lệ `fix_confirmed` trên các chunk đã kiểm, theo lớp và theo tài liệu.
- Lấy mẫu ngược 40 chunk `ok` (stratified theo tài liệu, ưu tiên R1/R2) và toàn bộ 24 `pending` để ước tính tỷ lệ bỏ sót; nếu bỏ sót vượt khoảng 5%, kiểm thêm lớp `ok` có rủi ro cao.
- Cập nhật `STATE.md`, thêm mục `LOG.md`, bảng nguyên nhân gốc vào báo cáo; Toma quyết định gộp verdict cuối vào `chunk_review.json`.

## 5. Mẫu bản ghi đối chiếu (`fix_recheck.csv`, không commit)

| Cột | Giá trị |
|---|---|
| `final_verdict` | `fix_confirmed` / `false_positive` / `fix_minor` / `unsure` |
| `severity` | S1 sai giá trị, mã, chân, bước (nguy hiểm khi trả lời); S2 thiếu nội dung; S3 hình thức |
| `root_cause` | mã I-xx |
| `action` | `rule_fix` / `re_ocr` / `manual_curate` / `exclude_pages` / `drop_chunk` / `merge` |
| `reviewer`, `date`, `pdf_page_checked` | người, ngày, trang đã mở |
| `note` | một dòng, tự đủ nghĩa |

## 6. Tiêu chí hoàn thành

- 100% chunk lớp R1, R2 có `final_verdict` do người xác nhận; lớp lấy mẫu đạt cỡ mẫu hoặc đã mở rộng 100%.
- Mỗi chunk `fix_confirmed` có `root_cause` và `action`; bảng tổng hợp theo nguyên nhân gốc có số chunk.
- Có số độ chính xác của bộ duyệt tự động (theo lớp) và ước tính tỷ lệ bỏ sót trên `ok`/`pending`.
- `unsure` còn lại ≤ 5% tập đã kiểm, kèm lý do.
- Tài liệu cập nhật (STATE, LOG, báo cáo kết quả); không có thay đổi nào trong DB hay `review_status`.

## 7. Quyết định cần Toma trước khi bắt đầu

1. **Ai là người duyệt thứ hai** (người cụ thể; có thêm model đối chiếu song song không).
2. **Chính sách chunk hình chỉ có caption/nhãn** (khoảng 79 chunk): giữ, gộp vào chunk lân cận, hay bỏ (`drop_chunk`). Quyết một lần thì lớp R4 không cần kiểm từng chunk.
3. **Ngưỡng chấp nhận lấy mẫu** (90% xác nhận, 5% bỏ sót) và cỡ mẫu tối thiểu có phù hợp không.
4. **Ưu tiên tài liệu**: bắt đầu từ bản Installation (nhỏ, xong nhanh, kiểm bộ duyệt) rồi đến `f54-operation-en`/`f86-operation-en`, hay theo nhu cầu chat (F54, F86 trước).
5. **I-53**: kết quả đối chiếu chỉ có tác dụng duyệt chunk sau khi chọn cơ chế gỡ mã chặn.

## 8. Rủi ro

- Run `crm-1.0-a` đã cũ hơn `crm-1.1-t0` (Bậc 0): một số lỗi (I-55, I-59, I-54, I-56 nhẹ) có thể đã được sửa ở run mới. Nên chạy script đối chiếu `chunk_key`/hash giữa hai run để loại các chunk đã đổi nội dung khỏi danh sách kiểm trước khi bắt đầu; run `crm-1.1-t0` chưa có ảnh (chạy không kèm `--pdf`).
- Ảnh trang và PDF nằm trong `data/` (gitignored): kế hoạch phụ thuộc máy có đủ dữ liệu; cần xác nhận đường dẫn PDF ở Bước 0.
- Verdict tự động có thể thiên về `fix` với lỗi chữ nhỏ (ví dụ nhầm `I`/`l`); không loại trừ trước khi có số đo ở Bước 4.
