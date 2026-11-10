# P-1 — Backlog triển khai

Nguồn:
- [p1_chunking_impact_assessment.md](p1_chunking_impact_assessment.md) (vấn đề I-xx/E-xx, HITL H-x, quyết định D-xx);
- [p1_normalization_contract.md](p1_normalization_contract.md) (T-xx);
- [p1_golden_tests.md](p1_golden_tests.md) (GT/CQ/RB).

## Tóm tắt quyết định

**C1 đã khóa (2026-11-03)**: D-01, D-02, D-03, D-04 (mô hình dữ liệu), D-08, D-11
đã chốt, chi tiết ở [assessment §6](p1_chunking_impact_assessment.md#6-quyết-định-đang-mở).
Contract rev 3 sửa T-01 (biên cột theo khe trắng).

**Rev 2 (pipeline chung)**: pipeline xử lý mọi PDF mà không biết trước lỗi.
Thêm S0 (BL-24), kiểm bất biến V-xx (BL-25), profile cấu hình (BL-26), gộp dòng
tiếp nối T-15 (BL-27). Spike F86 (BL-13) là ca kiểm tính chung đầu tiên.
Xem [contract §0](p1_normalization_contract.md#0-nguyên-tắc-pipeline-chung-rev-2).

| Hạng mục | Quyết định |
|---|---|
| Khóa contract C1 | **ĐÃ KHÓA (2026-11-03)** |
| S1/S2 (chuẩn hóa deterministic) | **GO** trong Ingestion V1, chạy với golden test, không ghi DB |
| Sinh baseline chunk (nháp) | **HOLD → GO** khi BL-05…BL-09, BL-11 đạt GT-01…GT-04, GT-07 (profile `default`), có BL-15, BL-24, BL-25, BL-27 và D-12 |
| Trích fact có cấu trúc (nháp) | **HOLD → GO** sau điều kiện trên + D-04, D-10 |
| Xuất bản unit / activation production | **HOLD**: phạm vi 3 (production integration) |

## Ba phạm vi

| Phạm vi | Task |
|---|---|
| 1. P-1 assessment | BL-00, BL-01 (xong trong bước này) |
| 2. Ingestion V1 | BL-02 … BL-22 |
| 3. Production integration | BL-90 … (chỉ liệt kê, chưa lên kế hoạch) |

Cột "Chặn": hạng mục không thể bắt đầu hoặc hoàn tất nếu task chưa xong.
- C1: contract artifact ingest.
- C2: DDL.
- P1: các lane triển khai đầu tiên của V1.
- Sinh chunk / Trích fact: theo nghĩa ở trên.
- Xuất bản: phạm vi 3.

## Phạm vi 1 — P-1 assessment

| ID | Việc | File | Phụ thuộc | Đầu ra | Nghiệm thu | Chặn |
|---|---|---|---|---|---|---|
| BL-00 | Đánh giá tác động, contract chuẩn hóa, golden test, backlog | `docs/ai/reports/p1_*.md` | spike F54 | 4 tài liệu | Số liệu kèm lệnh chỉ đọc; `git diff` chỉ có `docs/ai/reports/` | C1 |
| BL-01 | Sửa `parsing_spike.md` theo JSON thô (trang 168: cờ header gắn vào dòng dữ liệu, không phải header lặp; cell trống bị bỏ nhưng chỉ số cột đúng; list cha–con; bbox picture trang 9 hẹp hơn bitmap) | `docs/ai/reports/parsing_spike.md` | — | Báo cáo sửa | Mọi kết luận khớp JSON thô | C1 |

## Phạm vi 2 — Ingestion V1 (thứ tự ưu tiên)

### Nhóm A — Nền tảng kiểm chứng

Trạng thái 2026-11-02:
- **BL-02 xong**: fixture sinh bằng `doc_ingest/parse/make_fixture.py`, khoảng 0,6 MB, không cần gzip.
- **BL-03 xong**: `backend/tests/doc_ingest/test_f86_baseline.py`.
- Khung module độc lập đã có:
  - `doc_ingest/geometry.py` (thuần Python) và `doc_ingest/parse/` (nơi duy nhất cùng `spike/` được import docling/pypdfium2/PIL);
  - test ranh giới import;
  - marker `requires_docling`.
- Normalizer (Nhóm C) dùng lại `geometry.py`, đọc fixture JSON và không import Docling.

Trạng thái 2026-11-03 (sau khi khóa C1), chi tiết test ở
[p1_golden_tests.md §6](p1_golden_tests.md#6-bộ-test-theo-nhóm-quyết-định-c1-rev-3):
- **BL-14 xong** (contract rev 3, quyết định ghi ở assessment §6).
- **BL-04 một phần**: `schemas/normalized.py` (`LogicalTable`, `Applicability`,
  `ReviewItem`, `LogEntry`), `schemas/profile.py`, `schemas/review.py`,
  `technical_refs/params.py` (`ParamRef`). Chưa có `NormalizedElement` và schema
  `validation` (cần khi làm T-06…T-11, V-xx).
- **BL-26 xong**: `profile.py`, `profiles/default.yaml`, `profiles/qs_controller.yaml`.
- **BL-05, BL-06, BL-27 xong** cho bảng: `normalize/docling_reader.py`,
  `normalize/tables.py`, `normalize/recorder.py`.
- **BL-11 xong**: T-12/T-13 chạy trên cell của bảng logic
  (`technical_refs/params.py`, `technical_refs/applicability.py`) và trên text
  (`normalize/text_refs.py`, 2026-11-09).
- **BL-18, BL-20 xong phần lõi**: `review/approval.py` (máy trạng thái, luật phục
  vụ, approval gate, giữ approval theo hash, duyệt hàng loạt theo rủi ro, luật
  xuất bản theo phụ thuộc/conflict). Chưa có `review_events` lưu trữ và CLI (BL-21).
- **BL-29 xong**, **BL-31 xong**, **BL-32 xong** (CLI `run` + báo cáo HTML) (bảng dưới).
- **BL-07 xong** (trừ manifest ghi đè và `doc_version_mismatch`), **BL-08 xong** (trừ kiểm thứ tự số
  cho V-04): `normalize/pages.py` (T-17 xác nhận header/footer, T-06 trang in),
  `normalize/sections.py` (T-07), `normalize/elements.py` + schema `NormalizedElement`
  (BL-04 phần element), `normalized/elements.jsonl`. Sửa I-21; chữ trong hình → `figure_text`.
- **BL-24 xong** (S0: `parse/profile_probe.py`, `s0.py`, `raw/profile.json`, CLI `--ocr`,
  `ocr_required`, OCR RapidOCR backend torch theo trang); `empty_table` cho bảng 0 cell.
  Phát hiện: PDF F86 Operation Manual không có text layer (chữ vẽ bằng hình).
- **BL-02b xong**: `parse/pdf_probe.py::page_words`, `make_fixture --words-only`, 11 file
  `p{n}.words.json` (fixture tổng 915 KB). **BL-33 xong**. **BL-25 một phần**: V-01
  (`validate/coverage.py`, `validation.jsonl`, `text_coverage_gap`), ngưỡng tạm; V-02…V-04 và
  `confidence` chưa có.
- Sau khi khóa C1: ứng viên applicability tách khỏi fact (`Row.applicability_candidates`);
  `carry_over` giữ approval khi id bảng đổi bằng cách khớp duy nhất theo hash (HA-05b).
- `pydantic==2.14.2` được pin trong `requirements-ingest.txt` (đã có sẵn trong venv
  qua Docling, không cài gói mới).

| ID | Việc | File/module | Phụ thuộc | Đầu ra | Nghiệm thu | Chặn |
|---|---|---|---|---|---|---|
| BL-02 | Fixture golden F54 (rút gọn, README sha256) | `backend/tests/doc_ingest/fixtures/docling/f54/` | spike F54 | JSON + `bitmaps.json` + README | Test đọc fixture không cần Docling/PDF; tổng ≤ 3 MB | P1 |
| BL-02b | Bổ sung `p{n}.words.json` (token text layer + toạ độ) vào fixture | `doc_ingest/parse/make_fixture.py`, `parse/pdf_probe.py` | BL-02 | words.json 11 trang | Test V-01/V-02 chạy không cần PDF; tổng fixture ≤ 3 MB | V-01, V-02 |
| BL-03 | Khóa baseline F86 | `backend/tests/doc_ingest/test_f86_baseline.py` | — | test RB-01 | Fail khi CSV đổi | Xuất bản |
| BL-29 | Snapshot từ vựng registry (`product_models`, `aliases`, `control_interface`) cho profile + test đồng bộ (D-11, 11c) | `doc_ingest/profiles/registry_snapshot.json`, `tests/chatbot/test_registry_snapshot.py` | D-11 | snapshot | PI-07 fail khi registry đổi mà snapshot chưa sinh lại | P1 |
| BL-31 | Fixture tổng hợp (SYN) cho ca F54 không có: dòng xuống dòng, header nhiều tầng, bảng không header, nối trang lệch, cell lạc | `backend/tests/doc_ingest/synthetic.py` | BL-04 | builder `SynPage` | Các nhóm LT/HC/AP dùng được, không cần PDF | Sinh chunk |
| BL-33 | Phân loại nhãn Docling (T-16): mục lục `document_index` giữ nguyên, nhãn chưa hỗ trợ → `unsupported_element`; reader đọc con của mọi phần tử (caption) | `normalize/coverage.py`, `normalize/docling_reader.py` | BL-05 | `ElementCoverage` | Không phần tử body nào bị bỏ im lặng (`test_coverage.py`) | Sinh chunk |
| BL-34 | Đánh giá đa tài liệu — **có code 2026-11-09, nhãn chưa xác nhận**: báo cáo độ khớp profile (B1, tín hiệu cảnh báo), bộ nhãn tay mẫu (B2), lệnh `eval` chấm precision/recall tách trang text layer / OCR (B3), cổng đạt (B4) | `eval/profile_fit.py`, `eval/labels.py`, `eval/score.py`, `eval/render.py`, `tests/doc_ingest/fixtures/eval/*.labels.json` | BL-09, BL-11 | `RunReport.profile_fit`, `report/eval.json`, `report/eval.html` | F54 đạt (tạm); F86 Installation đạt (tạm); F10T, F86 Operation không đạt (OCR) | Dùng tài liệu mới cho BL-16 |
| BL-32 | CLI `run` (PDF hoặc Docling JSON đã lưu → chuẩn hóa → thư mục chạy contract §1) + báo cáo HTML từng bước | `doc_ingest/cli.py`, `pipeline.py`, `report/html_report.py`, `parse/docling_runner.py`, `schemas/run.py` | BL-05, BL-06 | `data/ingest_runs/{doc_id}/{run_id}/`, `report/index.html` | `test_run_report.py`; chạy Docling thật trùng kết quả fixture | — |
| BL-15 | Thư viện chunk assertion CQ-01…CQ-08 — **có code 2026-11-09**: CQ-01…CQ-10 + CQ-RB (contract C2 §10), chạy trong bước `build` | `backend/app/modules/doc_ingest/build/assertions.py` | BL-04 | `build/chunk_quality.json` | Đạt trên F54 (323 chunk) và F86 Installation (26 chunk); chưa chạy trên CSV F86 (RB-02: CSV không có `element_ids`, `row_ids`) | Sinh chunk |

### Nhóm B — Contract (C1 đã khóa 2026-11-03)

| ID | Việc | File/module | Phụ thuộc | Đầu ra | Nghiệm thu | Chặn |
|---|---|---|---|---|---|---|
| BL-14 | Cập nhật contract C1/C2: `param_*` (D-01), `LogicalTable` ref, `applicability`, list parent, `content_layer`, `lang`, knowledge unit | Plan + `docs/ai/` | D-02, D-03, D-04, D-08, D-11 | Contract đã review | Một vòng review; không mâu thuẫn giữa contract, DDL và runtime | **C1, C2** |
| BL-04 | Schema `NormalizedElement`, `LogicalTable`, `ParamRef`, log, review_queue, `validation`, `Profile` | `doc_ingest/schemas/normalized.py`, `schemas/profile.py`, `technical_refs/params.py` (chỉ model) | BL-14 | Pydantic `extra="forbid"` | Validate được ví dụ trong contract | P1 |
| BL-26 | Profile cấu hình: loader + profile `default` + `qs_controller` (dữ liệu, không code) | `doc_ingest/profiles/*.yaml`, `doc_ingest/profile.py` | BL-04, D-11 | `Profile` | Mọi luật đọc profile qua interface; GT-23 | P1 |

### Nhóm C — Chuẩn hóa deterministic (S1)

| ID | Việc | File/module | Phụ thuộc | Đầu ra | Nghiệm thu | Chặn |
|---|---|---|---|---|---|---|
| BL-24 | S0 hồ sơ tài liệu: text layer, chất lượng text, xoay, bitmap/vector, page labels, lang, bitmap lặp → `profile.json` + cấu hình Docling theo trang | `doc_ingest/parse/profile_probe.py` (dùng lại `pdf_probe.py`) | BL-04 | `profile.json` | F54: mọi trang có text layer, không trang xoay, watermark lặp 11/11; trang scan tổng hợp → `ocr_required` | Sinh chunk |
| BL-07 | T-06 trang in (`/PageLabels` → chuỗi furniture → manifest ghi đè) + đọc version ở header (cờ `doc_version_mismatch`) | `doc_ingest/normalize/pages.py` | BL-04 | `printed_page` | GT-11 (`source = furniture_sequence`, không cần regex manifest) | C1 (xác nhận field) |
| BL-08 | T-07 section path + label heading | `normalize/sections.py` | BL-04 | `section_path` | GT-12, GT-08 | Sinh chunk |
| BL-05 | T-01, T-02: TableGrid theo bbox, lấp ô trống | `normalize/tables.py` | BL-04, BL-02 | `LogicalTable` (1 segment) | GT-01, GT-18 | Sinh chunk |
| BL-06 | T-03, T-04, T-05: nối trang (sai số tương đối), kế thừa header, nhận header theo tín hiệu (trùng header / hình dạng token / mẫu profile) | `normalize/tables.py` | BL-05, BL-08, BL-26 | `LogicalTable` nhiều segment | GT-02, GT-03, GT-19 | Sinh chunk |
| BL-27 | T-15 gộp dòng tiếp nối + `orphan_row` | `normalize/tables.py` | BL-05 | dòng logic đã gộp | GT-22 (fixture tổng hợp) | Sinh chunk |
| BL-09 | T-08 list cha–con — **xong v1 2026-11-09** (kiểm trên F54; xem lại khi thêm tài liệu) | `normalize/lists.py` | BL-04 | `list_info` (`ListInfo`), review `list_orphan`, `list_level_ambiguous`, cờ `list_cross_page`, `list_marker_mixed`, `RunReport.lists`, mục List trong báo cáo HTML | GT-07 đạt; F54: 103 con, 0 mồ côi, 3 mơ hồ (trang 71) | Trích fact |
| BL-10 | T-09, T-10, T-11, T-14: screenshot, watermark candidate, caption, crop (+ T-18 nhãn sát hình) — **xong 2026-11-03** | `normalize/figures.py`, `parse/pdf_probe.py::page_objects` | BL-04 | `image`, `caption_link`, `raw/p{n}.objects.json`, `normalized/images/` | GT-05 (watermark), GT-06, GT-10 đạt. Chưa làm: render trang xoay. Liên quan, không thuộc BL-10: chép kích thước từ bản vẽ khi duyệt = fact `spec` `human_verified_figure` (V1.1); trả ảnh cùng câu trả lời = BL-92 (SSE `assets`) | Sinh chunk (hình) |
| BL-11 | T-12, T-13: `parse_param_ref` + kiểm giao mã + applicability — **xong** (ô bảng 2026-11-03; text 2026-11-09) | `technical_refs/params.py` (`find_param_refs`), `normalize/text_refs.py` | BL-04 | `ParamRef`, `TextParamRef` (vị trí + vai trò), `applicability`, `list_param_mismatch` (T-08 v1.1), `RunReport.refs` | GT-04, GT-05; F54 text phủ 302/302 token | Trích fact |
| BL-23 | Quyết định deterministic toàn pipeline | `normalize/__init__.py` | BL-05…BL-11 | — | GT-17 | Sinh chunk |
| BL-25 | Kiểm bất biến V-01…V-04 + `confidence` | `doc_ingest/validate/` | BL-02b, BL-05…BL-11, D-12 | `validation.jsonl`, mục review_queue | GT-20, GT-21, GT-22 | Sinh chunk |
| BL-13 | Spike F86 (PDF đã có trong `docs/ai/doc_ingest_spike/source/`) — ca kiểm tính chung đầu tiên: khi S1 có, chạy luật rút từ F54 lên F86 **không sửa luật**, ghi các ca không đạt | tool spike | PDF F86 | Báo cáo F86, checklist như F54, danh sách ca luật F54 không xử lý được | Người duyệt ký | S1 phần hình (D-07); D-12 |

### Nhóm D — Build và trích (nháp, chưa xuất bản)

| ID | Việc | File/module | Phụ thuộc | Đầu ra | Nghiệm thu | Chặn |
|---|---|---|---|---|---|---|
| BL-16 | Chunk builder baseline (deterministic, không LLM) — **có code 2026-11-09, chờ duyệt cổng 2b**: khối label heading, thủ tục nguyên khối (gộp chuỗi "Stage n:"), nhóm parameter kèm giá trị, bảng theo nhóm dòng lặp header, chunk hình = caption/tiêu đề + ảnh, cửa sổ cha ≤ 2.500 ký tự, manifest tài liệu, adapter `doc_chunks_v1`, kiểm 2b (độ phủ, ranh giới theo nhãn, so với CSV tay, duyệt tay), lệnh `build`, `figure-ocr` | `doc_ingest/build/`, `doc_ingest/export/`, `doc_ingest/manifest.py`, `manifests/*.yaml`, `report/chunks_report.py`, `parse/figure_ocr.py` | BL-05…BL-11, BL-15, BL-23, BL-25, BL-27 | `build/chunks.jsonl`, `doc_chunks_v1.jsonl`, `chunk_quality.json`, `chunk_review.json`, `report/chunks.html` | F54: CQ đạt, độ phủ 1,0, ranh giới P/R 1,0 (nhãn nháp); F86 Installation: CQ đạt, độ phủ 1,0, P/R 1,0, đúng loại 0,71; cổng 2b chờ team duyệt | Bước 3 (làm giàu tiếng Việt) |
| BL-17 | Trích fact nháp: `parameter` (bảng + text), `io_address`, connector→chức năng | `doc_ingest/enrich/` | BL-09, BL-11, D-04, D-10 | `facts` nháp + evidence verbatim | Evidence `table_cell`/`text_span` khớp nguyên văn; I-19 có cờ | — |
| BL-12 | Quality gate (document: nguồn + version; unit: cờ blocking) | `doc_ingest/review/gate.py` | BL-04 | `gate_report` | Trên F54: document `blocked` vì D-05 chưa xác nhận; unit có cờ thì `pending_review` | Xuất bản |

### Nhóm E — HITL

| ID | Việc | File/module | Phụ thuộc | Đầu ra | Nghiệm thu | Chặn |
|---|---|---|---|---|---|---|
| BL-18 | Knowledge unit + state machine + review_events + conflict_group (theo pattern `learning_ai/review/lifecycle.py`, viết riêng, không import chéo) | `doc_ingest/review/` | D-08, BL-14 | Model + transition | GT-13 | Xuất bản |
| BL-19 | Gán unit + `risk_tier` trong builder | `doc_ingest/build/` | BL-16, BL-18 | `unit_id` trên chunk/fact/asset | Mọi chunk/fact thuộc đúng 1 unit; GT-14 | Xuất bản |
| BL-20 | Giữ approval theo hash khi chạy lại | `doc_ingest/review/` | BL-18 | — | GT-15 | Xuất bản |
| BL-21 | CLI `review export / import / validate` có `--reviewer` + audit | `doc_ingest/cli.py` | BL-18 | Gói CSV review | Import từ chối khi thiếu reviewer, sai trạng thái hoặc còn cờ blocking; GT-16 | Xuất bản |
| BL-22 | Gói xuất bản đã duyệt + báo cáo coverage dạng text | `doc_ingest/build/package_writer.py` | BL-19, BL-21 | `approved/{doc_id}/` | Validate theo contract; `publish` dry-run trên Postgres local/test | Phạm vi 3 |

**Nghiệm thu Ingestion V1**:
1. Toàn bộ trang spike F54 qua pipeline mà không có lỗi P0 nào chưa bị gắn cờ.
2. GT-01…GT-18 và CQ-01…CQ-08 đạt.
3. Một vòng review thật trên F54 sinh được gói xuất bản: mọi fact có evidence
   verbatim, mọi chunk có provenance, conflict được giữ lại.
4. Chạy lại không đổi nội dung → giữ approval.
5. Không file runtime chatbot nào bị đổi.
6. Tính chung: F86 chạy qua S0 → T-xx → V-xx với profile `default` mà không sửa
   luật; mọi chỗ luật không xử lý được đều ra mục review_queue, không ra dữ liệu
   sai im lặng (đối chiếu bằng tay trên mẫu trang F86).

**Để sau V1 (không làm trong V1)**:
- `enhanced` embed_text bằng LLM (V1.1, sau eval);
- VLM caption, OCR trong hình (V2);
- fallback sơ đồ vector (V1.1, sau BL-13);
- fact `pinout` (chờ PDF F86);
- fact `spec` từ hình (`human_verified_figure`, V1.1);
- tag device/wiring cho asset (V1.1);
- review UI/API (V2, cần auth admin);
- dashboard coverage (V1.1).

## Phạm vi 3 — Production integration (chỉ liệt kê)

| ID | Việc | Phụ thuộc |
|---|---|---|
| BL-90 | SQL: `documents`, `knowledge_units`, `review_events`, `conflict_groups`, `technical_facts` (D-01), `doc_assets`; sửa `doc_chunks` (embedding nullable + CHECK `active_has_embedding`, `unit_id`) | BL-14, V1 đạt |
| BL-91 | Loader staging: version document + `publish_unit` (H-3, H-4, H-5); nạp `parent_id` từ `parent_key` (E-01) | BL-90 |
| BL-92 | Runtime B1–B4: entity 2 tầng, repository/ACL, lookup facts/assets, compose `<facts>`, SSE `assets`, widget | BL-91 |
| BL-93 | Eval C0 trên staging; so với baseline F86 (RB-03) | BL-91 |
| BL-94 | Activation production | BL-92, BL-93, D-05, D-09 |
