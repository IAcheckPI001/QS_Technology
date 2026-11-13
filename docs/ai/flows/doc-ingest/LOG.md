# Nhật ký luồng doc-ingest

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính. Sau khi thêm mục, viết lại [STATE.md](STATE.md).
Mẫu mục: [../_template/LOG.md](../_template/LOG.md).

Các mục tới 2026-11-09: [LOG-archive-2026-11-09.md](LOG-archive-2026-11-09.md).

## 2026-11-14 · Nội dung ảnh (vision) trong chunk: chỉ câu mô tả vào phần tìm kiếm · loại: quyết định

- Toma xác nhận hướng đã thảo luận ngày 2026-11-13 trên B0074 (bảng `item | detail` của f54:p049:e013, e019). Lý do:
  bảng facts không giúp lọc (không nằm trong cột lọc nào), làm loãng vector (B0074 vượt 800 token, đẩy tóm tắt VI ra
  khỏi `embed_text`) và gây nhiễu FTS (từ lặp "cổng", "vào", "ra", "dây" kéo chunk lên ở câu không liên quan).
- Ba điểm chốt:
  1. **`embed_text` chỉ nhận câu mô tả ngắn, mỗi ảnh một câu**, có **thông tin phân biệt** (dải mã, quan hệ chính;
     vd. "…IN0–IN31 ứng với X300–X337, chung chân CX.0–CX.3 nối 24V"), không chỉ nêu loại ảnh. Câu mô tả vẫn phải
     kiểm chéo OCR (vision-trial-3 gán nhầm ảnh ở f54:p050:e002).
  2. **Bỏ fact chỉ dịch nhãn** (vd. "Output port 0 → cổng ra 0"): không có quan hệ, không có ích ở đâu.
  3. **Fact có quan hệ** (chân ↔ tín hiệu ↔ màu dây; mã tham số ↔ tên ↔ đơn vị) **để ngoài phần embed** (metadata
     hoặc `assets` của ảnh), chỉ dùng làm ngữ cảnh khi trả lời. Giữ hay không chờ đo Bước 4; muốn dùng thì website-qa
     phải nạp thêm vào ngữ cảnh (chưa có).
- Còn mở: vision có thật sự cần không — đo ở Bước 4 với 3 biến thể (A) không vision, (B) thêm câu mô tả vào
  `embed_text`, (C) thêm cả facts; bộ câu có loại chỉ trả lời được từ ảnh. Mã từ OCR vẫn đi vào `keywords` như hiện tại.
- Không đổi code. `vision-trial-3/vision_extract.py` (ngoài pipeline) vẫn xuất `facts`; khi đưa vào pipeline phải theo
  ba điểm trên.

## 2026-11-13 · I-46: scope theo nội dung (thử nghiệm sau CP-I46) (run `f54/eval-m`, `f86_italliation/eval-m`) · loại: thay đổi

- `schemas/profile.py`: `ScopeContentRule` (scope + regex tiêu đề / regex nội dung / loại chunk), `Chunking.
  scope_content_rules`, `scope_title_min_level` (mặc định 2: không xét tên phần cấp 1 như "PART 2: WIRING -
  CONNECTION - SETTING"). `build/fields.py` `_content_scopes`: scope theo manifest + loại chunk như cũ, **cộng thêm**
  scope theo nội dung (không bớt). Luật trong `profiles/default.yaml` (qs_controller kế thừa): configuration (tiêu đề
  setting/parameter/configur…; nội dung "PARAMETER screen", "user password", "parameter (status) description",
  "configure/set the parameters"), operation (chỉ dấu hiệu rõ: operating instructions, MANUAL MODE, AUTO mode, CYCLE
  START, "process (M…)", "when command M… is called"; không dùng press/screen/program), maintenance ("reports an
  error", "the cause is/of", troubleshoot), installation (loại wiring/pinout/dimension). Contract C2 §4 cập nhật.
- Test: `test_chunker.py` +1 (`test_content_scope_rules_add_but_never_remove`); `tests\doc_ingest` → 366 passed (test
  scope cũ không đổi).
- Run mới (chép `eval-l`, build + carry): F54 296/296 verdict; **chỉ scope đổi**, mọi trường khác giữ nguyên; 80
  chunk đổi (gồm cha), không chunk nào bị bớt scope; lá `configuration` 34 → 103, `installation` 152 → 153 (B0002
  bản vẽ kích thước), `operation` 91 → 92 (B0175 quy trình M100), `maintenance` 1 → 2 (B0175). F86 Installation: 0 đổi.
  Bảng so sánh: `data/retrieval_eval/scope_test/scope_diff_f54.md`, `scope_diff_f86.md`. Cần Toma xem: B0175 thêm cả
  `maintenance` (mô tả M100 có câu báo lỗi); B0234 màn hình Offset thêm `configuration` ("Set the parameters of the
  work…").
- Chưa nạp DB (cổng: Toma duyệt bảng scope).

## 2026-11-13 · CHECKPOINT CP-I46 (trước khi sửa I-46) · loại: quyết định

- Toma: gắn cờ bước hiện tại; nếu kết quả I-46 không đạt thì quay lại. Checkpoint `data/checkpoints/CP-I46/`
  (gitignore): bản sao `build/fields.py`, `schemas/profile.py`, `profiles/default.yaml`, `profiles/qs_controller.yaml`,
  `tests/doc_ingest/test_chunker.py`, contract C2, STATE doc-ingest/website-qa + `README.md` ghi trạng thái (run
  `eval-l`, DB `doc_chunks_v2` F54 296 + F86 23 draft, mốc eval `20261113-172639`, `20261113-173701-scope_test`) và
  lệnh khôi phục (chép file; nạp lại `eval-l` bằng loader).

## 2026-11-13 · Bảng thuật ngữ: electronic gear ratio = "tỷ số truyền điện tử" · loại: quyết định

- Toma: `electronic gear ratio` → `tỷ số truyền điện tử` (trước: "tỉ số bánh răng/truyền điện tử"). Bằng chứng: eval
  tra cứu Q9 "công thức tính tỷ số truyền điện tử F54" — chunk mong đợi hạng 5, vector 0,436 vì tóm tắt VI viết "tỉ
  số bánh răng điện tử" (website-qa LOG cùng ngày).
- `profiles/qs_controller.yaml`; phiên bản làm giàu đổi `v4+g1cb3720f` → `v4+g45729502`: bản ghi cũ vẫn dùng tới khi
  chạy lại `cli enrich` (sẽ làm cùng prompt v5). Chunk trong `doc_chunks_v2` chưa đổi.
- Test `tests\doc_ingest` → 365 passed.

## 2026-11-13 · Adapter `doc_chunks_v2` + loader (bước 3b, 4 của D-009) (run `f54/eval-l`, `f86_italliation/eval-l`) · loại: thay đổi

- `export/doc_chunks_v2.py`: dòng bảng `doc_chunks_v2` (§10 [p2_doc_chunks_schema_review.md](../../reports/p2_doc_chunks_schema_review.md));
  `normalize_code` (mã chung: `#`+số hoặc 1–4 chữ + số, bỏ số 0 đầu; không nhận `24V`, `GND`); `chunk_codes` (tham số
  có cấu trúc, dải trải tối đa 64 mã — dài hơn giữ hai đầu, mã I/O, nhãn hình đã xác minh, **bỏ tên model**: "F54"
  có ở 121 nhãn); `review_status` = `approved` chỉ khi cổng 2b đạt **không tạm** + verdict `ok` đúng `content_hash` +
  không có mã review chặn + (lá) làm giàu đã duyệt 2c; kiểm dòng và cả bộ (khóa trùng, `parent_key` trỏ cha).
- `build` ghi thêm `build/doc_chunks_v2.jsonl`; `chunk_quality.json` thêm `export_errors_v2`, `review_status_v2`; CLI
  in dòng "doc_chunks_v2".
- Loader mới (ngoài `doc_ingest`): `app/modules/chunking_loader/load_ingest_run.py` — `--dry-run` / `--apply
  [--embed-parents]` / `--delete --doc-id [--doc-version]`; kiểm model theo `REGISTRY["product_models"]`; embed trước
  (`OpenAIProvider.embed`, lô 100, kiểm số chiều); một transaction: xóa bản cùng (`doc_id`, `doc_version`), insert cha
  lấy `id`, gán `parent_id` cho con (sửa E-01).
- Run mới (chép từ `eval-k`/`eval-j-regress`, xóa đầu ra build cũ, build venv chính + `--labels` + carry): chunk
  giống hệt run cũ (296/296, 23/23); verdict chép 296/296 (F54), 0/23 (F86). `doc_chunks_v2`: F54 296 `draft`, F86 23
  `draft` (cổng 2b tạm → đúng quyết định), 0 lỗi ràng buộc. F54: 177 dòng có mã, 1.919 mã, nhiều nhất 120 mã/chunk
  (ảnh màn hình tham số liệt kê M1920–M1959 — nhiễu có thể có cho nhánh mã, đo ở Bước 4).
- Dry-run loader: F54 243 lá cần embed (~87,7 nghìn token ≈ 0,0018 USD; `--embed-parents` 296 dòng ≈ 0,0021 USD);
  F86 23 dòng ≈ 0,0001 USD; 0 lỗi.
- Test: `test_export_v2.py` (7), `tests/test_load_ingest_run.py` (6). Từ `backend/`: `..\.venv-ingest\Scripts\python.exe
  -m pytest tests\doc_ingest` → 365 passed; `.\venv\Scripts\python.exe -m pytest tests` → 1068 passed, 14 skipped.
- Chưa ghi DB (Cổng 2).

## 2026-11-13 · Chuẩn bị chạy thử thật trên Supabase: đánh giá lại `doc_chunks` (Bước 5 sơ bộ) · loại: phân tích

- Kế hoạch đã duyệt: kiểm Supabase (chỉ đọc) → tài liệu đánh giá schema → Toma duyệt → SQL v2 + adapter → loader →
  `evals/run_retrieval_eval.py` trên DB thật → website-qa dùng v2. Đã làm tới bước tài liệu đánh giá, dừng chờ duyệt.
- Bằng chứng mới cho thiết kế khóa: giữa `eval-h` và `eval-k`, 0/294 chunk giữ `chunk_key`, 294/296 khớp
  (`content_hash`, `section_path`) → `chunk_key` chỉ là khóa trong một phiên bản; nhãn đánh giá dùng cặp hash + path.
- Đề xuất: [p2_doc_chunks_schema_review.md](../../reports/p2_doc_chunks_schema_review.md) (cột `doc_version`,
  `chunk_role`, `codes` trải dải, `printed_page_*`, `embedding_model`, `source`, `review_status`; bỏ check model cứng,
  loader kiểm theo registry; cha không bắt buộc embedding). Hiện trạng DB và lệch repo: website-qa LOG cùng ngày.
- Không đổi code `doc_ingest`.

## 2026-11-13 · Đóng cổng 2c của làm giàu v4: không đạt (run `f54/eval-k`) · loại: quyết định

- Toma đóng verdict (b) của mẫu 2c (30 chunk) mà không chấm từng chunk. Cổng 2c của phiên bản `v4+g1cb3720f`:
  **không đạt** — Claude đề xuất 17 ok / 13 fix, có 2 lỗi nặng (B0040 "trục chính", B0287 "bù trục chính": nội dung
  không có trong chunk). Các nhóm lỗi: câu hỏi không trả lời được (chunk chỉ liệt kê mã, chunk danh mục, chunk chỉ có
  hình), đoán trên chunk mỏng, thuật ngữ (homing switch, soft limit, board, workpiece homing).
- `chunk_review.json` không ghi verdict làm giàu cho mẫu này (30 chunk vẫn `pending`, hết hạn khi đổi phiên bản).
  Mẫu 2c mới chọn sau prompt v5 + bảng thuật ngữ bổ sung, và sau quyết định hướng ảnh (vision) theo Bước 4.
- Không đổi code.

## 2026-11-13 · Định nghĩa phạm vi: luồng chung cho mọi PDF upload, F54 là thí điểm · loại: quyết định

- Toma: luồng chunking không chuyên biệt cho F54; được triển khai để phân tích, xử lý và tạo chunk cho các PDF được
  upload. F54 là bản áp dụng đầu để phát hiện, khắc phục lỗi mới và chuẩn hóa luồng cho các PDF sau.
- Ghi vào README mục Phạm vi kèm nguyên tắc: sửa bằng luật chung; phần phụ thuộc hãng/dòng tài liệu đặt ở profile;
  ghi đè riêng tài liệu chỉ qua manifest có lý do; lỗi mới ghi dạng lỗi (I-xx) + test + hồi quy F86; đánh giá ngưỡng,
  cổng, chi phí theo cả lô.
- Áp vào việc đang làm: luật tầng 1 phân nhóm ảnh (`vision-trial-3/classify_figs.py`) đang chứa giá trị riêng QS/F54
  (watermark "QS TECHNOLOGY", phím máy, từ màn hình JOG/READY, phần mềm DNC Explorer) → khi đưa vào pipeline phải
  chuyển sang profile; luật chung chỉ gồm tín hiệu không phụ thuộc hãng (OCR có/không chữ, khung đỏ, mật độ mã, loại
  chunk). Ghi đè thủ công trước đây (`exclude_pages: [1, 2]` của F54) vẫn đúng nguyên tắc (manifest + lý do).
- Không đổi code. Ảnh hưởng: các đề xuất sau (vision, cổng 2c, Bước 4) đánh giá cả trên F86, không chỉ F54.

## 2026-11-13 · Thử vision theo nhóm ảnh: tầng 1 (luật) + tầng 2 (LLM xếp nhóm) + kiểm chéo OCR, 14 chunk · loại: thử nghiệm

- Toma chốt quy trình 3 tầng: tầng 1 luật tự động gán nhóm; ảnh "chưa rõ" → tầng 2 (gpt-4.1-mini tự xếp nhóm trong
  cùng lần gọi trích); tầng 3 Toma duyệt. Script ngoài pipeline (không sửa code); kết quả, script và báo cáo duyệt:
  `data/ingest_runs/f54/vision-trial-3/` (`fig_groups.json`, `extract.json`, `report.md`).
- Tầng 1 (`classify_figs.py`, `.venv-ingest`: Pillow/numpy có sẵn): tín hiệu = OCR thô đã bỏ watermark/rác, khung đỏ
  (màu điểm ảnh), loại chunk. 208 ảnh lá: **192 tầng 1**, **13 tầng 2**, **3 không gửi** (B0080 đầu cáp, B0275 QR,
  B0281 logo). Nhóm: đấu dây 71, tham số 35 (gồm màn hình bit +0..+7), trình tự 5, giản đồ xung 5 (mới, B0109), mặt máy
  khoanh 4, thao tác/PLC/phần mềm PC 70, mặt máy 1, kích thước 1. Khung đỏ 113/208.
- Trích (`vision_extract.py`): quy tắc riêng theo nhóm, output `images[{group, facts[{item, detail}], desc_vi}]` + tóm
  tắt/câu hỏi/từ khóa; 14 chunk (8 Toma chọn + B0011, B0020, B0177, B0002, B0003, B0112), 27 ảnh; 79.452 + 8.198
  token ≈ **0,045 USD**. Kiểm chéo OCR: unverified (mã model viết, OCR không có), missing (mã OCR có, model bỏ; nhóm
  1–3), value_leak (giá trị màn hình lọt vào; nhóm 2, 4, 5).
- Claude đối chiếu ảnh gốc, đề xuất 10 ok / 4 fix: **B0074** gán nhầm thứ tự 5 ảnh, bỏ sót cả ảnh OUTPUT (Y300–Y337)
  — kiểm OCR bắt được (độ phủ 0,05, 32 mã unverified); **B0109** diễn giải sai sóng Pul/Dir chiều âm; **B0002** số đúng
  nhưng đoán sai "đo cái gì"; B0196 sai thuật ngữ ("về home chi tiết gia công"). Đúng quy tắc: B0050 ghép đủ 14 chân ↔
  màu dây; B0149/B0161/B0204 không ghi giá trị màn hình; B0147 đọc đúng 3 giai đoạn (OCR đọc hỏng → 2 unverified giả).
  Tầng 2: B0003, B0112, ảnh Shift+7 của B0196 → `8_khac`, hợp lý.
- Phát hiện phụ: B0011 có 2 ảnh trùng nhau, B0109 có ảnh lặp (trùng hình chưa bị loại ở chuẩn hóa); ảnh I/O link ghi
  IN24(X320)… (lỗi in PDF, đúng ra X330); ảnh B0275 `e005` chỉ có mẩu watermark "QLOGY" → nên vào danh sách bỏ.
- Bài học cho thiết kế: ảnh dày (nhóm 1, 2) nên gọi **mỗi ảnh một lần** (chunk 5 ảnh làm lệch thứ tự); nhóm 7 chỉ ghi
  số, không đoán chiều đo; "unverified" nghĩa là cần người xem, không phải chắc chắn sai.
- Không đổi contract/schema/code pipeline. Chờ Toma duyệt 14 chunk (`report.md`, tầng 3). Verdict mẫu 2c vẫn tạm giữ.

## 2026-11-13 · Phân tích nhóm ảnh cho làm giàu vision + luật lọc theo OCR (run `f54/eval-k`) · loại: phân tích

- Chỉ đọc dữ liệu (`chunks.jsonl`, `figure_ocr.jsonl`, ảnh gốc); không sửa code, không gọi LLM. Verdict mẫu 2c vẫn tạm giữ.
- Toma phân nhóm ảnh khi xem các chunk; Claude đối chiếu ảnh B0147, B0149, B0161, B0177, B0196, B0204. Nhóm và đề xuất:
  (1) sơ đồ đấu dây/mạch — gửi, trích đủ cặp chân ↔ tín hiệu ↔ màu dây; (2) màn hình bảng tham số (B0149, B0086,
  B0193) — lấy mã, tên, **đơn vị** (B0149: "mm/min" chỉ có trong ảnh), KHÔNG lấy giá trị đang hiển thị (2000, 16576…
  là giá trị máy mẫu); (3) sơ đồ chuyển động/trình tự — B0147 có tham số từng giai đoạn về home, B0177 chỉ mũi tên
  (9)(10); (4) ảnh mặt trước có khoanh đỏ (B0196) — chỉ mô tả vùng khoanh; (5) màn hình thao tác/PLC (B0161 là màn
  hình PLC Ladder + tham số, không phải sơ đồ mạch; B0204) — chỉ tên màn hình/nút được khoanh; (6) ảnh trang trí — bỏ.
- Câu hỏi "LLM có mô tả hết giá trị trong ảnh": không (B0074 bỏ IN0=X300…, B0050 không ghép màu dây với chân; giới hạn
  600 ký tự) và không nên với giá trị minh họa — B0204 chứa tọa độ, giờ, đường dẫn file mẫu (nhiễu). Giá trị có tính
  quy định nên trích có cấu trúc (vd. trường `figure_facts`), kiểm chéo với nhãn OCR.
- Phát hiện phụ: ảnh B0147 ghi "#12110 → #12113" (Homing Feedrate 3rd) → xác nhận #12103 ở B0159 là lỗi in (I-40d).
  Ảnh B0204 (chunk ghi chú) minh họa các bước nằm ở chunk anh em B0205; ảnh bị cắt mất cột "Instructions".
- Luật Toma đề xuất "OCR không ra chữ/số → ảnh trang trí, không gửi vision": 208/208 ảnh lá đã OCR; chỉ **3/208** rỗng
  sau khi bỏ watermark — B0281 logo (đúng), B0080 ảnh đầu cáp giắc DB (có ích), B0275 **mã QR** (chứa link, OCR không
  đọc được). Ảnh "chỉ có máy" vẫn có chữ (B0001: nhãn phím, tên cổng CN9/CN8…; B0002 là bản vẽ kích thước) → luật an
  toàn nhưng lọc rất ít. Rủi ro: bỏ nhầm ảnh linh kiện/QR/khung đỏ không chữ; watermark và chữ rác OCR ("bobobbo",
  "日") làm ảnh trang trí bị tính có chữ; phải dùng OCR thô, không dùng `figure_labels` (chỉ giữ nhãn dạng mã).
- Đề xuất (chưa làm): giữ luật làm bộ lọc đầu, có ngoại lệ (chunk `wiring`/`dimension`/`pinout`, ảnh có khung đỏ, mã
  QR → ghi link ở manifest) và liệt kê ảnh bị bỏ để duyệt; ghi "không làm giàu bằng ảnh", không gán "trang trí".
- Mở tiếp: gán nhóm ảnh + quy tắc lấy gì theo nhóm → thử gpt-4.1-mini ~12 ảnh (2/nhóm) → quyết định hướng C (đổi C2 §8,
  schema) → chọn lại mẫu 2c; sửa bảng thuật ngữ (homing switch, soft limit, board, workpiece homing).

## 2026-11-13 · Thử vision với gpt-4.1-mini trên cùng 8 mẫu (so với gpt-4o-mini) · loại: thử nghiệm

- Cùng script, prompt, ảnh và 8 chunk như `vision-trial-1`; chỉ đổi model (env `TRIAL_MODEL`, giá 0,40/1,60 USD/1M).
  Kết quả: `data/ingest_runs/f54/vision-trial-2/`. Verdict mẫu 2c vẫn tạm giữ.
- Chi phí: 43.203 + 2.502 token ≈ **0,021 USD** (gpt-4o-mini: 0,062) — ảnh chỉ ~2–5k token; ước toàn F54 (208 ảnh)
  ≈ 0,37 USD. Thời gian 28 s (gpt-4o-mini 40 s). Mô tả dài hơn ~1,5 lần.
- Đối chiếu tay với ảnh gốc: 8/8 không bịa trong `figure_desc_vi`; chi tiết hơn gpt-4o-mini ở B0003 (cả cây menu con),
  B0050 (đọc được màu dây — gpt-4o-mini bỏ), B0074 (mô tả từng ảnh: RS485 CN4↔CN10 FG/D−/D+, LOW/HIGH INPUT, OUT0–OUT7
  mỗi cổng, 24V/0V), B0086 (AX5–8.ENA = 0), B0193 (M1950 ở 02024 cột +6, dải 0~255). Gọi "công tắc homing" thay vì
  "công tắc hành trình". Còn yếu: B0050 liệt kê màu dây theo thứ tự chứ không ghép từng chân; B0074 không nêu
  IN0=X300…/OUT0=Y300…; B0193 câu hỏi "M1950 nên đặt trong khoảng nào" suy từ dải 0~255 của màn hình; một số câu hỏi
  không trả lời được (B0003 "tạo và mở file", B0193 "kích hoạt workpiece homing"); từ khóa VI có tiếng Anh/mã
  (optocoupler, RS485, M1950).
- Kết luận đề xuất: gpt-4.1-mini tốt hơn và rẻ hơn ~3 lần cho phần ảnh. Không đổi contract/schema/code pipeline.

## 2026-11-13 · Thử nghiệm hướng C: làm giàu chunk hình bằng model vision (8 mẫu) · loại: thử nghiệm

- Bối cảnh: duyệt mẫu 2c (Claude đề xuất 17 ok / 13 fix, 2 lỗi nặng; Toma chọn tạm giữ verdict) cho thấy lỗi tập trung ở
  chunk hình: làm giàu chỉ nhận chữ của chunk (tiêu đề + caption), không nhận ảnh hay nhãn OCR → đoán (B0040 "trục
  chính", B0011 "cảm biến"). Toma yêu cầu thử gửi ảnh cho model vision với 8 mẫu.
- Cách làm: script ngoài pipeline (không sửa code, không ghi `eval-k`): system prompt v4 + thuật ngữ + phần thêm cho ảnh,
  trả thêm `figure_desc_vi`; gpt-4o-mini, `detail: high`, ảnh `original.png` của mọi asset. Mẫu: B0003, B0011, B0019,
  B0040, B0050, B0074, B0086, B0193 (12 ảnh). Kết quả và script: `data/ingest_runs/f54/vision-trial-1/`.
- Chi phí: 405.040 + 1.849 token ≈ **0,062 USD** cho 8 chunk (≈ 34k token/ảnh; gpt-4o-mini tính ảnh rất đắt). Ước
  toàn F54 (136 lá có ảnh, 208 ảnh): ≈ 1,1 USD, gấp ~19 lần làm giàu chữ (0,057 USD).
- Đối chiếu tay với ảnh gốc: `figure_desc_vi` **không bịa** ở 8/8; đúng chi tiết ở B0003 (9 menu), B0011 (X40–X47/CN6,
  X50–X57/CN7, 3K, 24V, CX.0–CX.3), B0019 (NPN COM 24V, PNP COM 0V, X40–X43 = trục X–A), B0040 (Alarm+/24V, X51–X54 =
  trục X–A — sửa được lỗi nặng của v4), B0086 (AX1–4.ENA = 1), B0193 (M1920–M1959, M1950 khung đỏ).
- Còn yếu: mô tả hời hợt khi nhiều ảnh/ảnh dày (B0050 bỏ màu dây; B0074 5 ảnh chỉ nêu cổng 0–3, bỏ IN0=X300…, CN4↔CN10
  D+/D−); B0193 hỏi "giá trị mặc định M1950" từ giá trị đang hiển thị (suy diễn); một số câu hỏi vẫn không trả lời được;
  thuật ngữ chưa sửa (homing switch → "công tắc hành trình", board → "bảng"); từ khóa VI chứa mã (M1950, X40).
- Không đổi contract/schema/code pipeline. Mở tiếp: Toma quyết định có đưa vision vào Bước 3 (trường riêng
  `figure_desc_vi` + duyệt riêng) và thử model rẻ ảnh hơn (gpt-4.1-mini) trước khi chạy toàn F54.

## 2026-11-13 · Bước 3: làm giàu toàn bộ F54 + cổng 2c (mẫu duyệt tay) (run `f54/eval-k`) · loại: thay đổi

- Toma sửa bảng thuật ngữ (`qs_controller.yaml`, 22 thuật ngữ; vd. tool setter → bộ so dao, homing → về home/về 0,
  backlash → bù rơ cơ khí; JOG, PLC giữ tiếng Anh) → phiên bản làm giàu `v4+g1cb3720f`.
- Làm giàu toàn bộ F54 (`cli enrich`, gpt-4o-mini): 199 nội dung, 0 lỗi, 244.804 + 23.869 token ≈ **0,051 USD**.
- **Lỗi thiết kế phát hiện qua CQ-13** (13 chunk "mã lạ G00"): làm giàu khóa theo `content_hash` nên thủ tục lặp nguyên
  văn ở 13 mục tham số (I-40c) dùng chung tóm tắt viết cho mục "JOG RAPID (G00)" — sai với 12 mục. Sửa: khóa =
  (`content_hash`, `section_path`) (`EnrichmentRecord.section_path`, `loader.enrichment_key`); bổ sung `section_path`
  cho 295 bản ghi cũ từ `chunks.jsonl` (290 duy nhất, 4 theo `chunk_key`, 1 không xác định → không dùng); làm giàu thêm
  24 chunk trùng nội dung ở mục khác (0,0061 USD). Tổng làm giàu F54 ≈ 0,057 USD; cả Bước 3 tới giờ ≈ 0,075 USD.
- Cổng 2c (C2 §10): `ChunkReviewEntry` thêm `enrichment_verdict/note/version/severe`; `enrich/review.py` (chọn mẫu,
  đếm verdict còn hiệu lực, `gate_2c`: 0 chờ, 0 lỗi nặng, ≥ 90% ok); `cli enrich-sample`, `cli enrich-approve` →
  `build/enrichment_approval.json` → `approved`; `chunk_quality.json.enrichment` thêm `auto_passed`, mẫu, `versions`;
  trang duyệt có mục cổng 2c và lọc `mau_2c`; chép verdict làm giàu khi `--carry-review`.
- Lệch kế hoạch: phê duyệt ghi file riêng `enrichment_approval.json` thay vì sửa `enrichment.jsonl` (giữ append-only).
- Kết quả `eval-k`: 243/243 lá làm giàu; tự động 2c **ĐẠT** (0 mã lạ, 1 bớt câu hỏi/từ khóa, 0 cắt content); mẫu 30
  chunk (1 chunk có cờ `glossary_term_missing`: B0161 Soft Limit + 29 phân tầng) chờ Toma duyệt.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 358 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1055 passed, 14 skipped. Test mới: trùng nội dung khác mục, cổng 2c.
- Ảnh hưởng contract/API/schema: C2 §10 (cổng 2c); schema review/enrichment như trên. Không ghi database.
- Mở tiếp: Toma duyệt 30 mẫu → `enrich-approve` → Bước 4.

## 2026-11-13 · Bước 3: prompt v3 → v4, thí điểm lại 19 chunk (run `f54/eval-k`) · loại: thay đổi

- Quyết định (Toma, phương án 2): sửa tiếp 2 lỗi còn lại của v2 trước khi chạy toàn bộ.
- v3: câu hỏi về tài liệu/hình bị bỏ khi còn ≥ 2 câu (`is_meta_question`), còn lại thì cờ `faq_meta`; thuật ngữ bảng
  ghi "giữ tiếng Anh" có trong content phải có nguyên văn trong làm giàu, thiếu → cờ `glossary_term_missing`; prompt
  thêm ví dụ câu hỏi cho đoạn chỉ có hình. Chạy 19 chunk (0,0050 USD): hết câu hỏi về hình, B0186 có "backlash", 0 cờ.
  **Lỗi do v3 gây ra:** B0001 (ảnh mặt trước/sau) có câu hỏi "Kích thước F54 bao nhiêu?" chép từ ví dụ trong prompt
  (không trả lời được từ đoạn); B0001 mất hết từ khóa VI vì bước dọn coi tên model `F54` là mã.
- v4 (sửa lỗi của v3): bỏ ví dụ cụ thể, thay bằng "hỏi điều chính hình cho biết theo tiêu đề/caption"; cấm "trong tài
  liệu", "trong phần này", "được trình bày"; `faq_meta` bắt thêm "phần này/mục này"; từ khóa VI được giữ tên model.
  Chạy 19 chunk (`v4+ga40bffb5`): 19/19, 0 lỗi, 0 cờ, 24.010 + 2.395 token ≈ **0,0050 USD**; sau build 0 mã lạ, 0 bớt,
  0 cắt content, lá lớn nhất 676 token. B0001 có từ khóa và câu hỏi đúng ảnh; hết "trong tài liệu". Còn sót nhẹ
  (để duyệt mẫu 2c): B0048 "được trình bày rõ ràng", B0022 câu hỏi tối nghĩa, vài từ khóa chung ("hướng dẫn sử dụng").
- `enrichment.jsonl` của `eval-k` giữ đủ v1…v4 cho 19 chunk (so sánh); build dùng bản mới nhất. Tổng chi phí thí điểm
  Bước 3 tới giờ ≈ 0,018 USD.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 356 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1053 passed, 14 skipped.
- Mở tiếp: Toma duyệt v4 → chạy phần còn lại (~224 nội dung, ≈ 0,06 USD) → duyệt mẫu 2c.

## 2026-11-13 · Bước 3: prompt v2 + bảng thuật ngữ, thí điểm lại 19 chunk (run `f54/eval-k`) · loại: thay đổi

- Quyết định (Toma): bảng thuật ngữ bổ sung dần trong quá trình cập nhật luồng (team kỹ thuật/khách hàng bận); bắt
  đầu bằng bản nháp, thuật ngữ chưa chắc giữ tiếng Anh.
- Code: `Profile.glossary` (`GlossaryTerm en/vi/note`), bản nháp 22 thuật ngữ trong `profiles/qs_controller.yaml`
  (16 có cách gọi VI; PLC, macro giữ tiếng Anh; tool setter, homing, backlash, offset chờ team xác nhận); prompt v2
  (`enrich/prompt.py`: không mở "Đoạn này…", không hỏi về tài liệu/hình, từ khóa VI không mã/tiếng Anh, chèn bảng
  thuật ngữ); `prompt_version` = `v2+g<dấu bảng>` → sửa bảng là `enrich` làm lại; `--only-enriched`; `clean_output` bỏ
  từ khóa VI chứa mã; cờ kiểm `summary_preamble`. Test `test_enrich.py` +3.
- Run `f54/eval-k` (chép `normalized/`, `figure_ocr.jsonl`, `enrichment.jsonl` từ `eval-j`, build venv chính, carry
  296/296): chunk không đổi. `enrich --only-enriched` (prompt `v2+ga40bffb5`): 19/19 ghi, 0 lỗi, 0 cờ; thật 21.084 +
  2.304 token ≈ **0,0045 USD**; sau build: 0 mã lạ, 0 bớt, 0 cắt content, lá lớn nhất 633 token.
- So v1 ↔ v2 (cùng 19 chunk; file `enrichment.jsonl` giữ cả hai phiên bản): hết "Đoạn này" (19/19); thuật ngữ áp đúng
  ("tool setter", "rơ-le trung gian", "chạy tay (JOG)", "tưới nguội"); hết mã trong từ khóa VI; câu hỏi về tài liệu/hình
  giảm, còn 2 (B0001 "Hình ảnh… tìm ở đâu?", B0002 "Có hình vẽ nào…?"); B0186 dịch backlash thành "bù trục" và mất từ
  "backlash" dù bảng ghi giữ tiếng Anh; vài từ khóa chung ("điều khiển CNC", "hướng dẫn sử dụng").
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 355 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1052 passed, 14 skipped.
- Ảnh hưởng contract/API/schema: C2 §8 (bảng thuật ngữ, phiên bản làm giàu); profile thêm `glossary`. Không ghi
  database.
- Mở tiếp: Toma duyệt v2 → chạy phần còn lại (~224 nội dung, ≈ 0,06 USD) → duyệt mẫu 2c; bổ sung thuật ngữ dần.

## 2026-11-13 · Duyệt gộp ghi chú vào chunk hình (B0006, B0060) — mốc so sánh cho Bước 4 · loại: quyết định

- Duyệt: Toma, `ok` cho 2 chunk gộp theo R-13 (I-45) của `f54/eval-j`; reviewer `toma+claude`. F54 `eval-j`: 296 ok /
  0 fix / 0 chờ, **cổng 2b đạt (tạm)**.
- Ghi để so lại khi kiểm tra cứu (Bước 4) — trước (`f54/eval-i`) / sau (`f54/eval-j`):

  | Mục | Trước | Sau |
  |---|---|---|
  | 2.2 Controller power supply | cha B0007 (97 token) = con B0008 figure (Figure 6, 67 token) + con B0009 overview ("Note:" 2 dòng, 83 token) | B0006 standalone figure (97 token): Figure 6 + Note |
  | 2.4.1 Y40 output signal (S-ON) | cha B0063 (272 token) = con B0064 wiring (Figure 46, 47; 253 token) + con B0065 overview ("Note: Ter.(5,9,13,14)…", 96 token) | B0060 standalone wiring (272 token): sơ đồ + Note |

- Giả thuyết cần đo: chunk gộp khớp tốt hơn câu hỏi về ghi chú (vd. "nguồn xung hay biến áp cho F54?", "chân FG dùng
  làm gì?", "Ter.5,9,13,14 là gì?") vì ghi chú nằm cùng ngữ cảnh hình; rủi ro: vector của chunk hình loãng hơn. Bước 4
  thêm các câu hỏi này vào bộ đánh giá; nếu kém hơn thì nới/tắt R-13 (`figure_text_max` hoặc bỏ gộp).
- Phần 6 trong câu hỏi trước của Toma: không có (ghi dư).

## 2026-11-13 · Loại chunk theo manifest, bỏ ảnh khung chữ, giới hạn nhãn OCR, gộp ghi chú vào hình (run `f54/eval-j`) · loại: thay đổi

- Vấn đề (Toma đánh giá chunk thử trên `eval-i`): chưa có cách loại chunk vô ích (B0000: bìa + lời cảm ơn, trang
  1–2); 22 ảnh khung "Instructions" (`text_frame`) vẫn là asset dù chữ đã ở `content`; nhãn OCR ảnh tổng quan (B0002:
  34 mã chân) vào từ khóa; hình + ghi chú ngắn bị tách vụn (B0007 → B0008 67 + B0009 83 token).
- Quyết định (duyệt: Toma, chọn từng mục): (1) manifest `exclude_pages`/`exclude_sections`/`exclude_reason`, lý do độ
  phủ `manifest_excluded`; F54 loại trang 1–2; (2) hình `text_frame` không là asset, không làm khối thành chunk hình
  (I-44); T-20 nhận khung có tiêu đề khung mà chỉ còn caption bước (F54 trang 153 từng bị sót); (3) nhãn OCR chỉ vào
  từ khóa của chunk `wiring`/`pinout`/`dimension` (`chunking.figure_label_keyword_types`); (4) ghi chú ngắn ngay sau
  chunk hình cùng mục gộp vào chunk hình khi tổng ≤ 600 ký tự (C2 R-13, I-45).
- Lệch kế hoạch: luật gộp ghi đánh số R-13 (kế hoạch ghi R-14; R-13 chưa dùng vì phương án tách cửa sổ cha của I-43
  bị bỏ). Ngoài 2.2, mục 2.4.1 cũng được gộp.
- File: `schemas/{manifest,profile}.py`, `manifests/f54.yaml`, `build/{chunker,fields,builder}.py`,
  `normalize/figures.py`; test `test_chunker.py` (+3, sửa 1), `test_text_frames.py` (+1); C1 T-20; C2 §3, §7, §8.1,
  R-13; [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.16;
  [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md) (I-44, I-45).
- Kiểm chứng: `f54/eval-j` (chuẩn hóa lại từ raw `eval-i` vì T-20 đổi, build venv chính, carry từ `eval-i`, chép
  `figure_ocr.jsonl` + `enrichment.jsonl`): 296 chunk (cha 53, con 150, độc lập 93; trước 301); chỉ 3 mục đổi nội
  dung (B0000 loại — 9 phần tử `manifest_excluded`; 2.2 → 1 chunk hình; 2.4.1 → 1 chunk wiring); asset lá 234 → 208
  (23 khung chữ + 3 ảnh bìa); 74 lá chỉ đổi từ khóa; CQ-01…CQ-12, độ phủ 1,0, ranh giới P/R 1,0; review 294 ok /
  2 pending; làm giàu 19/243 lá còn khớp (bản ghi B0000 không còn dùng). Hồi quy `eval-j-regress`: F86 Installation,
  Operation 0 chunk/asset đổi; 1 và 5 chunk đổi từ khóa (bỏ nhãn OCR trên chunk không phải wiring/pinout/dimension).
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 352 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1049 passed, 14 skipped.
- Ảnh hưởng contract/API/schema: C1 T-20; C2 §3 (manifest), §7, §8.1, R-13; `DocManifest` thêm 3 trường; profile thêm
  `figure_label_keyword_types`. Trả ảnh kèm câu trả lời (vd. bản vẽ kích thước B0003) còn phụ thuộc website-qa (chưa
  có SSE ảnh) và bước xuất bản (upload asset). Không ghi database.
- Mở tiếp: Toma duyệt 2 chunk mới (B0006, B0060); câu hỏi phần 6 của Toma bị cắt; prompt v2 + thuật ngữ.

## 2026-11-13 · Bước 3: code làm giàu tiếng Việt + thí điểm 20 chunk (run `f54/eval-i`) · loại: thay đổi

- Quyết định (Toma, theo kế hoạch Bước 3): chạy với cổng 2b đạt **tạm** (nhãn `verified: false`); model
  `gpt-4o-mini` (truyền `--model`, vì env `OPENAI_MODEL` của dịch vụ chat là `gpt-4.1-mini`); thí điểm 20 chunk phân
  tầng trước khi chạy hết.
- Code: module `enrich/` (`checks`, `prompt` v1, `client` OpenAI structured output, `runner`, `env`); lệnh
  `cli enrich` (`--sample`, `--limit`, `--dry-run`, `--model`, giá); `build` đọc `build/enrichment.jsonl` theo
  `content_hash`, ghép tóm tắt/câu hỏi/từ khóa VI vào `embed_text` chunk lá, `enrichment_status = draft`, không bao
  giờ cắt `content` vì làm giàu (bớt câu hỏi → từ khóa → tóm tắt, cờ `enrich_trimmed`); kiểm 2c (CQ-13) trong
  `chunk_quality.json.enrichment`; trang duyệt hiện tóm tắt/câu hỏi. Schema: `EnrichmentOutput`, `EnrichmentRecord`,
  `EnrichmentSummary`.
- Lệch kế hoạch: (1) `doc_ingest` không được import `app.core.config` (`test_import_boundary.py`) → key/model đọc từ
  env, rơi về `backend/.env` qua `python-dotenv` (có sẵn); giá gpt-4o-mini là hằng số, model khác phải truyền giá.
  (2) Bảng bước của `pipeline.py` dành tên module `enrich` cho trích fact → đổi bước fact sang module `facts`, thêm
  bước "Làm giàu tiếng Việt". (3) Luật mã lạ ban đầu bắt nhầm tên model `F54` (6/20) → so với `content` + model +
  section path; đã tính lại `checks` của 20 bản ghi (không gọi lại API).
- Run `f54/eval-i` (chép `normalized/` từ `eval-h`, build venv chính, carry 301/301): chunk không đổi so với `eval-h`.
  Dry-run toàn bộ: **221** nội dung khác nhau cần làm giàu (246 lá; 25 lá trùng nội dung với lá khác), ước tính
  177K + 55K token ≈ 0,060 USD.
- Thí điểm (`--sample 20`, 8 loại chunk): 20/20 ghi, 0 lỗi; thật 15.223 + 2.294 token ≈ **0,0037 USD**; sau build: 0 mã
  lạ, 0 bớt, 0 cắt content; token lá tăng ~+150–210 (lớn nhất B0182 480 → 667 ≤ 800). Cổng 2c: 20/246 (chưa đạt —
  đúng, chưa chạy hết).
- Nhận xét chất lượng thí điểm (chờ Toma duyệt): tiếng Việt tự nhiên, giữ nguyên mã (`M1920`, `#14006`, `Y44`); nhưng
  (a) hầu hết tóm tắt mở bằng "Đoạn này …" (thừa); (b) vài câu hỏi hỏi về tài liệu/hình, không trả lời được từ nội
  dung (B0002, B0003, B0029 "Mô hình nào…"); (c) từ khóa VI có lẫn mã/tiếng Anh ("tham số M1920", "dimension",
  "MPG"); (d) thuật ngữ dịch chưa theo cách gọi ở VN ("bộ định vị công cụ" cho tool setter, "bù trừ độ trễ" cho
  backlash) → đề xuất prompt v2 + bảng thuật ngữ.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 348 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1045 passed, 14 skipped. Test mới `test_enrich.py` (client giả).
- Ảnh hưởng contract/API/schema: C2 §3 (lệnh), §8 (làm giàu), §10 (cổng 2c, chạy với cổng tạm). Không ghi database.
- Mở tiếp: Toma duyệt thí điểm → prompt v2 (+ thuật ngữ) → chạy lại 20 thí điểm → chạy 201 còn lại.

## 2026-11-13 · Làm rõ D-008: Bước 3 và embed chỉ cho chunk lá · loại: quyết định

- Câu hỏi (Toma): theo D-008 thì chunk cha không được tìm; vậy làm giàu tiếng Việt (Bước 3) và embed có chỉ làm
  cho chunk con và độc lập không? Trả lời: đúng (duyệt: Toma).
- Căn cứ, kiểm trên `f54/eval-h` (chỉ đọc): 55 cha, 154 con, 92 độc lập; `content` con nằm trong cha 154/154;
  `content` cha = nối nguyên văn các con 55/55 (2–5 con mỗi cha); 0 phần tử chỉ có ở cha; tập chunk lá (246) phủ
  toàn bộ nội dung. 5 phần tử nằm ở > 1 chunk lá đều là segment bảng trang 167–171 (một segment trang chứa dòng của
  2–3 phần bảng); mỗi dòng bảng vẫn đúng một phần.
- Tra cứu: con khớp → `Retriever._expand_parents` trả `content` của cha (nhiều con cùng cha → một kết quả); độc lập
  khớp → trả chính nó. Cha chỉ cần `content`, không cần embedding, tóm tắt, câu hỏi.
- Hệ quả: phạm vi Bước 3 và embed của F54 = **246 chunk lá** (không phải 301). Chunk cha: `summary_vi`/`faq_vi`
  trống, `enrichment_status = none`.
- File: contract C2 §8 (bỏ "chunk cha cùng mẫu, tóm tắt cho cả cửa sổ"; "mọi chunk" → "mọi chunk lá"). Không
  đổi code; không sửa dòng D-008 trong `decisions.md` (đã nói cha không được embed để khớp).

## 2026-11-13 · I-43: chỉ chunk lá chịu ngân sách embed; quyết định D-008 (run `f54/eval-h`) · loại: thay đổi

- Vấn đề: đo lại `eval-g` thì 3 chunk vượt ngân sách 650 token (800 − 150 dự trữ Bước 3) đều là **chunk cha**
  (B0036 800 đã `embed_truncated`, B0115 712, B0020 690; `embed_text` của cha gộp mọi con + tới 40 từ khóa); mọi
  chunk lá ≤ 584 token, F86 0 chunk vượt. Mô tả I-43 ban đầu ("chunk không phải bảng") sai.
- Làm rõ (với Toma): 800 là ngưỡng tự đặt ở C2 §8 (model nhận 8.191 token), 650 chỉ để tránh luật cắt của ta;
  kích thước tối ưu cho điểm khớp chưa đo (Bước 4). Tra cứu hiện tại tìm cả cha; cha + con cùng khớp gom một nhóm
  ngữ cảnh nhưng chiếm 2 trong 6 suất top-k (S-03).
- Quyết định (duyệt: Toma; liên luồng → [decisions.md](../../decisions.md) D-008): chỉ tìm trên chunk con/độc lập,
  cha chỉ mở rộng ngữ cảnh. Bỏ phương án tách cửa sổ cha theo token (kế hoạch đầu, bị từ chối).
- Thay đổi: cha không gắn `embed_truncated`; chunk lá vượt ngân sách → cờ `embed_over_budget`; CQ-12 mới (phần
  bảng nhiều dòng vượt → không đạt, lá khác → ghi chú, cha không tính). Không tách cửa sổ, không đổi `content`.
- File: `build/{fields,assertions,quality}.py`; test `test_chunk_quality.py` (+1, mở rộng 1); C2 §5, §8, §10
  (CQ-12), S-03, R-11; [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.16;
  [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md) (I-43); website-qa
  STATE/LOG (việc mở D-008).
- Kiểm chứng: `f54/eval-h` (chép `normalized/` từ `eval-g`, build venv chính, carry từ `eval-g`): 301 chunk, 0
  nội dung đổi, chỉ cha B0036 bỏ cờ `embed_truncated`; 0 lá vượt ngân sách; CQ-01…CQ-12, CQ-RB đạt, độ phủ 1,0,
  ranh giới P/R 1,0; **301 ok / 0 fix / 0 chờ, cổng 2b đạt (tạm)**. Hồi quy `eval-h-regress`: F86 Installation,
  F86 Operation 0 đổi.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 342 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1039 passed, 14 skipped.
- Ảnh hưởng contract/API/schema: C2 như trên; thêm cờ `embed_over_budget`, CQ-12. Phía tra cứu (cột `chunk_role`,
  lọc trong `match_doc_chunks`) chưa làm — cùng bước xuất bản (E-01, BL-22). Không ghi database.
- Mở tiếp: team xác nhận nhãn (`verified: true`); Bước 3 (báo chi phí LLM trước); I-41; I-40 (c), (d).

## 2026-11-12 · Duyệt 7 chunk của `f54/eval-g` — F54 đạt cổng 2b (tạm) · loại: đánh giá

- Duyệt: Toma xác nhận 7 verdict đề xuất; reviewer `toma+claude`.
- `ok` cho 6 chunk mới sau I-40a/I-42: B0069 (cha 2.4.3), B0070 (2.4.3: Figure 50, 51, 52 đúng thứ tự), B0072
  (2.4.4: chỉ Figure 53, 54), B0245 (cha 4.4.3), B0246 (thủ tục 4 điểm + sơ đồ trang 129), B0247 (thủ tục 3 điểm +
  sơ đồ trang 130).
- B0045 `fix` → `ok`: nội dung không đổi, từ khóa OCR rác đã được lọc (I-40b).
- Build lại `eval-g` bằng venv chính (cùng code, chunk không đổi): 301 chunk (cha 55, con 154, độc lập 92),
  **301 ok / 0 fix / 0 chờ**; CQ-01…CQ-11, CQ-RB đạt, độ phủ 1,0, ranh giới P/R 1,0 → **cổng 2b ĐẠT (tạm)**: tạm vì
  nhãn mẫu và nhãn ranh giới còn `verified: false`.
- Tổng kết chuỗi sửa trên F54 (2026-11-11 → 12): `eval-c` 342 chunk, 42 `fix` → `eval-d` (I-37) → `eval-e` (I-38)
  → `eval-f` (I-39) → `eval-g` (I-40a, I-40b, I-42), 0 `fix`.
- Ảnh hưởng contract/API/schema: không. Không đổi code. Không ghi database.
- Mở tiếp: I-43 (P2, nên sửa trước Bước 3); team xác nhận nhãn (`verified: true`); quyết định sang Bước 3 (báo chi
  phí LLM trước); I-41, I-40 (c), (d).

## 2026-11-12 · Sửa I-40a, I-40b, I-42: hình lạc mục, nhãn OCR rác, hai thủ tục dính (run `f54/eval-g`) · loại: thay đổi

- Trước đó: ghi 3 verdict `ok` cho chunk I-39 của `eval-f` (B0115, B0117, B0118; duyệt: Toma qua kế hoạch) →
  `eval-f` 297 ok / 4 fix.
- Vấn đề (4 `fix` còn lại, đều là nội dung thật cần chunk): B0072 mang Figure 52 của mục 2.4.3 (Docling xếp hình đầu
  trang 44 xuống cuối trang); B0045 có từ khóa OCR rác (`DR4-`, `FUL2-`, `PL14+`, `QFF54`…, điểm OCR tới 0,99);
  B0246/B0247 mục 4.4.3 hai thủ tục dính, câu dẫn và sơ đồ lệch thủ tục.
- Quyết định/luật (duyệt: Toma), áp cho mọi tài liệu:
  - T-07 (C1): hình cấp trên nằm hẳn trên heading đánh số đầu trang nhưng xếp sau → dời lên trước, thuộc mục trước,
    cờ `reading_order_fixed`; chỉ trang text layer, cùng cột với heading;
  - R-02 (C2): bước đánh số lại từ 1 → thủ tục mới; câu dẫn ngắn (≤ `procedure_lead_max` 160) và sơ đồ cùng trang
    đi theo thủ tục mới; khối tiêu đề + hình + câu dẫn ngắn ngay trước chuỗi bước gộp vào thủ tục;
  - C2 §8.1: nhãn OCR crop vào từ khóa khi có trong từ vựng text layer của tài liệu hoặc khớp
    `figure_label_trusted_patterns` (qs_controller: PUL/DIR/EDM, X/Y, A/B/Z±, AI/AO, G/M-code, GND/PE/FG, điện áp);
    khác → `figure_labels[].verified = false`. Toma chọn phương án này thay vì chỉ từ vựng (loại 186 nhãn, gồm chân
    đúng `PUL1+`, `DIR1+`, `GND`) hoặc không lọc.
- Lệch kế hoạch: tham số mẫu tin cậy đặt ở cấp profile (`figure_label_trusted_patterns`), không ở `chunking`, vì
  `chunking` của profile con thay nguyên khối của default.
- File: `normalize/sections.py`, `pipeline.py`, `build/{chunker,fields}.py`, `schemas/{profile,chunk}.py`,
  `profiles/{default,qs_controller}.yaml`; test `test_sections.py` (+4), `test_chunker.py` (+2); C1 T-07, cờ; C2
  R-02, §8.1; [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.16;
  [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md) (I-40a/b, I-42 xử lý).
- Kiểm chứng: `f54/eval-g` (chuẩn hóa lại từ raw `eval-f` bằng `.venv-ingest`, build bằng venv chính, carry từ
  `eval-f`): 301 chunk; F54 chỉ 1 hình bị dời (Figure 52 → 2.4.3, sau Figure 51, trước "Note:"); chỉ 2.4.3, 2.4.4,
  4.4.3 đổi nội dung; 4.4.3 → 2 thủ tục (218, 226 token), mỗi thủ tục có câu dẫn, sơ đồ, Step 1–2; nhãn OCR crop
  1.325 giữ / 175 loại; 45 chunk chỉ đổi từ khóa (verdict giữ theo `content_hash`); CQ-01…CQ-11, độ phủ 1,0,
  ranh giới P/R 1,0, BL-34 đạt. Review: 294 ok / 1 fix (B0045, nội dung không đổi) / 6 pending. Hồi quy
  `eval-g-regress`: F86 Installation, F86 Operation 0 chunk đổi, 0 hình dời, 0 từ khóa đổi (không có OCR crop).
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 341 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1038 passed, 14 skipped.
- Ảnh hưởng contract/API/schema: C1 T-07; C2 R-02, §8.1; `FigureLabel.verified` (mặc định `true`, có trong
  `figure_labels` của export `doc_chunks_v1`); profile thêm `procedure_lead_max`, `figure_label_require_vocab`,
  `figure_label_trusted_patterns`. Không ghi database.
- Mở tiếp: duyệt 6 chunk `pending` + đổi B0045 sang `ok`; I-40 (c), (d); I-41; I-43.

## 2026-11-12 · Sửa I-39: chia khối dài theo "Case/Example" (run `f54/eval-f`) · loại: thay đổi

- Vấn đề: khối "How to calculate the electronic gear ratio" (F54 mục 2.6.4.7) vượt 2.500 ký tự nên bị chia
  theo từng phần tử: B0116 (774 token) chứa Case 1, Case 2 và nửa đầu Case 3; kết luận của Case 3 tách sang
  B0117. Bullet là glyph ``.
- Quyết định/luật (duyệt: Toma, theo kế hoạch; C2 R-12 mới), áp cho mọi tài liệu:
  - khối dài có đầu phần (`chunking.block_part_patterns`: Case/Example/Ví dụ/Trường hợp + số) chỉ chia ở đầu
    phần; hình ngay trước đầu phần đi theo phần đó; mỗi phần ≤ 2.500 ký tự và ≤ 650 token `embed_text`;
  - phần 2…n lặp tiêu đề `(phần i/n)` + phần dẫn chung ≤ `block_lead_max` (300 ký tự; ở đây: công thức), vì
    retriever (`_expand_parents`) không kéo chunk láng giềng nên mỗi phần phải tự đủ nghĩa;
  - một phần quá dài → chia theo phần tử trong phần đó, không trộn với phần khác, cờ `block_part_oversize`;
  - glyph vùng Private Use đầu dòng render thành `- ` (`text` của phần tử không đổi).
- Lệch kế hoạch: bỏ ý "`label_heading` giữa khối cũng là đầu phần" vì "Formula:" là `label_heading` và sẽ tách
  công thức khỏi tiêu đề; chỉ dùng mẫu. Thêm: phần của khối bị tách không gộp lại ở bước gộp overview.
- File: `build/{chunker,render}.py`, `schemas/profile.py`, `profiles/default.yaml`; test `test_chunker.py` (+4);
  C2 §6, §6.1, R-11, R-12; [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.16;
  [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md) (I-39 xử lý, I-43 mới).
- Kiểm chứng: `f54/eval-f` (chép raw/normalized từ `eval-e`, build bằng venv chính, carry từ `eval-e`) → 301
  chunk (cha 55, con 154, độc lập 92); chỉ mục 2.6.4.7 đổi: 2 phần (Case 1–2: 551 token; Case 3 + kết luận:
  410 token, lặp công thức); phần 1 cùng ghi chú đầu mục thành cửa sổ cha mới (712 token); CQ-01…CQ-11, độ phủ
  1,0, ranh giới P/R 1,0, BL-34 đạt. Review: 294 ok / 4 fix / 3 pending. Hồi quy `eval-f-regress`: F86
  Installation, F86 Operation 0 chunk đổi.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 335 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1032 passed, 14 skipped.
- Ảnh hưởng contract/API/schema: C2 như trên; `Chunking` thêm `block_part_patterns`, `block_lead_max`. Không
  đổi chuẩn hóa, không đổi retriever, không ghi database.
- Mở tiếp: duyệt 3 chunk `pending` của `eval-f`; I-42, I-40, I-41; I-43 (chunk không phải bảng > 650 token).

## 2026-11-12 · Duyệt 9 phần bảng `pending` của `f54/eval-e` (cổng 2b) · loại: đánh giá

- Duyệt: Toma xác nhận đề xuất (qua duyệt kế hoạch); reviewer `toma+claude`.
- B0291–B0299 (bảng 5.1, 5.2, 5.3 sau I-38): cả 9 `ok`. Căn cứ: kiểm tự động mỗi dòng đúng một
  lần, tiêu đề `(phần i/n)` và header lặp ở mọi phần, không phần nào `embed_truncated`; nội dung
  dòng giống các chunk bảng đã đọc ở `eval-d`.
- Build lại `eval-e` bằng venv chính (cùng code, chunk không đổi): 300 chunk, **294 ok / 6 fix /
  0 pending**, 0 stale; CQ, độ phủ 1,0, ranh giới P/R 1,0 đạt. Cổng 2b không đạt chỉ vì 6 `fix`
  (I-39, I-40, I-42); kết quả đánh dấu tạm vì nhãn mẫu `verified: false`.
- Ảnh hưởng contract/API/schema: không. Không đổi code.
- Mở tiếp: I-39 (P1) → lập kế hoạch sửa trước khi đụng code.

## 2026-11-11 · Sửa I-38: chia phần bảng theo token của `embed_text` (run `f54/eval-e`) · loại: thay đổi

- Vấn đề: bảng chia theo ký tự (≤ 2.500) nhưng `embed_text` giới hạn theo token (≤ 800). Bảng
  5.1, 5.2 của F54 có `embed_text` 1.069–1.291 token, chỉ 12–18 dòng đầu vào embedding; phần
  3/3 của 5.1 chỉ có 1 dòng.
- Quyết định/luật (duyệt: Toma, theo bản kế hoạch), áp dụng cho mọi bảng của mọi tài liệu:
  - phần bảng phải thỏa cả ≤ `parent_max` ký tự và `embed_text` ≤ `embed_max_tokens` −
    `embed_enrich_reserve` (tham số mới, 150 token, chừa chỗ cho tóm tắt và câu hỏi của Bước 3);
  - chỉ chia ở ranh giới dòng; chi phí một dòng = token của dòng + token mã của nó trong "Từ
    khóa:"; chi phí được cân giữa các phần;
  - dòng nhóm (một ô có chữ, không mang mã) đi cùng dòng sau nó và được lặp ở phần sau;
  - CQ-11: chunk bảng nhiều dòng có `embed_truncated` làm cổng không đạt.
- File: `build/{chunker,fields,builder,assertions,quality}.py`, `cli.py`, `schemas/profile.py`,
  `profiles/default.yaml`; test `test_chunker.py` (+4), `test_chunk_quality.py`,
  `chunk_helpers.py`; contract C2 §6, §10, §14 (R-05);
  [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.15, §6.16.
- Kiểm chứng: `f54/eval-e` (chuẩn hóa lại từ raw của `eval-d`, build bằng venv chính) → 300
  chunk (cha 54, con 152, độc lập 94); chỉ 3 mục PART 5 đổi; 5.1 → 5 phần 13–15 dòng (545–569
  token), 5.2 → 2 phần (584, 561 token), 5.3 → 2 phần (367, 356 token); mỗi dòng đúng một lần;
  0 `embed_truncated`; CQ-01…CQ-11, CQ-RB đạt, độ phủ 1,0, ranh giới P/R 1,0, BL-34 đạt. Chép
  291/300 verdict (285 ok, 6 fix), 9 `pending` (B0291–B0299, `table_part`).
- Lệch kế hoạch: 5.1 ra 5 phần thay vì ước tính ~6 (sau khi bỏ đếm trùng mã I/O trong chi phí
  dòng); bảng cổng F86 Installation cũng chia lại (đã báo trong kế hoạch). Không gắn cờ mới cho
  khối tiêu đề + hình của I-37 (đã báo ở mục I-37).
- Duyệt 9 phần bảng: đề xuất cả 9 `ok` (kiểm tự động: mỗi dòng đúng một lần, header và tiêu đề
  `(phần i/n)` lặp ở mọi phần, không phần nào bị cắt); **chờ Toma xác nhận**, chưa ghi
  `chunk_review.json`.
- Hồi quy (`eval-d-regress`): F86 Installation 21 → 23 chunk (bảng cổng 2.1: 3 → 6 phần,
  392–529 token), CQ và ranh giới đạt; F86 Operation 0 chunk đổi.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 331
  passed; `.\venv\Scripts\python.exe -m pytest tests` → 1000 passed, 14 skipped.
- Đính chính các mục 2026-11-11 bên dưới: lần build lại `eval-c` và build `eval-d`,
  `eval-c-regress` trong ngày chạy bằng `.venv-ingest` (không có tiktoken) nên `token_count`
  trống và không chunk nào được gắn `embed_truncated`; câu "CQ đạt" ở đó đo bằng ước lượng ký
  tự/4. Đã build lại bằng venv chính: `eval-c` 342 chunk, 300/42/0, 3 chunk `embed_truncated`;
  `eval-d` 296 chunk, 286/10/0, 3 chunk `embed_truncated`. Nội dung chunk, `content_hash` và
  verdict không đổi. Trong lúc sửa, `eval-c` từng bị build nhầm bằng chunker mới (302 chunk), đã
  khôi phục bằng code trước khi sửa I-37 (lấy từ git index).
- Phòng lặp lại: `build` in cảnh báo và đánh dấu kết quả là tạm khi không có tiktoken. Không
  build lại run cũ bằng code mới; kết quả mới luôn vào run id mới.
- Ảnh hưởng contract/API/schema: có, C2 như trên; `Chunking` thêm `embed_enrich_reserve`; cổng 2b
  thêm CQ-11. Không đổi chuẩn hóa. Không ghi database.
- Mở tiếp: duyệt 9 phần bảng `pending` của `eval-e`; I-39, I-40, I-41, I-42. Ước lượng chi phí
  dòng còn dư cho bảng cổng F86 (phần thực tế ≤ 529 token trên ngân sách 650).

## 2026-11-11 · Duyệt tay 66 chunk `pending` của `f54/eval-d` (cổng 2b) · loại: đánh giá

- Vấn đề: sau khi sửa I-37, `f54/eval-d` có 66 chunk đổi nội dung (36 mục) ở trạng thái `pending`.
- Kiểm chứng: đọc từng mục, đối chiếu chunk cũ của `eval-c` với chunk mới (theo `content_hash` +
  `section_path`). Người duyệt `toma+claude` → 64 `ok`, 2 `fix`.
- `fix`: B0245, B0246 (mục 4.4.3, I-42). Cha B0244 ghi `ok` (nội dung cha đủ).
- Ghi chú kèm `ok`: bìa gộp vào lời giới thiệu, mang `ocr_required` (B0000); "Kiểu phát xung
  A/B" gộp vào chunk hình đứng trước (B0114); dòng "Model: F54, F86, Astro 6A, Astro 10i" không
  còn trong `content` (B0260, B0265); bảy mục giới thiệu màn hình có danh sách chức năng loại
  `figure` (I-35); số mục in sai và `section_path` ở gốc (I-40d, I-41).
- Build lại `eval-d`: 296 chunk, CQ đạt, độ phủ 1,0, ranh giới P/R 1,0; duyệt tay 286 ok /
  10 fix / 0 chờ / 0 stale → cổng "Duyệt tay" **không đạt** (10 `fix` mở: I-38 4, I-39 2,
  I-40 2, I-42 2).
- Ảnh hưởng contract/API/schema: không. Không đổi code.
- Mở tiếp: I-38…I-42.

## 2026-11-11 · Sửa I-37: nhãn khung, mục lục lọt, khối tiêu đề + hình (run `f54/eval-d`) · loại: thay đổi

- Vấn đề: 34 trong 42 chunk `fix` của `f54/eval-c` thuộc I-37: chunk hình chỉ có tiêu đề mục
  (21), chỉ có "Model: F54 controller" (8), chỉ có "Instructions / Model: F54" (1), và
  B0000/B0001/B0003/B0004 (bìa, dòng mục lục, "1.1 Overview / Specification:").
- Quyết định/luật (duyệt: Toma, theo bản kế hoạch):
  - T-20 mở rộng: nhãn khung Docling không gom vào picture thành chữ của hình, cờ
    `frame_label_attached`: tiêu đề khung + dòng model liền sau; dòng model ngay trên picture
    hoặc bảng 0 cell. Profile thêm `frame_model_patterns`.
  - T-16 mở rộng: dòng có chấm dẫn ("." hoặc "…") + số trang, và tiêu đề mục lục
    (`toc_title_patterns`) ngay trước mục lục → `toc`, không là heading của T-07.
  - R-04: heading + một dòng dẫn kết thúc ":" (≤ `table_lead_max` 80) trước bảng thành dòng dẫn
    của bảng; khối tiêu đề + hình không caption gộp vào khối sau cùng mục (hết khối thì vào
    khối trước; trước bảng hoặc là nội dung duy nhất của mục thì giữ là chunk hình).
  - R-02: khối thủ tục không nhãn nối với chuỗi khối bước sau; label heading dạng bước được
    đếm là một bước khi phân loại (một phần I-35, duyệt bổ sung trong lúc làm).
- File: `normalize/{figures,coverage,sections,elements}.py`, `pipeline.py`, `build/chunker.py`,
  `schemas/profile.py`, `profiles/default.yaml`; test `test_text_frames.py`, `test_coverage.py`,
  `test_chunker.py` (+9); contract C1 (T-16, T-20, cờ), C2 §14 (R-02, R-04);
  [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.7, §6.15, §6.16.
- Kiểm chứng: `f54/eval-d` chuẩn hóa lại từ raw của `eval-c` → 296 chunk (cha 54, con 152, độc
  lập 90); 36 mục đổi; 34/34 chunk `fix` của I-37 không còn; CQ-01…CQ-10, CQ-RB đạt, độ phủ
  1,0, ranh giới P/R 1,0, BL-34 đạt. Chép 230/296 verdict (222 ok, 8 fix), 66 `pending`.
- Hồi quy (run `eval-c-regress`, không render ảnh): F86 Installation 26 → 21 chunk (bìa sạch,
  chunk mục lục `toc_like` biến mất, mục 2.5 và 2.6 gộp sơ đồ với NOTE), CQ, độ phủ, ranh giới,
  BL-34 đạt; F86 Operation 0 chunk đổi; F10T chỉ "CONTENT" → `toc`.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 327
  passed; `.\venv\Scripts\python.exe -m pytest tests` → 996 passed, 14 skipped.
- Lệch kế hoạch: không gắn cờ `assets_attached_to_neighbor` cho khối tiêu đề + hình (tiêu đề đã
  nằm trong `content`). F86 Installation có đổi (kế hoạch kỳ vọng 0), đã liệt kê ở trên.
- Ảnh hưởng contract/API/schema: có, C1 và C2 như trên; `Profile` thêm 2 trường, `Chunking`
  thêm 1 trường. Luồng tra cứu không đổi. Không ghi database.
- Mở tiếp: I-42 (mục 4.4.3 hai thủ tục dính nhau, phát sinh từ thay đổi này; giữ nguyên theo
  quyết định duyệt); duyệt 66 chunk `pending` của `eval-d`; I-38…I-41.

## 2026-11-11 · Duyệt tay 36 chunk `pending` của `f54/eval-c` (cổng 2b) · loại: đánh giá

- Vấn đề: sau T-20, `f54/eval-c` còn 36 chunk `pending` (13 mục đổi nội dung so với `eval-b`).
- Kiểm chứng: đọc nội dung từng chunk, đối chiếu với ghi chú của `eval-b` (danh sách Step và
  phần tử bị loại do I-36). Mọi Step bị mất trước đây đã có mặt, câu bị cắt đã đủ (vd. 3.4
  Step 3; 4.3.3 Step 1–4; 3.3.4 Step 1–5; 4.10.1 và 4.11.2 Step 1–8). Không mở lại PDF gốc.
- Kết quả (người duyệt `toma+claude`): 30 `ok`, 6 `fix`. `fix`: B0247, B0250, B0254, B0285,
  B0317, B0321, đều là chunk hình chỉ có tiêu đề mục (I-37). Ghi chú kèm `ok`: nhãn khung
  "Instructions / Model: F54" còn sót, có chỗ chen giữa thủ tục (B0316, B0327; I-37, không
  chặn); thủ tục ngắn chia ở Step 3 (B0308/B0309, B0328/B0329); B0286 sai `chunk_type` (I-35).
- Build lại `eval-c` với `--labels tests\doc_ingest\fixtures\eval\f54.chunks.json`: 342 chunk,
  CQ đạt, độ phủ 1,0, ranh giới P/R 1,0; duyệt tay 300 ok / 42 fix / 0 chờ / 0 stale → cổng
  "Duyệt tay" **không đạt** (42 `fix` mở).
- Phát hiện mới: I-41 (P2). Số mục in sai 3.3.x làm lệch `section_path`: 3.3.4, 3.3.5, 3.9.2 và
  cả `4.3.6 Copy and Paste` (số đúng) thành mục gốc, mất `PART 4 > 4.3`. Thêm vào
  [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md).
- Ghi chú: verdict chép từ `eval-b` giữ nguyên ghi chú cũ; vài mục `fix` (vd. B0229) còn ghi lý
  do I-28 dù nay là chunk hình chỉ có tiêu đề (I-37). Verdict vẫn đúng, không sửa ghi chú.
- Ảnh hưởng contract/API/schema: không. Không đổi code.
- Mở tiếp: sửa I-37 (nhóm `fix` lớn nhất), rồi I-38…I-41.

## 2026-11-11 · Tách nhật ký chunking sang cấu trúc theo luồng (D-002) · loại: thay đổi

- Vấn đề: `chunking_flow_log.md` gộp trạng thái, lịch sử, quyết định và backlog nên tự
  mâu thuẫn: tiêu đề ghi cập nhật 11-09 trong khi mục 1 có nội dung 11-10, 11-11; mục 7 ghi
  "0 ok / 323 chờ" còn mục 1 ghi "270 ok / 53 fix"; I-36 và T-20 thiếu ở mục 5, 6; mục 4
  không có mục ngày 11-10, 11-11.
- Quyết định/luật: tách thành `README.md` (mục 2, 3 cũ + phần thiết kế từ
  `architecture.md`), `STATE.md` (mục 1, 8 cũ), `LOG.md`; mục 4–8 cũ chép nguyên văn vào
  `LOG-archive-2026-11-09.md` (duyệt: Toma, D-002 trong [decisions.md](../../decisions.md)).
- File: `docs/ai/flows/doc-ingest/*`; `docs/ai/chunking_builder/chunking_flow_log.md` còn
  là con trỏ; `architecture.md` và `current-state.md` rút phần `doc_ingest` còn tóm tắt.
- Kiểm chứng: số trong STATE đọc lại từ `data/ingest_runs/*/build/chunk_review.json` và
  `chunk_quality.json` → khớp các mục 11-10, 11-11 bên dưới. Từ `backend/`:
  `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 318 passed.
- Ảnh hưởng contract/API/schema: không. Không đổi code.

## 2026-11-11 · T-20 khung chữ và `build --carry-review` (sửa I-36 trên trang text layer) · loại: thay đổi

- Vấn đề: I-36 (P0). Trên trang text layer của F54, Docling nhận khung cột "Instructions"
  là picture, nên 39 đoạn hướng dẫn trên 23 trang thành `figure_text` và các chunk thủ
  tục thiếu Step.
- Quyết định/luật: luật chuẩn hóa mới T-20 "khung chữ", chạy trước T-17. Picture thực chất
  là khung hướng dẫn (nhãn Step hoặc câu văn, phần lớn dòng nhiều từ, không phải tiêu đề
  khung) trả chữ về text thân theo thứ tự đọc, cờ `frame_text_released`; picture gắn cờ
  `text_frame`; tiêu đề khung ("Instructions", "Model: F54") giữ là `figure_text`. Chỉ áp
  dụng cho trang text layer; trang OCR không đổi (I-28 còn mở).
- Quyết định/luật: `build --carry-review <chunk_review.json> --carry-chunks <chunks.jsonl>`
  chép verdict của lần build trước theo `content_hash` + `section_path`; chunk mới, đổi nội
  dung hoặc đổi mục thành `pending`.
- File: `normalize/figures.py`, `build/builder.py`, `cli.py`; test
  `tests/doc_ingest/test_text_frames.py`; contract C1 (thứ tự T-20 → T-17, cờ mới) và C2
  (lệnh `--carry-review`); [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.16.
- Kiểm chứng: run mới `f54/eval-c`, chuẩn hóa lại từ raw của `eval-b`, không ghi đè
  `eval-b` → 342 chunk (cha 70, con 197, độc lập 75); đúng 13 mục đổi so với `eval-b`, mọi
  mục có đủ Step; CQ-01…CQ-10 và CQ-RB đạt, độ phủ 1,0, ranh giới P/R 1,0; BL-34 đạt;
  `figure_text` bị loại trừ 518 → 449. Chép 306/342 verdict (270 ok, 36 fix), 36 `pending`.
  F86 Installation, F86 Operation, F10T: 0 khung.
- Ảnh hưởng contract/API/schema: có, C1 (luật T-20, cờ `text_frame`, `frame_text_released`)
  và C2 (tùy chọn CLI). Luồng tra cứu không đổi.
- Mở tiếp: duyệt 36 chunk `pending` của `eval-c`; I-37 (chunk hình chỉ có tiêu đề mục, nhãn
  khung còn lại ở trang Docling không gom khung), I-38, I-39, I-40.

## 2026-11-10 · Duyệt tay cổng 2b trên F54 (run `f54/eval-b`) · loại: đánh giá

- Vấn đề: cổng 2b cần verdict của người duyệt cho từng chunk; trước đó toàn bộ `pending`.
- Kiểm chứng: `chunk_review.json` của `f54/eval-b`, người duyệt `toma+claude` → 270 ok /
  53 fix / 0 chờ trên 323 chunk. Build lại `eval-b`: cổng "Duyệt tay" **không đạt** (53 fix
  mở), 0 stale.
- Nhóm `fix`, theo nhật ký cũ:
  - mất Step do khung "Instructions" bị nhận là picture: I-36 (P0), 18 chunk;
  - chunk gần rỗng và ảnh tách khỏi hướng dẫn: I-37, 27 chunk;
  - bảng tham số vượt 800 token: I-38, 4 chunk;
  - `block_split` cắt giữa ví dụ: I-39, 2 chunk;
  - Figure 52 sai mục và từ khóa OCR rác: I-40, 2 chunk.
- Ghi chú trong `chunk_review.json` được viết trước khi có ID I-36…I-40 và dùng nhãn I-28
  (18 chunk), I-33 (13 chunk); không sửa lại file đó.
- Lỗi của PDF gốc (số mục 3.9.x, chữ tiếng Việt, `M1951`/`M1950`) ghi `ok` kèm ghi chú.
- Ảnh hưởng contract/API/schema: không.
- Mở tiếp: I-36…I-40 (thêm vào
  [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md));
  F86 Installation chưa duyệt.
