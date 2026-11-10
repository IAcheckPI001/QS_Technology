# Nhật ký luồng chunking (`doc_ingest`)

Cập nhật: 2026-11-09 (lần cuối: chunk builder BL-16 + kiểm chất lượng 2b, sau khi chạy `figure-ocr`).

File này tổng hợp kiến trúc, trạng thái và lịch sử thay đổi của luồng nạp tài liệu kỹ
thuật (PDF → chunk). Đây là điểm vào, không phải tài liệu chuẩn. Khi có khác biệt, tài liệu
chuẩn thắng:

- Luật và schema: [p1_normalization_contract.md](../reports/p1_normalization_contract.md)
- Vấn đề đã ghi nhận (I-xx): [p1_chunking_impact_assessment.md](../reports/p1_chunking_impact_assessment.md)
- Golden test: [p1_golden_tests.md](../reports/p1_golden_tests.md)
- Backlog (BL-xx): [p1_implementation_backlog.md](../reports/p1_implementation_backlog.md)
- Trạng thái toàn dự án: [current-state.md](../current-state.md), kiến trúc: [architecture.md](../architecture.md)

## 1. Tóm tắt trạng thái (2026-11-09)

- Pipeline chạy từ PDF tới hết **lớp chuẩn hóa**: S0 → Docling → S1 (T-xx) → V-01 →
  `normalized/elements.jsonl`.
- **Có chunk nháp từ 2026-11-09** (BL-16, bước `build`): chạy trên thư mục chạy có sẵn, sinh
  `build/chunks.jsonl` + kiểm chất lượng 2b + trang duyệt `report/chunks.html`. **Chưa ghi DB**, chưa có
  phần tiếng Việt (Bước 3), chờ team duyệt cổng 2b. Trích fact, gán unit, CLI review và xuất bản chưa có.
  Bảng `doc_chunks` trong DB vẫn chứa chunk F86 biên soạn tay (`chunking_loader/load_csv.py`).
- Đầu ra hiện tại hợp lệ theo schema (mọi dòng của 6 file đầu ra đều validate).
- Các lỗi P0/P1 phát hiện trên F54 (171 trang) và F86 (trang 1–17) đã xử lý (mục 5).
- T-08 list cha–con có từ 2026-11-09 (phiên bản 1, mới kiểm trên F54).
- T-12/T-13 chạy cả trên text từ 2026-11-09 (mã parameter + vị trí + vai trò).
- Hàng review còn 3 mục chặn sinh chunk và 20 mục chặn trích fact trên F54 (mục 7).
- Đánh giá đa tài liệu có từ 2026-11-09 (BL-34): F54, F86 Installation đạt cổng (tạm, nhãn chưa xác nhận); F10T, F86 Operation không đạt (chủ yếu OCR). Ba vấn đề mới I-28…I-30 trên F10T chưa sửa.
- Contract chunk C2 duyệt 2026-11-09 (sửa §1, §2, thêm §13, §14): [p2_chunk_contract.md](../reports/p2_chunk_contract.md).
- **Trạng thái kiểm duyệt chunk (2026-11-09):** kiểm tự động đạt trên F54 và F86 Installation (CQ-01…CQ-10,
  CQ-RB, độ phủ 1,0, ranh giới P/R 1,0 trên nhãn nháp). **Chưa có duyệt của team**: nhãn ranh giới `verified: false`,
  `chunk_review.json` 0 ok / 0 fix (toàn bộ `pending`) → cổng 2b "chưa đủ dữ liệu", chưa sang Bước 3.
- Vấn đề mới từ chunk builder (2026-11-09, chưa sửa): I-31…I-35; **I-32 là P0** cho bảng cổng F86 Installation.

## 2. Kiến trúc luồng

```text
PDF
 │
 ├─ S0  đo trang (pypdfium2): text layer, ký tự lỗi, bitmap, path, xoay, page label
 │      → quyết định OCR theo trang (ocr_required)                      raw/profile.json
 ├─ Parse  Docling theo từng trang (OCR RapidOCR khi S0 yêu cầu)         raw/p{n}.docling.json
 ├─ Đo PDF  từ của text layer (V-01), bitmap + hash + nét vector (hình)  raw/p{n}.words.json
 │                                                                        raw/p{n}.objects.json
 └─ S1  chuẩn hóa deterministic (một Recorder: review_queue + normalization_log)
      T-17 xác nhận header/footer  (+ T-18 nhãn sát hình)
      T-16 phân loại nhãn Docling, mục lục
      T-06 số trang in
      T-07 section path
      Hình: T-09 screenshot → T-10 watermark → T-19 hình trùng → T-11 caption → T-14 crop
      Bảng: T-01…T-05, T-15 (+ T-12/T-13 trên ô bảng)
      T-08 list cha–con (v1)
      T-12/T-13 trên text, T-08 v1.1 (mã cha–con)
      V-01 độ phủ text
      → NormalizedElement                                               normalized/*.jsonl
      → ảnh crop (khi có PDF)                                           normalized/images/
      → độ khớp profile (B1)                                            run_report.json profile_fit
      → báo cáo HTML                                                    report/index.html
      → [lệnh eval] chấm theo nhãn mẫu (B3, B4)                         report/eval.json, eval.html
      → [figure-ocr, tùy chọn] OCR nhãn trong hình trang text layer     build/figure_ocr.jsonl
      → build: manifest + chunker + CQ-01…CQ-10 + kiểm 2b (BL-15/16)    build/chunks.jsonl, doc_chunks_v1.jsonl,
                                                                        chunk_quality.json, report/chunks.html
 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  chưa có  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
      làm giàu tiếng Việt (Bước 3) → đánh giá tra cứu offline (Bước 4) → trích fact (BL-17)
      → gán unit + duyệt (BL-18…BL-21) → gói xuất bản → doc_chunks (BL-22, BL-90…)
```

Bước hình chạy **trước** bước bảng: screenshot (T-09) không thành bảng rỗng, và caption
gắn lại (T-11) đổi điều kiện đóng bảng của T-03.

**Module** (`backend/app/modules/doc_ingest/`):

| Vùng | File | Vai trò |
|---|---|---|
| CLI, điều phối | `cli.py`, `pipeline.py` | `run`: PDF hoặc raw đã lưu → thư mục chạy; thứ tự bước, ghi file, trạng thái bước |
| Đo PDF | `parse/profile_probe.py`, `parse/pdf_probe.py`, `s0.py` | S0; `page_objects` (bitmap + px + hash, nét vector; form XObject lấy bounds của form) |
| Docling | `parse/docling_runner.py` | parse theo trang, render trang và ảnh crop |
| Chuẩn hóa | `normalize/docling_reader.py`, `pages.py`, `coverage.py`, `sections.py`, `figures.py`, `tables.py`, `lists.py`, `elements.py`, `recorder.py` | T-xx, ghép `NormalizedElement` |
| Mã kỹ thuật | `technical_refs/params.py`, `applicability.py`, `normalize/text_refs.py` | T-12, T-13 trên ô bảng và text |
| Kiểm | `validate/coverage.py` | V-01 |
| Đánh giá | `eval/profile_fit.py`, `eval/labels.py`, `eval/score.py`, `eval/render.py` | độ khớp profile, chấm theo nhãn mẫu |
| Duyệt | `review/approval.py` | lõi trạng thái unit, approval theo hash (chưa có gán unit, CLI) |
| Manifest (2026-11-09) | `manifest.py`, `manifests/*.yaml`, `schemas/manifest.py` | thông tin cấp tài liệu cho chunk: doc_id, loại, model, scope, bucket |
| Chunk builder (2026-11-09) | `build/loader.py`, `chunker.py`, `render.py`, `fields.py`, `assertions.py`, `quality.py`, `builder.py` | chia đơn vị, cửa sổ cha–con, gán trường, CQ-01…CQ-10, kiểm 2b |
| Xuất (2026-11-09) | `export/doc_chunks_v1.py` | `DraftChunk` → dòng bảng `doc_chunks` hiện tại (chỉ ghi file) |
| OCR nhãn hình (2026-11-09) | `parse/figure_ocr.py` | RapidOCR torch trên ảnh crop trang có text layer → `build/figure_ocr.jsonl` |
| Báo cáo | `report/html_report.py`, `report/chunks_report.py` | HTML tự chứa, từng bước, mục Hình, mục Chunk; trang duyệt chunk |
| Cấu hình | `profile.py`, `profiles/*.yaml`, `schemas/` | profile `default`, `qs_controller`; schema Pydantic `extra="forbid"` |

**Ranh giới:**
- Tool offline. `doc_ingest` không import chatbot và ngược lại (có test ranh giới); không
  nằm trong image chat service.
- Hai venv:
  - `.venv-ingest`: có Docling, pypdfium2; dùng để parse, đo PDF, render.
  - `backend/venv`: chạy lại chuẩn hóa từ raw đã lưu, `build` (có tiktoken để đếm token) và test.
- Không ghi DB.

## 3. Trạng thái từng bước (2026-11-09)

| Bước | Luật | Trạng thái | Backlog |
|---|---|---|---|
| S0 hồ sơ tài liệu + OCR theo trang | — | có | BL-24 |
| Parse Docling | — | có | — |
| Header/footer, nhãn sát hình | T-17, T-18 | có | BL-07, BL-10 |
| Phân loại nhãn, mục lục | T-16 | có | BL-33 |
| Bảng logic | T-01…T-05, T-15 | có | BL-05, BL-06, BL-27 |
| Mã parameter, điều kiện áp dụng | T-12, T-13 | có (ô bảng + text) | BL-11 |
| Trang in | T-06 | có (chưa có ghi đè manifest) | BL-07 |
| Section path | T-07 | có | BL-08 |
| List cha–con | T-08 | có (v1, kiểm trên F54) | BL-09 |
| Hình: screenshot, watermark, hình trùng, caption, crop | T-09, T-10, T-19, T-11, T-14 | có (chưa render trang xoay) | BL-10 |
| Kiểm bất biến | V-01…V-04 | một phần: chỉ V-01 | BL-25 |
| Đánh giá đa tài liệu | — | có code; nhãn mẫu chờ team xác nhận | BL-34 |
| Chunk builder + kiểm 2b | C2 | có code; chờ team duyệt cổng 2b | BL-15, BL-16 |
| Trích fact | — | chưa có | BL-17 |
| Duyệt theo unit | — | một phần: lõi approval; chưa gán unit, chưa CLI | BL-18…BL-21 |
| Xuất bản → `doc_chunks` | — | chưa có | BL-22, BL-90… |

## 4. Nhật ký cập nhật

### 2026-11-03

**S0 + OCR theo trang (BL-24)**
- Vấn đề: F86 Operation Manual không có text layer (I-20).
- Thay đổi: S0 đo từng trang; trang thiếu hoặc hỏng text layer được OCR và gắn `ocr_required` (chặn chunk).
- Kết quả: F86 trang 1–17 OCR đủ 17/17.

**T-17, T-06, T-07 + `NormalizedElement` (BL-07, BL-08, sửa I-21)**
- Header/footer:
  - chuỗi lặp ≥ 3 trang ở dải trên/dưới, dòng ghép từ các chuỗi đó, hoặc `furniture_patterns` → furniture;
  - heading đánh số xuất hiện một lần → trả về body;
  - chữ OCR trong hình → `figure_text`.
- Trang in: lấy từ /PageLabels hoặc dãy số ở footer, không suy từ offset.
- Section path: theo số đánh.
- Đầu ra mới: `normalized/elements.jsonl`. Thêm fixture `f86_ocr` (F86 trang 5–17).

**Hình (BL-10)**
- Ghi thêm `raw/p{n}.objects.json`.
- Luật mới:

  | Luật | Việc |
  |---|---|
  | T-18 | Nhãn sát hình (`320 mm`) → chữ của hình |
  | T-14 | Crop = bbox + bitmap + nét vector + nhãn của hình; render ảnh |
  | T-09 | Bảng 0 ô phủ bitmap → screenshot |
  | T-10 | Đánh dấu ứng viên watermark |
  | T-11 | Gắn lại caption |

- Sửa lỗi đo bitmap trong Form XObject.

### 2026-11-08

**Chạy F54 đủ 171 trang** (run `f54/20261103-144432`): mọi file đầu ra validate. Phát hiện ba lỗi:
- I-24 (P0): T-10 nhận nhầm screenshot là watermark.
- I-25: T-18 gắn nhầm nhãn mục vào hình.
- I-26: `PART 1:CONTROLLER OVERVIEW` không thành heading.

**Sửa I-24, I-25, I-26**
- `objects.json` thêm `hash` nội dung ảnh.
- T-10: watermark = cùng nội dung và cùng vị trí. Ảnh cùng nội dung ở vị trí khác chỉ có cờ `repeated_image`.
- T-18: bỏ qua dòng bắt đầu ở lề trái văn bản.
- T-07: chấp nhận tiêu đề dính sau `:`.
- T-11: khi hai ứng viên hòa, giữ liên kết Docling.

**Sửa I-27 bằng luật mới T-19**
- Vấn đề: Docling sinh cả picture lẫn bảng 0 ô cho cùng một ảnh.
- Thay đổi: hai hình cùng trang có IoU ≥ 0,9 được coi là một ảnh. Giữ phần tử có caption, nếu không có thì giữ screenshot. Phần tử còn lại gắn `duplicate_image` + `duplicate_of`, không crop, không xóa.

### 2026-11-09

**Chạy lại F54 đủ 171 trang từ PDF** (run `f54/20261109-063902`, profile `qs_controller`, không dùng raw đã lưu):
- Mục đích: xác nhận luồng chạy lại được từ đầu sau các sửa I-24…I-27.
- Kết quả: số liệu khớp mục 7 của bản 2026-11-08 (run `fix-i27`, dùng raw đã lưu) ở mọi chỉ số đã đối chiếu: phần tử, bảng, hình, V-01, review, trang in, header/footer, ảnh crop.
- Thời gian: S0 0,6 s; Docling 826 s; chuẩn hóa 0,2 s; render ảnh 41,5 s.
- Không đối chiếu được hash bảng với `fix-i27` vì thư mục run đó không còn; hash của run mới được ghi ở mục 7 làm mốc cho các lần sau.
- Không đổi code, contract hay test.

**T-08 list cha–con, phiên bản 1 (BL-09, sửa I-07)**
- Vấn đề: Docling trả list phẳng. Ở F54, mục con `o M1920 = 0 : Normally closed sensor (NC)` mất chủ thể
  (`M1920: … X axis`), nên builder có thể tách cha khỏi con và bước trích fact không ghép được mã với giá trị.
- Khảo sát: 482 list_item; lề x 103 (cấp 1), x 139 (103 mục `o `), x 121/113 (list cấp 1 thụt khác);
  `marker` Docling không đáng tin (`-` cho 292 mục).
- Luật v1 (đã duyệt, ghi rõ chỉ kiểm trên một tài liệu):
  - lề trái là tín hiệu chính, glyph chỉ có tác dụng khi thụt 3–18 pt và phải có khoảng trắng theo sau;
  - mọi phần tử body không phải list ngắt khối list;
  - list đầu trang nối khối list cuối trang trước (`list_cross_page`);
  - không chắc → review: `list_orphan`, `list_level_ambiguous` (mã mới), chặn fact, không chặn chunk;
  - anh em khác marker → cờ `list_marker_mixed`.
- Rủi ro tài liệu lộn xộn (glyph dùng sai, thụt lề không đều) đã xét: glyph không bao giờ tạo con khi không thụt
  sâu hơn; lề không khớp cấp nào → review thay vì gán im lặng.
- File: `normalize/lists.py` (mới), `schemas/normalized.py` (`ListInfo`, mã review), `normalize/docling_reader.py`
  (`marker`), `normalize/recorder.py`, `normalize/elements.py`, `schemas/profile.py` + `profiles/default.yaml`
  (`list_indent_min`), `schemas/run.py` + `pipeline.py` (`RunReport.lists`, bước `s1_lists`),
  `report/html_report.py` (mục List); test `tests/doc_ingest/test_lists.py` (17 test).
- Kết quả F54 171 trang (run `bl09-t08`): 103 con, 0 mồ côi, 2 nối qua trang (trang 67), 3 `list_level_ambiguous`
  (trang 71: dòng công thức Docling gắn list_item, bullet Wingdings `\uf0f0`); review 21 → 24; mọi chỉ số khác không
  đổi. F86 trang 5–17 không đổi.

**T-12/T-13 trên text + T-08 v1.1 (BL-11 phần text)**
- Vấn đề: mã parameter trong text (định nghĩa `M1920: …`, giá trị `o M1920 = 0`, nhắc trong câu) chưa được
  nhận; builder và trích fact không biết mã nào ở đâu.
- Quyết định đã duyệt: lưu mã + vị trí + vai trò (`TextParamRef`); thêm review `list_param_mismatch`.
- Luật:
  - chỉ quét prefix khai báo trong `param_text_patterns` của profile (`qs_controller`: `#` 4–5 chữ số,
    `M` đúng 4 chữ số); `default` không quét;
  - gộp đơn/dải/danh sách theo ngữ pháp contract §4; dải ngược, trộn dải với danh sách → `param_unparseable`;
  - token đúng prefix nhưng sai số chữ số → near-miss, chỉ báo cáo;
  - T-13 chạy cả trên text;
  - T-08 v1.1: cha định nghĩa mã khác mã của con → `list_param_mismatch` (chặn fact).
- File: `technical_refs/params.py` (`TextParamRef`, `find_param_refs`), `normalize/text_refs.py` (mới),
  `schemas/normalized.py`, `schemas/profile.py`, `profiles/*.yaml`, `normalize/recorder.py`,
  `normalize/elements.py`, `pipeline.py` (`RunReport.refs`, bước `s1_refs` implemented), `schemas/run.py`,
  `report/html_report.py` (mục "Mã parameter"); test `test_text_refs.py` (22 test).
- Kết quả F54 171 trang (run `bl11-text`): 227 ref ở 220 phần tử (98 định nghĩa, 75 giá trị, 54 nhắc tới),
  phủ 302/302 token mã; 0 unparseable; near-miss 9 (`M100` ×4, `M8` ×2, `M100H` ×2, `M195` ×1);
  `list_param_mismatch` 2 ở trang 96; review 24 → 26; mọi chỉ số khác không đổi. F86 không đổi.
- Hai lỗi soạn thảo của chính tài liệu F54 được phát hiện: trang 96 cha `M1951` nhưng con `M1950 = 0/1`;
  trang 94 `configure parameter M195..` (thiếu chữ số).

**Đánh giá đa tài liệu (BL-34)**
- Người dùng chạy thêm F86 Installation (26 trang, 92 s) và F10T (105 trang, 101 trang OCR, Docling 1.394 s).
- B1 — độ khớp profile (`eval/profile_fit.py`, `RunReport.profile_fit`, mục HTML "Độ khớp profile"): mã đã nhận, near-miss,
  dạng mã lạ, tỷ lệ trang OCR, picture lớn chứa câu văn, chữ tiếng Việt trên trang OCR. Sáu tín hiệu cảnh báo, không tự đổi
  profile. Đã siết hai tín hiệu để không báo nhầm trên F54 (chỉ đếm chữ Việt trên trang OCR; picture phải chứa câu văn).
- B2 — nhãn nháp 4 tài liệu (`tests/doc_ingest/fixtures/eval/*.labels.json`), soạn từ text layer PDF gốc và ảnh trang,
  **không** lấy từ output pipeline; `verified: false`.
- B3/B4 — lệnh `eval` (precision/recall tách trang text layer / OCR) và cổng. Trong lúc chạy, cổng ban đầu chấm F10T "đạt" chỉ
  dựa trên 1 trang text layer; đã thêm điều kiện "tỷ lệ trang OCR ≤ 50%".
- Kết quả (run `eval-b`, tạm):

  | Tài liệu | Tín hiệu B1 | Cổng | Ghi chú |
  |---|---|---|---|
  | F54 (13 trang mẫu) | `unknown_code_shapes` (G-code `G00`, `G54`) | đạt | T-12 67/0/0, vai trò 1,0, list 26/0/0, T-13 4/4, nội dung 3/3 |
  | F86 Installation (4 trang) | không | đạt | 0 mã bịa (chân Z3-, CN11 không bị nhận), nội dung 4/4 |
  | F86 Operation (2 trang) | `ocr_majority` | không đạt | toàn bộ OCR; nội dung 3/3 |
  | F10T (4 trang) | `unknown_code_shapes`, `near_miss_high`, `ocr_majority`, `picture_swallows_text`, `ocr_lang_mismatch` | không đạt | T-12 OCR precision 0,5 (M0100 ×3), nội dung thân 0/4 |

- Vấn đề mới (chưa sửa, cần quyết định):
  - **I-28 (P0)**: F10T bố cục hai cột trong khung; Docling nhận cả khung trang là picture → hướng dẫn thành `figure_text`.
  - **I-29 (P0)**: OCR tiếng Anh trên tài liệu tiếng Việt → mất dấu; `0` đọc thành `o`.
  - **I-30 (P1)**: `M0100.txt` (tên macro) bị nhận là parameter.
- File: `eval/` (mới), `schemas/run.py` (`ProfileFit`), `pipeline.py`, `report/html_report.py`, `cli.py` (lệnh `eval`);
  test `test_eval.py` (9 test), `test_run_report.py`.

**Chunk builder (BL-16) + kiểm chunk (BL-15), Bước 2 và 2b của kế hoạch nối RAG**
- Contract C2 duyệt với góp ý: bảng `doc_chunks` hiện tại chỉ là mốc → `DraftChunk` độc lập với bảng + adapter
  `export/doc_chunks_v1.py`; thêm §13 (khoảng trống schema S-01…S-07, đo ở Bước 4) và §14 (quy tắc làm rõ khi triển khai).
- Giai đoạn 2 `build` đọc thư mục chạy có sẵn + manifest (`manifests/f54.yaml`, `f86_installation.yaml`,
  `f86_operation.yaml`); `run` gọi `build` ở cuối khi có manifest.
- Luật chính: đơn vị = khối label heading; chuỗi "Stage n:" gộp thành một thủ tục; nhóm parameter kèm giá trị; bảng
  theo nhóm dòng lặp header; hình = caption/tiêu đề + ảnh; cửa sổ cha nối nguyên văn các con ≤ 2.500 ký tự.
- Kiểm 2b: CQ-01…CQ-10 + CQ-RB, độ phủ phần tử, ranh giới theo nhãn nháp (`fixtures/eval/{doc}.chunks.json`, file
  riêng để không đổi kết quả BL-34), so với 27 chunk F86 viết tay, tổng hợp `chunk_review.json`, cổng.
- Lệnh `figure-ocr`: RapidOCR (backend torch, có sẵn trong `.venv-ingest`) trên ảnh crop hình ở trang có text layer;
  nhãn chỉ vào `figure_labels`/`keywords`.
- Lỗi phát hiện và sửa trong lúc chạy: review cấp trang (`ocr_required`, `text_coverage_gap`) chưa gắn vào chunk;
  đoạn lặp nguyên văn ở mục khác làm bộ chấm ranh giới ghép nhầm; CQ-06 coi bảng `pinout` là chunk hình; YAML đọc
  `2024-04-25` thành ngày; mã lỗi E-02 bị trùng → đổi thành E-05.
- Kết quả (nhãn **tạm**):

  | Tài liệu | Chunk (cha/con/độc lập) | CQ | Độ phủ | Ranh giới P / R / đúng loại | Chunk có review chặn |
  |---|---|---|---|---|---|
  | F54 (`f54/eval-b`) | 323 (62/178/83) | đạt | 1,0 | 1,0 / 1,0 / 0,9 (10 đơn vị) | 2 (`ocr_required` bìa, `caption_ambiguous`) |
  | F86 Installation (`f86_italliation/eval-b`) | 26 (2/4/20) | đạt | 1,0 | 1,0 / 1,0 / 0,71 (7 đơn vị) | 7 |
  | F86 Operation (`f86/eval-b`, nháp) | 16 (0/0/16) | đạt | 1,0 | — | 16 (`ocr_required`) |

- `figure-ocr` (chạy 2026-11-09, ~4–13 s/hình trên CPU): F54 232 hình, F86 Installation 21 hình. Sau khi chạy lại
  `build`: nhãn `crop_ocr` có ở 102/144 chunk lá có ảnh (F54) và 15/17 (F86), vd. `CN3`, `CN10`, `DIR4-` (F54 1.1),
  `X67`, `Z6-` (F86 2.1). Nhãn chỉ ở `keywords`/`figure_labels`; CQ và ranh giới không đổi.
- So với chunk F86 viết tay: 7/27 chunk tay có ≥ 60% token nằm trong một chunk builder. Khác biệt chính: chunk tay chia
  theo từng cổng và có mô tả hình do người viết; builder chia bảng cổng theo nhóm dòng và chunk hình chỉ có tiêu đề.
- Vấn đề mới (chưa sửa): I-31 (F86 trang mục lục không được nhận), I-32 (bảng cổng F86 lệch ô mô tả giữa các dòng,
  P0 cho bảng cổng), I-33 (chunk hình không caption chỉ có tiêu đề), I-34 (độ hạt bảng cổng), I-35 (luật loại chunk thô).
- File: `build/`, `export/`, `manifest.py`, `manifests/`, `schemas/chunk.py`, `schemas/manifest.py`,
  `schemas/profile.py` (`Chunking`, `Vocabulary.spec_attributes`), `profiles/default.yaml` (`chunking`),
  `profiles/registry_snapshot.json` (+ `spec_attributes`), `report/chunks_report.py`, `report/html_report.py` (mục Chunk),
  `parse/figure_ocr.py`, `eval/labels.py` (`ChunkLabels`), `cli.py` (`build`, `figure-ocr`, `--no-build`), `schemas/run.py`
  (`chunks`); test `test_chunker.py` (12), `test_chunk_quality.py` (8), `chunk_helpers.py`, cập nhật `test_run_report.py`,
  `test_profile_isolation.py` (thêm `build`, `export`), `tests/chatbot/test_registry_snapshot.py`; `.gitignore`
  (ngoại lệ cho `doc_ingest/build/`).
- Kiểm duyệt: kiểm tự động đạt (mục 7); nhãn ranh giới và nội dung chunk **chưa được team duyệt**.

## 5. Lỗi đã khắc phục

| ID | Vấn đề | Nguyên nhân | Cách sửa | Bằng chứng sau sửa |
|---|---|---|---|---|
| I-08 | F54 trang 18: screenshot Figure 15 ra bảng 0×0 | Docling | T-09 | `screenshot` có caption, không còn `empty_table` |
| — | Bitmap trang 18 bị ghi ở góc (0,720) | pdfium trả tọa độ cục bộ của Form XObject | `page_objects` lấy bounds của form cấp trang | (141,492)–(500,695); test `test_f54_fixture.py` |
| I-09 | Watermark trang 171 nhận là picture | Docling | T-10 (phủ picture ≥ 90%) | `watermark_candidate`, không xóa |
| I-10 | F54 trang 11: "Figure 5" gắn vào bảng | Docling | T-11 | caption chuyển sang hình, cờ `caption_relinked` |
| I-11 | F54 trang 9: crop theo bbox Docling mất "4 - M4" | bbox hẹp hơn bitmap ~35 pt | T-14 hợp bbox + bitmap + vector + nhãn | ảnh crop có đủ 212/220/140/90/25 và "4 - M4" |
| I-21 | F86: 5 heading bị gắn `page_header` → mất khỏi nội dung | Docling trên trang OCR | T-17 | 5/5 heading trả về body, section path đúng |
| I-23 (một phần) | Chữ OCR trên sơ đồ 60–90 mảnh/trang, heading rác, `PAGEO` | OCR | `figure_text`; T-06 không nội suy | chữ trong hình không vào text thân; `PAGEO` → trang in `null` |
| — | F86 trang 8, 9: nhãn `320 mm` nằm ngoài picture | Docling không gắn parent | T-18 | `figure_text` của đúng hình; ảnh crop chứa nhãn |
| I-24 (P0) | F54: 7/15 `watermark_candidate`, 7/8 `watermark_conflict` là screenshot thật | T-10 so theo kích thước; F54 dùng một khung 480×272 px cho mọi ảnh giao diện | T-10 theo hash nội dung + cùng vị trí; ảnh lặp khác vị trí → `repeated_image` | 8 `watermark_candidate`, đều là watermark thật; `watermark_conflict` 8 → 1 |
| I-25 | F54 trang 80 `INDEX homing type` (và 7 dòng `Model: F54 controller`) bị gắn vào hình | T-18 không phân biệt nhãn mục ở lề trái | Bỏ qua dòng bắt đầu ở lề trái văn bản (± 3 pt) | 8 dòng trở lại `label_heading`; F86 vẫn gắn 7 nhãn hình |
| I-26 | `PART 1:CONTROLLER OVERVIEW` không thành heading | Mẫu từ khóa bắt buộc khoảng trắng sau `:` | Cho phép tiêu đề dính sau `:`/`.` nếu bắt đầu bằng chữ cái | 1.1–1.3 nằm dưới PART 1; `section_parent_missing` 16 → 13 |
| — | 4 `caption_ambiguous` mới sau khi sửa I-24 | Picture và screenshot trùng vùng hòa nhau | T-11 giữ liên kết Docling khi hòa | `caption_ambiguous` về 1 (trang 38, ca thật) |
| I-27 | F54 trang 64, 81, 85, 96, 98: một ảnh có hai phần tử hình | Docling sinh picture + bảng 0 ô (IoU 1,0) | T-19 | mỗi trang một ảnh; ảnh render 247 → 242 |
| I-07 (P0) | F54 trang 19: list con `o M1920 = 0` không biết thuộc cha nào | Docling trả list phẳng, cha và con cùng `level` | T-08 v1 | GT-07 đạt (4 cha × 2 con); toàn F54 103 con, 0 mồ côi; `o #4142 = 1/2` đầu trang 67 nhận cha ở trang 66 |

Sau mỗi lần sửa đều kiểm: hash 11 bảng F54, trang in và V-01 không đổi.

## 6. Thay đổi contract đã được duyệt

| Luật | Thay đổi | Lý do (bằng chứng) |
|---|---|---|
| T-06 | Bỏ "cùng vị trí x" và "trang liền nhau"; gom theo offset ≥ 3 trang | OCR gộp dòng footer (F86 trang 6, 11); một số in sai không được làm mất cả đoạn |
| T-10 | (1) phủ picture ≥ 90% thay IoU ≥ 0,9; (2) cùng hash nội dung + cùng vị trí | (1) F54 trang 171 IoU 0,53; (2) I-24 |
| T-11 | Đích phải chồng theo chiều ngang; dùng `table_caption_keywords`; hòa → giữ liên kết Docling | F86 trang 9 (logo lề phải); I-24 |
| T-14 | Thêm nguồn crop: nét vector, chữ của hình | F86 bản vẽ vector, nhãn ngoài bbox |
| T-17 | Luật mới: xác nhận header/footer | I-21 |
| T-18 | Luật mới: nhãn sát hình; bổ sung loại dòng ở lề trái | F86 `320 mm`; I-25 |
| T-19 | Luật mới: gộp phần tử hình trùng | I-27 |
| T-12, T-13 | Chạy cả trên text; `param_text_patterns`; `TextParamRef` (vị trí + vai trò); near-miss chỉ báo cáo | `M100`/`M8` không phải parameter; BL-17 cần evidence nguyên văn |
| T-08 v1.1 | `list_param_mismatch` | F54 trang 96 |
| T-08 | v1: lề trái là tín hiệu chính, glyph phụ (cần khoảng trắng); ngắt khối bởi mọi phần tử không phải list; nối qua trang; mã review `list_level_ambiguous`; ngưỡng `list_indent_min` | Luật cũ: con trang 67 mồ côi; con cùng lề không glyph bị coi là cấp 1; glyph dùng sai gây gán nhầm |
| Thứ tự | Hình chạy trước bảng | T-09, T-11 ảnh hưởng T-03 |
| `NormalizedElement` | Thêm `parent_element_id`, `figure_text`, `image` (gồm `crop_sources`), `caption_link`, `duplicate_of`; `lang` cho phép `null`; `list_info` thành model `ListInfo`; `param_refs` thành `TextParamRef` | — |
| `objects.json` | Thay `bitmaps.json`; thêm px, `hash`, nét vector | T-09, T-10, T-14 |
| Contract C2 (2026-11-09) | Contract mới cho chunk: map cột `doc_chunks`, cha–con, ngôn ngữ, thủ tục, hình, bảng, kiểm 2b; §1 bảng hiện tại là mốc + `DraftChunk` độc lập với bảng; §13 khoảng trống schema S-01…S-07; §14 quy tắc R-01…R-11 | Luồng tra cứu trả content của chunk cha; góp ý duyệt của Toma; chạy thật trên F54, F86 |

## 7. Kết quả kiểm hiện tại (2026-11-09)

**F54**, 171 trang, run `data/ingest_runs/f54/bl11-text` (raw của run `20261109-063902` parse từ PDF + PDF để render, profile `qs_controller`; run tham chiếu hiện tại. Run `bl09-t08` cho cùng số liệu trừ phần mã trong text; run `fix-i27` trước đó không còn thư mục):

| Mục | Giá trị |
|---|---|
| Phần tử | 2.619; heading 129, label_heading 181, list_item 482, text 230, caption 152, furniture 659, figure_text 518, toc 5, unsupported 1 |
| Bảng logic | 11 (181 dòng). Hash nội dung (16 ký tự đầu) làm mốc: t001 `cf5b8d6f7bb5d37a`, t002 `bbc805a4f6034edd`, t003 `b5c05dd11aee3c9c`, t004 `bfc061cb6bb3c393`, t005 `0bd56176feaadea1`, t006 `7df6b4bd7c95208a`, t007 `17c4669c5cea8806`, t008 `4d303479c820e09c`, t009 `b22e0a50131f9653`, t010 `edef83830b7a371c`, t011 `7ed920a63e8538e6` |
| Hình | picture 206, screenshot 33, watermark_candidate 8; `duplicate_image` 5, `repeated_image` 3, `caption_relinked` 1; 242 ảnh crop |
| Header/footer | 4 chuỗi lặp, mỗi chuỗi trên 164–165 trang (cụ thể: số trang ở trang 8–171, `www.qstcnc.com` ở trang 1 và 8–171) |
| Trang in | PDF trang 9 → 2, trang 171 → 164; trang 1–7 không có số |
| V-01 | 168 đạt, 0 lỗi, 3 không đo được (bìa OCR, hai trang chỉ có hình) |
| List (T-08) | 482 list_item, 103 con, độ sâu tối đa 1, 0 mồ côi, 3 `list_level_ambiguous` (trang 71), 2 `list_cross_page` |
| Mã trong text (T-12) | 227 ref ở 220 phần tử: 98 định nghĩa, 75 giá trị, 54 nhắc tới; phủ 302/302 token; near-miss 9; `list_param_mismatch` 2 (trang 96) |
| Review (26) | chặn chunk 3, chặn fact 20, không chặn 3 |

**F86**, trang 5–17, run `data/ingest_runs/f86/bl11-text` (PDF + fixture `f86_ocr`; giống `fix-i27`, thêm 7 list_item, 0 con, 0 mã):

| Mục | Giá trị |
|---|---|
| Heading | 16; 5 heading I-21 đã trả về body |
| Hình | picture 24, 24 ảnh crop; nhãn T-18: 7; `repeated_image` 5 (logo); `caption_relinked` 2 (trang 17) |
| Header/footer | `QS TECHNOLOGY CO.,LTD` và `PAGE n` (11 trang) |
| Review | `ocr_required` 13 (mọi trang OCR, chặn chunk), `furniture_reclassified` 5 |
| V-01 | không đo được (không có text layer) |

**Chunk nháp** (run `eval-b`, build lại 2026-11-09 sau `figure-ocr`; profile `qs_controller`; token đếm bằng tiktoken):

| Mục | F54 | F86 Installation | F86 Operation (nháp) |
|---|---|---|---|
| Chunk (cha/con/độc lập) | 323 (62/178/83) | 26 (2/4/20) | 16 (0/0/16) |
| Loại chunk lá | figure 71, procedure 64, wiring 51, overview 35, parameter 30, table 8, alarm 1, dimension 1 | wiring 11, figure 8, pinout 4, overview 1 | figure 7, wiring 6, overview 2, dimension 1 |
| Độ dài content chunk lá (min/trung vị/max) | 14 / 239 / 2.449 | 20 / 59 / 2.472 | 30 / 82 / 411 |
| CQ-01…CQ-10, CQ-RB | đạt | đạt | đạt |
| Độ phủ phần tử | 1,0 (1.402/1.402), 0 lặp | 1,0 (72/72), 0 lặp | 1,0 |
| Ranh giới (nhãn nháp) P / R / đúng loại | 1,0 / 1,0 / 0,9 (10 đơn vị, trang 18, 19, 87, 88, 90) | 1,0 / 1,0 / 0,71 (7 đơn vị, trang 6, 11, 12, 13, 18, 26) | — |
| Lỗi ràng buộc bảng `doc_chunks` (adapter v1) | 0 | 0 | 0 |
| Chunk lá có review chặn | 2: `ocr_required` (bìa), `caption_ambiguous` (trang 38) | 7: `text_coverage_gap` 4, `orphan_row` 3, `ocr_required` 1 | 16: `ocr_required` |
| Cờ | `embed_truncated` 3, `table_part` 3, `block_split` 2, `table_no_header` 2, `ocr_page` 2 | `table_part` 4, `toc_like` 1, `ocr_page` 1 | `ocr_page` 16 |
| So với chunk tay (CSV) | — | 7/27 chunk tay ≥ 60% token trong một chunk builder | 0/65 (run chỉ có trang 5–17) |
| Duyệt tay (`chunk_review.json`) | 0 ok / 0 fix / 323 chờ | 0 ok / 0 fix / 26 chờ | 0 ok / 0 fix / 16 chờ |
| Cổng 2b | chưa đủ dữ liệu (tạm) | chưa đủ dữ liệu (tạm) | — (toàn bộ bị chặn) |

Đã kiểm tay trên dữ liệu thật (2026-11-09): F54 mục 2.3.2.4 ra 1 cha + 5 con đúng ví dụ C2 §11; M100 Stage 1–10 ra 1
`procedure` + 1 `alarm` liên kết hai chiều; bảng parameter t009–t011 chia phần lặp header, mỗi dòng đúng một lần. Loại sai
trên nhãn nháp: F54 2.3.3 (`wiring`, mong đợi `figure`), F86 2.1 ghi chú (`wiring`, mong đợi `overview`), F86 2.8
(`figure`, mong đợi `wiring`) → I-35.

**Test** (2026-11-09)
- `.venv-ingest`, `tests\doc_ingest`: 310 passed.
- `backend/venv`, `backend\tests`: 848 passed, 14 skipped (1 cảnh báo Starlette, không liên quan).
- `.gitignore` có `build/` (output đóng gói) nên đã thêm ngoại lệ `!backend/app/modules/doc_ingest/build/` để package
  chunk builder được theo dõi.
- `npm run lint` của frontend đang fail sẵn (286 lỗi ở `src/`, không liên quan tới luồng này); `npm run build` đạt.

**Báo cáo HTML**
- `data/ingest_runs/f54/bl11-text/report/index.html` (có mục List, Mã parameter)
- `data/ingest_runs/f86/bl11-text/report/index.html`
- Chunk nháp: `data/ingest_runs/{f54,f86_italliation,f86}/eval-b/report/chunks.html`
- Đánh giá: `data/ingest_runs/{f54,f86,f86_italliation,f10t}/eval-b/report/index.html` (mục Độ khớp profile) và `.../eval-b/report/eval.html`

## 8. Còn tồn đọng và bước tiếp theo (2026-11-09)

**Review trên F54**
- Chặn chunk:
  - `ocr_required` (trang bìa);
  - `unsupported_element` (công thức, trang 147);
  - `caption_ambiguous` (trang 38: Docling gộp Figure 39 và 40 vào một hình).
- Chặn fact (18):
  - `applicability_note` 7;
  - `applicability_model_unmatched` 6;
  - `list_level_ambiguous` 3 (trang 71);
  - `list_param_mismatch` 2 (trang 96, lỗi soạn thảo của tài liệu);
  - `header_missing` 2.
- Không chặn:
  - `watermark_conflict` (trang 160);
  - `furniture_unconfirmed` 2 (trang 1–2);
  - 3 hình có `repeated_image`.

**Review chặn chunk trên F86 Installation:** `text_coverage_gap` trang 2 (mục lục, I-31) và trang 26; `orphan_row` 3
(bảng cổng t001); `ocr_required` trang bìa.

**Chưa làm**
- Team xác nhận nhãn mẫu (`verified: true`), sau đó chạy lại `eval`.
- I-28, I-29, I-30 (F10T): cần quyết định hướng sửa trước khi dùng tài liệu scan tiếng Việt.
- V-02…V-04 (BL-25).
- Team duyệt cổng 2b: xác nhận nhãn ranh giới (`*.chunks.json`), ghi `chunk_review.json`.
- I-32 (bảng cổng F86 lệch ô) trước khi dùng chunk `pinout` của F86 Installation.
- Trích fact (BL-17).
- Gán unit và CLI review (BL-19, BL-21).
- Xuất bản (BL-22, BL-90…).
- Trả ảnh và trích dẫn trong câu trả lời chatbot (BL-92).
- Bảng vẽ dưới dạng ảnh, F86 trang 15 (I-22).
- Render trang xoay.
- Chạy F86 đủ 97 trang (BL-13).
- Chép kích thước từ bản vẽ khi duyệt (fact `spec` `human_verified_figure`, V1.1).
- Xem lại luật T-08, T-12 khi chạy tài liệu mới (F86 đủ 97 trang, F10T, tài liệu tiếng Việt).

**Contract chunk C2 (đã duyệt, 2026-11-09):** [p2_chunk_contract.md](../reports/p2_chunk_contract.md) — map từng cột `doc_chunks`, quy tắc cha–con theo cách retriever trả nội dung chunk cha, ngôn ngữ chunk, thủ tục, hình, bảng, kiểm chất lượng Bước 2b. Luồng tra cứu không đổi. Lỗi mới E-05 (nhánh FTS của `match_doc_chunks`).
Góp ý khi duyệt: bảng `doc_chunks` hiện tại chỉ là **mốc** (dựng từ chunk F86 viết tay), chưa phải đích cố định. `DraftChunk` giữ thêm trường ứng viên có kiểu; adapter `export/doc_chunks_v1.py` ra đúng bảng hiện tại. Bảy khoảng trống schema S-01…S-07 (C2 §13) sẽ được đo ở đánh giá tra cứu offline (Bước 4) và đề xuất ở Bước 5 (`p2_doc_chunks_schema_review.md`); migration là thay đổi riêng ở module chatbot.

**Quy trình nạp tài liệu mới (B6):**
1. Chạy `run` với profile `default`.
2. Đọc mục "Độ khớp profile" trong báo cáo HTML.
3. Chọn hoặc tạo profile (dữ liệu YAML, không sửa code): mẫu mã `param_text_patterns`, `code_patterns`, lexicon.
4. Chạy lại `run` với profile đó.
5. Xử lý hàng review.
6. Nếu là loại tài liệu hoặc hãng mới: gán nhãn mẫu 8–15 trang, chạy `eval`.
7. Chỉ tài liệu đạt cổng mới đưa sang BL-16: thêm manifest `manifests/{doc}.yaml`, chạy `build` (+ `figure-ocr` nếu
   có hình), gán nhãn ranh giới `{doc}.chunks.json`, team duyệt `chunks.html` / `chunk_review.json` (cổng 2b).

**Thứ tự đề xuất:** team duyệt cổng 2b (trang `chunks.html`) → Bước 3 làm giàu tiếng Việt (báo chi phí trước) →
Bước 4 đánh giá tra cứu offline → Bước 5 đánh giá schema `doc_chunks`; song song: I-32, I-28/I-29/I-30.
