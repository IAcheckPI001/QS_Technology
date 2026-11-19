# Luồng doc-ingest: chunking tài liệu kỹ thuật (`doc_ingest`)

Thiết kế của luồng. Trạng thái hiện tại ở [STATE.md](STATE.md), lịch sử ở [LOG.md](LOG.md).

## Phạm vi

Biến PDF manual (F54, F86, F10T…) thành phần tử đã chuẩn hóa (`NormalizedElement`), rồi
thành chunk nháp có provenance (trang, vùng trên trang, nguồn CRM) để người duyệt, với đích là
nạp vào bảng `doc_chunks_v2` cho `match_doc_chunks_v2` truy xuất. Đây là **tool offline chạy bằng
CLI**. Luồng không ghi database và không chạy được từ dịch vụ chat. PDF lấy từ kho tài liệu công
khai của CRM bằng `crm-plan`/`crm-fetch` (mục "Nạp tài liệu từ CRM") hoặc đưa tay.

**Mục tiêu là luồng chung cho mọi PDF được upload**, không phải xử lý riêng một tài liệu
(Toma, 2026-11-13). F54 là **bản triển khai thí điểm đầu**: chạy trên F54 để phát hiện lỗi
mới, sửa và chuẩn hóa luồng, rồi áp cho các PDF upload sau. Nguyên tắc khi sửa lỗi gặp ở F54:

- Sửa bằng **luật chung** (T-xx, R-xx, CQ-xx, kiểm tự động); thứ phụ thuộc hãng hoặc dòng tài
  liệu (watermark, mẫu mã, thuật ngữ, từ màn hình máy) để trong **profile** YAML, không viết
  cứng trong code.
- Ghi đè riêng một tài liệu (trang loại, errata, nhóm ảnh) chỉ qua **manifest**, kèm lý do;
  không dùng ghi đè để che lỗi của luật chung.
- Mỗi lỗi mới ghi thành issue (I-xx) có mô tả **dạng lỗi** để nhận ra ở tài liệu khác; mỗi
  luật mới có test và chạy hồi quy trên các tài liệu đã có (F86 Installation, F86 Operation)
  để không làm hỏng tài liệu khác.
- Ngưỡng, cổng duyệt và chi phí (làm giàu, vision) đánh giá theo cả lô tài liệu, không chỉ F54.

## Điểm vào

CLI `backend/app/modules/doc_ingest/cli.py`, chạy từ thư mục `backend`:

| Lệnh | Việc | venv |
|---|---|---|
| `run --pdf <file> --doc-id <id> [--pages …] [--profile …]` | Parse Docling + chuẩn hóa + báo cáo HTML; gọi `build` ở cuối khi có manifest (`--no-build` để tắt) | `.venv-ingest` |
| `run --raw-dir <dir> --doc-id <id>` | Chuẩn hóa lại từ Docling JSON đã lưu, không cần Docling | `backend/venv` |
| `eval --run-dir <dir> --labels <file>` | Chấm run theo nhãn mẫu → `report/eval.json`, `eval.html` | cả hai |
| `build --run-dir <dir> [--manifest …] [--labels …] [--carry-review … --carry-chunks …]` | Chunk builder + kiểm chất lượng trên run có sẵn | `backend/venv` |
| `figure-ocr --run-dir <dir>` | OCR nhãn trong hình ở trang có text layer → `build/figure_ocr.jsonl` | `.venv-ingest` |
| `curate-check --catalog-run <dir>` | Kiểm dữ liệu biên soạn `curated/` với chữ PDF của run nguồn | cả hai |
| `curated-build --catalog-run <dir> --doc-version <v>` | Dữ liệu biên soạn đã duyệt → chunk `product_catalog` (`source = manual`) → `qs_catalog/<run_id>/build/` | `backend/venv` |
| `crm-plan` | Đọc cây tài liệu CRM, so với sổ nguồn → `data/crm_sync/<ts>/plan.md` (mới / đổi phiên bản / bất thường / bị gỡ / bỏ qua) | cả hai |
| `crm-fetch --plan <dir> [--only <doc_id>…]` | Tải PDF mới/đổi phiên bản → `data/crm_sources/<doc_id>/<version>/`, sinh manifest nháp, cập nhật sổ nguồn, in lệnh `run` | cả hai |
| `crm-status` | Sổ nguồn + run mới nhất của từng tài liệu (chỉ đọc) | cả hai |

```powershell
..\.venv-ingest\Scripts\python.exe -m app.modules.doc_ingest.cli run --pdf "<file.pdf>" --pages 11,14,167-171 --doc-id f54 --profile qs_controller
.\venv\Scripts\python.exe -m app.modules.doc_ingest.cli run --raw-dir tests\doc_ingest\fixtures\docling\f54 --doc-id f54
```

Docling mất khoảng 6–19 giây mỗi trang, nên chọn trang khi thử.

## Pipeline

```text
[nguồn CRM, tùy chọn] crm-plan (so cây CRM ↔ sổ nguồn) → crm-fetch (tải PDF, sha256, manifest nháp)
PDF
 ├─ S0  đo trang (pypdfium2) → quyết định OCR theo trang (ocr_required)   raw/profile.json
 ├─ Parse  Docling theo từng trang (RapidOCR khi S0 yêu cầu)              raw/p{n}.docling.json
 ├─ Đo PDF  từ của text layer, bitmap + hash + nét vector                 raw/p{n}.words.json, objects.json
 └─ S1  chuẩn hóa deterministic (một Recorder: review_queue + normalization_log)
      T-20 khung chữ → T-17 header/footer (+ T-18 nhãn sát hình) → T-16 phân loại nhãn, mục lục
      → T-06 số trang in → T-07 section path
      Hình: T-09 screenshot → T-10 watermark → T-19 hình trùng → T-11 caption → T-14 crop
      Bảng: T-01…T-05, T-15 (+ T-12/T-13 trên ô bảng)
      T-08 list cha–con → T-12/T-13 trên text → V-01 độ phủ text
      → NormalizedElement                                                  normalized/*.jsonl, images/
      → báo cáo HTML, độ khớp profile                                      report/index.html, run_report.json
      → build: manifest + chunker + CQ-01…CQ-10 + kiểm 2b                  build/chunks.jsonl, doc_chunks_v1.jsonl,
                                                                           doc_chunks_v2.jsonl, chunk_quality.json,
                                                                           chunk_review.json, report/chunks.html
 ─ ─ ─ ─ ─ ─ ─ ─  ngoài doc_ingest (app/modules/chunking_loader)  ─ ─ ─ ─ ─ ─ ─ ─
      load_ingest_run: kiểm (model theo registry) → embed lá → ghi doc_chunks_v2 trong một transaction (D-009)
 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  chưa có (xem STATE.md)  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
      đánh giá tra cứu trên DB thật → trích fact → gán unit + duyệt
```

Bước hình chạy trước bước bảng: screenshot (T-09) không thành bảng rỗng, và caption gắn
lại (T-11) đổi điều kiện đóng bảng của T-03.

Module (`backend/app/modules/doc_ingest/`):

| Vùng | File | Vai trò |
|---|---|---|
| CLI, điều phối | `cli.py`, `pipeline.py` | Thứ tự bước, ghi thư mục run; trạng thái bước tính từ module có thật |
| Đo PDF | `parse/profile_probe.py`, `parse/pdf_probe.py`, `s0.py` | S0; bitmap, hash, nét vector; đối tượng trong Form XObject lấy bounds của form |
| Docling | `parse/docling_runner.py` | Parse theo trang, render trang và ảnh crop. `parse/` và `spike/` là nơi duy nhất import Docling, pypdfium2, PIL |
| Chuẩn hóa | `normalize/` (`docling_reader`, `pages`, `coverage`, `sections`, `figures`, `tables`, `lists`, `text_refs`, `elements`, `recorder`) | Luật T-xx, ghép `NormalizedElement` |
| Mã kỹ thuật | `technical_refs/params.py`, `applicability.py` | T-12 mã parameter, T-13 điều kiện áp dụng (ứng viên, chưa phải fact) |
| Kiểm | `validate/coverage.py` | V-01 độ phủ text so với text layer |
| Đánh giá | `eval/` | Độ khớp profile, chấm theo nhãn mẫu |
| Manifest | `manifest.py`, `manifests/*.yaml` | Thông tin cấp tài liệu cho chunk: doc_id, loại, model, scope, bucket |
| Chunk builder | `build/` (`loader`, `chunker`, `render`, `fields`, `assertions`, `quality`, `builder`) | Chia đơn vị, cửa sổ cha–con, gán trường, CQ-01…CQ-10, cổng 2b, chép verdict theo `content_hash` + `section_path` |
| Nguồn biên soạn | `curated/` (`schema`, `check`, `build`, `products/*.yaml`, `selection_matrix.yaml`) | Tài liệu pipeline trích lỗi cấu trúc (catalog): dữ liệu YAML có duyệt → chunk bám sát chữ PDF (contract C2 §15) |
| Xuất | `export/doc_chunks_v1.py` | `DraftChunk` → dòng bảng `doc_chunks` hiện tại (chỉ ghi file) |
| OCR nhãn hình | `parse/figure_ocr.py` | RapidOCR trên ảnh crop; nhãn chỉ vào `keywords`/`figure_labels` |
| Duyệt | `review/approval.py` | Lõi trạng thái unit, approval theo hash |
| Báo cáo | `report/html_report.py`, `report/chunks_report.py` | HTML tự chứa từng bước; trang duyệt chunk |
| Cấu hình | `profile.py`, `profiles/*.yaml`, `schemas/` | Profile `default`, `qs_controller`; schema Pydantic `extra="forbid"` |
| Spike P-1 | `spike/` | Công cụ đo ban đầu; kết luận ở [parsing_spike.md](../../reports/parsing_spike.md) |
| Nguồn CRM | `sources/crm/` (`crm.yaml`, `crm_sources.lock.json`, `tree`, `diff`, `lock`, `manifest_draft`, `commands`, `client`) | Đồng bộ tài liệu công khai trên CRM: chọn tài liệu, so phiên bản, tải PDF (stdlib `urllib`), manifest nháp |

## Contract

| Contract | Tài liệu |
|---|---|
| C1: `NormalizedElement`, `LogicalTable`, luật T-xx/V-xx, bố cục thư mục run | [p1_normalization_contract.md](../../reports/p1_normalization_contract.md) |
| C2: `NormalizedElement` → `DraftChunk` → cột `doc_chunks`, cha–con, kiểm 2b | [p2_chunk_contract.md](../../reports/p2_chunk_contract.md) |
| Golden test GT/CQ | [p1_golden_tests.md](../../reports/p1_golden_tests.md) |
| Sổ vấn đề I-xx/E-xx, quyết định D-xx | [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md) |
| Backlog BL-xx | [p1_implementation_backlog.md](../../reports/p1_implementation_backlog.md) |

Khi file này khác contract, contract thắng.

## Bất biến của luồng

- Luật T-xx chỉ dùng tín hiệu hình học/cấu trúc với sai số tương đối, không tham chiếu
  tài liệu cụ thể. Tri thức miền (mẫu mã, cụm từ điều kiện, từ khóa caption, registry
  model) nằm trong profile; profile `default` hoàn toàn chung.
- Lỗi chưa biết được bắt bằng S0 và V-xx, rồi thành mục review hoặc cờ; không thành dữ
  liệu sai im lặng. Duyệt bắt buộc theo mức rủi ro là yêu cầu cứng.
- Không xóa phần tử: phần tử bị loại được gắn cờ (`duplicate_image`, `watermark_candidate`…).
- Chữ trong hoặc sát hình chỉ là từ khóa của hình, không vào thân chunk hay fact.
- Thủ tục không tách theo từng bước; cửa sổ cha nối nguyên văn các con, tối đa 2.500 ký tự.
- ID bảng là định danh của một lần chạy; so giữa các lần chạy dùng content hash.
- Run mới dùng run id mới, không ghi đè run cũ. Sau mỗi lần sửa luật, kiểm hash 11 bảng
  F54, trang in và V-01 không đổi (số mốc: [LOG-archive-2026-11-09.md](LOG-archive-2026-11-09.md) mục 7).
- Đổi luật hoặc schema phải có bằng chứng từ run thật và người duyệt, ghi vào LOG và contract.

## Cấu hình

| Biến hoặc file | Tác dụng |
|---|---|
| `profiles/default.yaml`, `qs_controller.yaml` | Ngưỡng luật, `param_text_patterns`, lexicon, `chunking` |
| `profiles/registry_snapshot.json` | Bản chép registry chatbot; `tests/chatbot/test_registry_snapshot.py` kiểm khớp |
| `manifests/{doc}.yaml` | Bắt buộc để chạy `build` cho một tài liệu |
| `backend/requirements-ingest.txt` | Dependency của `.venv-ingest` (Docling, pypdfium2…) |

## Test và eval

Từ thư mục `backend`:

```powershell
..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest   # đủ, kể cả test cần Docling
.\venv\Scripts\python.exe -m pytest tests                        # test requires_docling tự skip
```

Test thuần chỉ đọc fixture JSON trong `tests/doc_ingest/fixtures/`, không cần PDF. Nhãn
mẫu cho `eval` và `build` nằm ở `fixtures/eval/*.labels.json`, `*.chunks.json`.

## Log runtime

Mỗi lần chạy ghi `data/ingest_runs/{doc_id}/{run_id}/` (gitignored): `raw/`, `normalized/`
(`elements.jsonl`, `tables.jsonl`, `review_queue.jsonl`, `normalization_log.jsonl`,
`validation.jsonl`), `build/`, `report/` và `run_report.json` (trạng thái bước, thời gian,
phiên bản tool). Mở `report/index.html` và `report/chunks.html` bằng trình duyệt.

## Ranh giới với luồng khác

- `doc_ingest` chỉ import `app.modules.doc_ingest.*`; phần còn lại của `app` không import
  `doc_ingest`. `tests/doc_ingest/test_import_boundary.py` kiểm cả hai chiều.
- `backend/.dockerignore` loại `doc_ingest` và `requirements-ingest.txt` khỏi image chat.
- Bảng `doc_chunks` do luồng website-qa đọc. Hiện bảng chứa chunk F86 biên soạn tay, nạp
  bằng `chunking_loader/load_csv.py`; migration schema là thay đổi riêng ở module chatbot.

## Quy trình nạp tài liệu mới

1. Chạy `run` với profile `default`, đọc mục "Độ khớp profile" trong báo cáo HTML.
2. Chọn hoặc tạo profile (dữ liệu YAML, không sửa code), chạy lại `run`.
3. Xử lý hàng review.
4. Loại tài liệu hoặc hãng mới: gán nhãn mẫu 8–15 trang, chạy `eval`.
5. Tài liệu đạt cổng mới sang `build`: thêm manifest, chạy `build` (và `figure-ocr` nếu có
   hình), gán nhãn ranh giới `{doc}.chunks.json`, team duyệt `chunks.html` và
   `chunk_review.json` (cổng 2b).

## Nạp tài liệu từ CRM (crm-sync)

Nguồn: `GET https://erp.qstcnc.com/api/v1/public/company-docs/website-tree` (không có `/` cuối). Quy ước
(Toma, 2026-11-19): khóa tài liệu là `id`; cây chỉ trả bản hiện hành; upload mới → `version` (dạng `"1.0"`,
chỉ nhánh "Bộ điều khiển") và mã file trong `file_url` đổi; CRM không có `sha256`. URL đã ký (`exp`, `sig`)
hết hạn theo ngày → **không lưu**, chỉ dùng lúc tải.

1. `crm-plan` → đọc `plan.md`. Chọn theo `crm.yaml`: nhánh "Bộ điều khiển" (`mode: build`) và
   "Catalogue & Hồ sơ" (`run_only`); model theo tiền tố tên tài liệu; mỗi (model, loại tài liệu) một bản,
   ưu tiên `en`. Luật so phiên bản ở `sources/crm/diff.py`; "bất thường" (thay file không tăng version,
   version giảm) không tự xử lý.
2. `crm-fetch --plan <dir>` → PDF (kiểm `%PDF` + `file_size`, ghi `sha256`), manifest nháp
   `manifests/<doc_id>.yaml` (có `source`), sổ nguồn `state=fetched`. Cập nhật phiên bản giữ các trường người
   đã điền (`exclude_*`, `scope_rules`, `note`).
3. Người kiểm manifest (TODO: `exclude_pages`…), rồi chạy lệnh `run` mà `crm-fetch` in ra (tài liệu `run_only`
   có `--no-build`). Từ đây theo "Quy trình nạp tài liệu mới" ở trên; làm giàu (enrich) chỉ sau khi duyệt
   nội dung trích xuất.
4. Chưa có (giai đoạn 2): nạp vào `doc_chunks_v2` theo sổ nguồn, gỡ phiên bản cũ khi bản mới được duyệt,
   chạy `crm-plan` theo lịch.
