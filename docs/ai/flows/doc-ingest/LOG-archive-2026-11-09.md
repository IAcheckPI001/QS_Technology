# Nhật ký luồng doc-ingest: lưu trữ tới 2026-11-09

Chép nguyên văn các mục 4–8 của `docs/ai/chunking_builder/chunking_flow_log.md` khi tách
nhật ký ngày 2026-11-11 (chỉ sửa đường dẫn liên kết). Không sửa file này. Số mục giữ như
bản gốc để các tham chiếu cũ còn đúng. Cuối file có phụ lục chép các bản ghi về
`doc_ingest` từ `current-state.md`.

- Mục 4 xếp từ cũ tới mới; các mục từ 2026-11-10 trở đi ở [LOG.md](LOG.md), mới nhất ở trên.
- Mục 5 và 6 dừng ở 2026-11-09: I-36 và luật T-20 có trong LOG.md, không có ở đây.
- Mục 7 là ảnh chụp ngày 2026-11-09. Dòng "Duyệt tay 0 ok / 0 fix / 323 chờ" là số trước lần
  duyệt tay 2026-11-10.
- Mục 8 mang ngày 2026-11-09 nhưng có hai dòng đã được sửa ngày 11-10 và 11-11 (duyệt tay F54,
  I-36). Trạng thái hiện tại ở [STATE.md](STATE.md).

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
- Team duyệt cổng 2b: xác nhận nhãn ranh giới (`*.chunks.json`); ghi `chunk_review.json` cho F86 Installation
  (F54 đã ghi 2026-11-10: 270 ok / 53 fix).
- I-36 xong trên text layer (eval-c): duyệt 36 chunk `pending` của eval-c. Còn I-37…I-40 (I-37 tiếp theo: chunk hình chỉ có
  tiêu đề mục, nhãn khung "Instructions / Model" còn lại ở trang Docling không gom khung).
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

**Contract chunk C2 (đã duyệt, 2026-11-09):** [p2_chunk_contract.md](../../reports/p2_chunk_contract.md) — map từng cột `doc_chunks`, quy tắc cha–con theo cách retriever trả nội dung chunk cha, ngôn ngữ chunk, thủ tục, hình, bảng, kiểm chất lượng Bước 2b. Luồng tra cứu không đổi. Lỗi mới E-05 (nhánh FTS của `match_doc_chunks`).
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

## Phụ lục: bản ghi về `doc_ingest` từ `current-state.md`

Chép nguyên văn (tiếng Anh) ngày 2026-11-11 khi rút `current-state.md`; chỉ sửa đường dẫn
liên kết. Mục cuối của phần "Validation record" có nội dung tới 2026-11-11.

### Dòng P7 của bảng "Completion summary"

| P7 technical document ingest (`doc_ingest`) | Parsing spike done (F54); contract C1 locked (rev 3); table normalization, profile, approval core and CLI `run` with HTML report implemented and tested; pipeline PDF → chunk not complete | Offline CLI tool in a separate `.venv-ingest` (Docling), isolated from the chat service (import boundary tested both ways, excluded from the chat image via `backend/.dockerignore`). C1 locked 2026-11-03 (D-02, D-03, D-04 data model, D-08, D-11); rev 3 changes T-01 to whitespace-gap column boundaries because the rev 2 rule failed on F54 itself. Implemented: `schemas/` (Pydantic, `extra="forbid"`), `profile.py` + `profiles/` (`default`, `qs_controller`, registry vocabulary snapshot), `normalize/` (Docling JSON reader; logical tables T-01…T-05, T-15), `technical_refs/` (ParamRef T-12, applicability T-13 on table cells), review queue, `review/approval.py` (unit states, serve rule, approval gate, carry-over by id then unique hash match, risk-based bulk approval, publish rule), CLI `run` (`cli.py`, `pipeline.py`, `report/html_report.py`, `parse/docling_runner.py`): PDF or saved Docling JSON → run dir `data/ingest_runs/{doc_id}/{run_id}/` + `report/index.html` showing each step. T-13 output is `applicability_candidates` (candidates, not facts). Tests: five C1 groups (LT, HC, AP, HA, PI) on the F54 fixture plus synthetic fixtures, none need Docling. Also implemented: Docling label classification (T-16), V-01 text coverage, S0 with per-page OCR, header/footer check (T-17), printed pages (T-06), section paths (T-07), `NormalizedElement`, figures (T-18 labels next to pictures, T-09 screenshot, T-10 watermark candidate, T-11 caption, T-14 crop + render to `normalized/images/`, T-19 duplicates), list parent/child (T-08 v1), T-12/T-13 on text. Not implemented: V-02…V-04, chunk builder, fact extraction, unit assignment, review CLI, publish, web upload. No DB writes. `doc_chunks` still holds hand-authored F86 chunks loaded by `chunking_loader/load_csv.py`. |

### Mục "P6 — Technical document ingest" của "Next remediation order" (việc 25–30)

Design and per-step status are in `docs/ai/architecture.md`; the task list is
`docs/ai/reports/p1_implementation_backlog.md` (BL-xx).

Done: P-1 Parsing Spike on F54 (pdf pages 9, 11, 14, 18, 19, 40, 167–171;
Docling 2.145.0, `do_ocr=False`, TableFormer accurate, ~96 s), spike tool
`doc_ingest/spike/` (`run_spike.py`, `render_review.py`), `requirements-ingest.txt`,
`.gitignore` entries, and the P-1 documents (BL-00, BL-01). The module and the
P-1 documents are committed. Note: `docs/ai/doc_ingest_spike/source/F54_Operation
Manual (English Version)_V.02.pdf` is tracked in git although `source/` is meant
to be gitignored; whether to keep it is not decided.

Current step: **Ingestion V1 group A–C in progress** (C1 locked 2026-11-03).

25. Reviewer fills the "Người duyệt" column in `parsing_spike.md` and confirms
    decisions 1–11 (all rows are currently empty).
26. Run the spike on F86 (BL-13, D-07). Both F86 PDFs are now in
    `docs/ai/doc_ingest_spike/source/`, but no F86 output exists; required
    before S1 image rules (vector diagrams) are approved.
27. Done (2026-11-03): D-02, D-03, D-04 (data model), D-08, D-11 decided and
    contract C1 locked as rev 3 (BL-14); details in
    `p1_chunking_impact_assessment.md` §6. Still open: D-12 (V-xx/S0 thresholds)
    blocks chunk generation; D-05, D-06, D-09, D-10 and the LLM part of D-04 block
    later steps (F54 publish, F86 facts, unit publish, per-code values, fact
    extraction).
28. Ingestion V1 group A–C. Done (2026-11-03): schemas for tables, profile and
    review (BL-04 partial; `NormalizedElement` and validation schemas missing),
    configuration profile (BL-26), registry vocabulary snapshot (BL-29), table
    normalizers T-01…T-05 and T-15 (BL-05, BL-06, BL-27), T-12/T-13 on table cells
    (BL-11 partial), approval core (BL-18, BL-20 partial), synthetic fixtures
    (BL-31). Remaining: fixture text-layer words (BL-02b), V-01…V-04 (BL-25), chunk assertion
    library (BL-15), whole-pipeline determinism (BL-23), F86 spike (BL-13).
    Done earlier (2026-11-02): isolated module skeleton, golden F54 fixture
    (BL-02), F86 baseline lock (BL-03).
29. Ingestion V1 group D–E: baseline chunk builder, draft fact extraction,
    quality gate, knowledge units, review CLI, approved package (BL-16…BL-22).
30. Production integration (BL-90…BL-94): new tables, `doc_chunks` changes
    (`unit_id`, nullable embedding, `parent_id` from `parent_key`), loader,
    runtime facts/assets, eval vs. F86 baseline. Not planned yet.

### Các mục `doc_ingest` của "Validation record"

- `doc_ingest` isolated module skeleton (`geometry.py`, `parse/`, golden F54
  fixture, import-boundary tests, F86 baseline lock) (2026-11-02): backend
  pytest in `backend\venv` **557 passed, 11 skipped** (the skips are the
  `requires_docling` tests); `.venv-ingest` `pytest tests\doc_ingest`
  **37 passed**. Spike re-run on pages 11 and 18 after the helper move: Docling
  JSON byte-identical, `p*_items.json` identical apart from the crop timing
  field `ms`.
- `doc_ingest` C1 implementation (schemas, profile, table normalization T-01…T-05
  and T-15, T-12/T-13 on cells, approval core, five C1 test groups) (2026-11-03):
  backend pytest in `backend\venv` **659 passed, 11 skipped** (skips are the
  `requires_docling` tests); `.venv-ingest` `pytest tests\doc_ingest`
  **138 passed**. GT-23 scan checked by inserting `"F54"` and `r"^#\d"` into a
  rule module (test failed, file restored). Tests that need later steps (LT-10,
  LT-11, AP-08…AP-10, HA-10…HA-12, PI-09) are listed as pending in
  `p1_golden_tests.md` §6, not implemented as stubs.
- `doc_ingest` CLI `run` + HTML report, `applicability_candidates`, carry-over by
  hash (2026-11-03): backend pytest in `backend\venv` **668 passed, 11 skipped**;
  `.venv-ingest` `pytest tests\doc_ingest` **147 passed**. Manual: CLI with Docling
  on the F54 PDF (pages 11, 14, 167–171, ~79 s of Docling) gave `tables.jsonl` with
  the same content hashes, cells, flags and review items as `--raw-dir` on the
  fixture; report opened from `data/ingest_runs/f54/verify-f54/report/index.html`
  (rendering checked by tests on HTML content, not in a browser by Claude).
- `doc_ingest` safety net (2026-11-03): Docling label classification (T-16: table of
  contents `document_index` kept, unsupported labels flagged `unsupported_element`), reader
  now walks children of every node (captions were silently missing before), V-01 text
  coverage against the PDF text layer (`words.json`, provisional thresholds 0.9/0.1, D-12
  open). Found from the user's run of F54 pages 5–10, where the table of contents was
  dropped without any flag. Backend pytest in `backend\venv` **679 passed, 12 skipped**;
  `.venv-ingest` `pytest tests\doc_ingest` **159 passed**. Re-run of pages 5–10: TOC kept
  (3 × T-16), V-01 passed 6/6; F54 fixture V-01 passed 11/11.
- `doc_ingest` S0 + per-page OCR (2026-11-03): the user's F86 Operation Manual run
  (pages 1–17) showed pictures but no text: the PDF has no text layer (text drawn as
  bitmaps/paths), Docling ran without OCR, and the report showed 0 review items. Now S0
  measures each page, pages without a text layer are OCR'd with RapidOCR (torch backend,
  already in `.venv-ingest`; the default onnxruntime backend is not installed) and get
  `ocr_required` (blocking). Re-run of F86 pages 1–17: 17/17 OCR, 235 s; captions
  (Figure 1-1…2-11) and headings recovered; open issues I-21 (headings tagged as page
  headers become furniture), I-22 (table drawn as an image, page 15), I-23 (OCR errors).
- `doc_ingest` T-17 / T-06 / T-07 (2026-11-03): fixes I-21. Docling header/footer labels
  are now checked: strings repeated on ≥ 3 pages in the top/bottom band (digits treated
  as equal), lines merged from them, or profile `furniture_patterns` are furniture; a
  header/footer seen once that is a numbered heading returns to the body
  (`furniture_reclassified`, non-blocking); other single ones stay furniture with
  `furniture_unconfirmed` (non-blocking). OCR text inside pictures becomes `figure_text`
  (not body text, not headings). Printed page numbers come from /PageLabels or the footer
  number sequence, never from an offset. `normalized/elements.jsonl` holds
  `NormalizedElement` rows (fields for T-08…T-11 still empty). F86 pages 5–17 OCR output
  is now a fixture (`fixtures/docling/f86_ocr`). F54 table hashes unchanged.
- `doc_ingest` figures, BL-10 (2026-11-03): the run now stores `raw/p{n}.objects.json`
  (bitmaps with pixel size, vector paths; objects inside a Form XObject use the form's
  bounds, which fixes a wrong position for F54 page 18). New rule T-18 attaches short labels
  next to a picture (F86 `320 mm` on pages 8 and 9) as `figure_text`. T-14 crop = Docling
  bbox + covering bitmaps + nearby vector paths + the picture's labels, rendered to
  `normalized/images/` when the run has the PDF. T-09 turns a 0-cell table covered by a
  bitmap into `screenshot`; T-10 marks a caption-less picture inside a bitmap repeated on
  ≥ 3 pages (same pixel size and same displayed size, any position) as
  `watermark_candidate` (condition changed from IoU ≥ 0.9 to ≥ 90% of the picture covered,
  because IoU missed F54 page 171; F86: 5 logos caught); T-11 moves figure/table captions to
  the nearest target. Text inside or next to pictures is only a keyword for the picture,
  never chunk body or a fact. HTML report has a Figures section. Picture units, review and
  serving images with answers are still not built (BL-19, BL-21, BL-92).
- `doc_ingest` full F54 run (171 pages, run `20261103-144432`, re-checked 2026-11-08 with
  the current code: same output). All output files pass their schemas; V-01 168 passed,
  0 failed, 3 not run (cover page OCR, two picture-only pages); 11 logical tables, 128
  headings, 33 screenshots, 247 rendered crops. Defects found then: T-10 treated UI
  screenshots of the same pixel and display size as a repeated bitmap (7 of 15 watermark
  candidates and 7 of 8 conflicts were real screenshots, I-24); T-18 took short section
  labels at the text left margin (I-25); `PART 1:CONTROLLER OVERVIEW` was not a heading
  (I-26). Normalized output is the chunk builder's input; no chunks are produced yet (BL-16).
- `doc_ingest` fixes I-24…I-26 (2026-11-08): `objects.json` bitmaps carry a content `hash`;
  T-10 watermark = same content at the same position on ≥ 3 pages, while the same content
  at other positions only gets the info flag `repeated_image`; T-18 skips lines starting at
  the document's text left margin; the keyword heading pattern accepts a title glued after
  `:`; T-11 keeps the Docling link when two candidates tie. Full F54 re-run (PDF objects on
  the saved raw): 8 watermark candidates, all real; 1 watermark conflict; 1 caption
  ambiguity (page 38, real); table hashes and printed pages unchanged.
- `doc_ingest` I-27 (2026-11-08): Docling sometimes emits both a picture and a 0-cell table
  for one screenshot. New rule T-19: two figure elements on a page with IoU ≥ 0.9 are one
  image; the captioned one (else the screenshot, else the first) is kept, the other gets
  `duplicate_image` and `duplicate_of`, no crop and no caption; nothing is deleted. Full
  F54: 5 duplicates (pages 64, 81, 85, 96, 98), rendered crops 247 → 242, everything else
  unchanged; F86 pages 5–17 unaffected.
- `doc_ingest` summary log: [chunking_builder/chunking_flow_log.md](../../chunking_builder/chunking_flow_log.md)
  collects the flow, step status, change history and fixed issues in one place (2026-11-08).
- `doc_ingest` reference run (2026-11-09): F54 171 pages re-parsed from the PDF
  (`data/ingest_runs/f54/20261109-063902`) reproduces the `fix-i27` figures exactly; its table
  hashes are now the baseline (listed in the summary log). No code change.
- `doc_ingest` BL-09 / T-08 v1 (2026-11-09): new `normalize/lists.py`. Docling returns lists
  flat, so the level comes from the left margin (main signal); a bullet glyph followed by a
  space only counts for a 3–18 pt indent. Any non-list body element ends a list block; a list
  at the top of a page continues the list ending the previous page (`list_cross_page`).
  Unclear cases get a review item instead of a guessed parent: `list_orphan` and the new
  `list_level_ambiguous` (both block facts, not chunks); siblings with different markers get
  `list_marker_mixed`. `list_info` is now the typed `ListInfo`; `RunReport.lists`; HTML report
  section "List". Full F54: 482 list items, 103 children, 0 orphans, 3 ambiguous (page 71),
  review 21 → 24, everything else unchanged; F86 pages 5–17 unchanged. Rule is v1, checked on
  F54 only.
- `doc_ingest` BL-11 text part (2026-11-09): `technical_refs/params.py::find_param_refs` and
  `normalize/text_refs.py`. Parameter codes in body text become `TextParamRef` (ParamRef +
  `start`/`end` + `role` definition/value_option/mention). Only prefixes listed in the new
  profile field `param_text_patterns` are scanned (`qs_controller`: `#` 4–5 digits, `M` exactly
  4, so M-code `M100` and pin `M8` are not parameters; they are counted as near-misses).
  T-13 also runs on text. T-08 v1.1: new review `list_param_mismatch` when a list child talks
  about a different code than its parent defines. Step `s1_refs` is now implemented;
  `RunReport.refs`; HTML section. Full F54: 227 refs (98/75/54), 302/302 code tokens covered,
  2 mismatches on page 96 (an editing error in the manual itself), review 24 → 26, everything
  else unchanged; F86 unchanged. Next: evaluation on other documents (profile fit report,
  labelled samples, F86 Installation and F10T).
- `doc_ingest` BL-34 multi-document evaluation (2026-11-09): `eval/profile_fit.py` adds
  `RunReport.profile_fit` (code tokens matched, near-misses, unknown code shapes, OCR share,
  big pictures holding sentences, Vietnamese text on OCR pages) and warning signals shown in
  the HTML report; nothing is changed automatically. New CLI `eval --run-dir --labels` scores
  a run against hand-labelled sample pages (`tests/doc_ingest/fixtures/eval/*.labels.json`,
  drafted by Claude from the PDF text layer and page images, `verified: false` until the team
  confirms) and writes `report/eval.json`/`eval.html`; the gate needs ≤ 50% OCR pages plus
  T-12 precision ≥ 0.99, recall ≥ 0.95, roles ≥ 0.95, no wrong list parent, all lexicon notes,
  ≥ 95% body sentences kept. Provisional results: F54 and F86 Installation pass; F86 Operation
  and F10T fail on OCR. New issues: I-28 (F10T: Docling takes a whole two-column page frame as
  one picture, so instructions become figure text), I-29 (OCR runs in English on a Vietnamese
  scan: diacritics lost), I-30 (`M0100.txt` macro name read as parameter). Not fixed yet.
- `doc_ingest` BL-16 chunk builder + BL-15 chunk checks (2026-11-09, **draft, awaiting team review of
  the 2b gate**): stage 2 `build` reads an existing normalized run + a document manifest
  (`manifests/*.yaml`) and writes `build/chunks.jsonl` (`DraftChunk`, independent of the table),
  `build/doc_chunks_v1.jsonl` (adapter to the current `doc_chunks` columns, candidate fields in
  `metadata`), `build/chunk_quality.json` (CQ-01…CQ-10, coverage, boundaries vs draft labels
  `fixtures/eval/{doc}.chunks.json`, comparison with the hand-written F86 CSV, review summary, gate),
  `build/chunk_review.json` (team verdicts) and `report/chunks.html`. CLI: `build`, `figure-ocr`
  (RapidOCR torch on figure crops of text-layer pages → keywords only); `run` calls `build` when a
  manifest exists. No DB writes; the chatbot retrieval flow is unchanged; no Vietnamese text yet (step 3).
  Results: F54 323 chunks, F86 Installation 26; CQ pass, coverage 1.0, boundaries P/R 1.0 on draft
  labels (type accuracy 0.9 / 0.71). New issues I-31 (F86 TOC page not detected), I-32 (F86 port table
  description cells shifted between rows), I-33 (figure chunks without caption carry only the heading),
  I-34 (port table granularity vs per-connector hand chunks), I-35 (coarse chunk-type rules).
  The FTS-branch bug was renumbered E-05 (E-02 already existed).
  Manual 2b review of F54 (2026-11-10): `chunk_review.json` has 270 ok / 53 fix, so the manual-review
  gate fails until the builder/normalizer is fixed and `build` is re-run. Open issues from the review:
  I-36 (P0: on F54 text-layer pages Docling takes the "Instructions" column frame as a picture, so 39
  instruction passages on 23 pages become figure text and steps are missing from 13 chunks), I-37
  (near-empty chunks, screenshots split from their instructions), I-38 (parameter tables over the
  800-token embed limit), I-39 (block split inside a worked example), I-40 (minor: figure order, OCR
  keyword noise, repeated boilerplate, source errata). F86 Installation is not reviewed yet.
  I-36 fixed for text-layer pages (2026-11-11): new normalization rule T-20 "text frame" returns the text of a
  picture that is really an instruction frame (step labels or sentences, mostly multi-word lines, not a
  frame title) to body text; frame titles stay figure text and step captions become text in reading
  order. OCR pages are untouched (I-28 stays open). New `build --carry-review/--carry-chunks` copies
  verdicts by content hash + section path. Run `f54/eval-c`: 342 chunks, exactly the 13 affected
  sections changed and now hold all their steps; CQ and BL-34 pass; 306/342 verdicts carried, 36 pending
  review. F86 Installation/Operation and F10T: 0 frames.
- `doc_ingest` C2 chunk contract (2026-11-09, approved with changes to §1, §2 and a new §13):
  [reports/p2_chunk_contract.md](../../reports/p2_chunk_contract.md) maps every `doc_chunks` column to its
  source, based on a read of the current retrieval flow (`Retriever`, `match_doc_chunks`,
  `product_docs_ask`). Key points: a matched child returns its **parent's** content and assets, so a
  parent is a context window holding its children verbatim (≤ 2,500 chars, one level); content stays in
  the source language while `embed_text` always carries a Vietnamese summary/FAQ/keywords (queries are
  rewritten in Vietnamese); procedures are never split per step; figure labels go to keywords only.
  The retrieval flow itself is not changed. New issue E-05: the FTS branch of `match_doc_chunks` drops
  all rows when the model filter is an empty array (vector branch treats it as no filter); to be fixed
  separately in the chatbot module.
