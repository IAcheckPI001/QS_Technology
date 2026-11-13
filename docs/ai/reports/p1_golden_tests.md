# P-1 — Đặc tả golden test và chunk assertion

Đặc tả cho Ingestion V1. Mọi khẳng định dưới đây đã được đối chiếu với JSON
Docling thô và ảnh trang của spike F54 ([parsing_spike.md](parsing_spike.md)),
không suy từ báo cáo.

Trạng thái (2026-11-03): fixture F54 (BL-02) đã có; bộ test theo 5 nhóm quyết
định C1 (§6) chạy trên fixture F54 + fixture tổng hợp. Trạng thái từng GT/CQ ở
§6.6; test cần bước chưa có code ghi rõ "chờ BL-xx", không có stub.

Contract được kiểm:
- [p1_normalization_contract.md](p1_normalization_contract.md) (T-01…T-14,
  ParamRef D-01);
- mô hình HITL ở [assessment §4](p1_chunking_impact_assessment.md#4-quality-gate-tài-liệu-theo-document-và-knowledge-unit).

## 1. Fixture (BL-02, làm ở V1)

| Mục | Quy định |
|---|---|
| Nguồn | Docling JSON thô của 11 trang spike (9, 11, 14, 18, 19, 40, 167–171), sinh bằng `doc_ingest.spike.run_spike` với cấu hình ghi trong `parsing_spike.md` |
| Vị trí | `backend/tests/doc_ingest/fixtures/docling/f54/p{n}.docling.json` |
| Kích thước | Tổng JSON thô ≈ 6,7 MB (riêng p011 ≈ 2 MB). Trước khi commit, chỉ giữ các trường T-01…T-14 dùng (`texts`, `tables`, `pictures`, `groups`, `body`, `furniture`, `pages[].size`) và bỏ dữ liệu không dùng, có test kiểm bản rút gọn cho cùng kết quả normalize. Nếu vẫn > 3 MB thì nén gzip |
| Bitmap | Bounds bitmap nhúng (T-09, T-10, T-14) lấy từ PDF lúc chạy spike, lưu kèm `p{n}.bitmaps.json`; test **không** cần PDF |
| Text layer | Token text layer kèm toạ độ cho V-01/V-02, lưu `p{n}.words.json` (BL-02b, đã sinh cho 11 trang bằng `make_fixture --words-only`) |
| README | sha256 PDF (`7cd0e69c…1bce21`), version Docling/docling-core/pypdfium2, lệnh sinh lại |
| PDF | Không commit (đã gitignore) |

Test chạy trong venv backend, không import Docling: chỉ đọc JSON fixture.

## 2. Golden test lớp chuẩn hóa

| ID | Trang | Khẳng định | Biến đổi |
|---|---|---|---|
| GT-01 | 11 | Bảng 2 cột, header `Port \| Functions`; cột 0 của 10 dòng dữ liệu là `CN1`…`CN10` theo thứ tự; dòng `CN3` có cột 1 = `MPG Handle`; flag `column_order_repaired`; caption `Figure 5. F54 controller I/O ports` thuộc **picture**, không thuộc bảng | T-01, T-11 |
| GT-02 | 167 → 168 → 169 t0 | **Một** `LogicalTable` gồm 3 segment, 4 cột (`Parameter`, `Description`, `Work range`, `Default`); `#4140 - #4147` là dòng dữ liệu (`is_header=false`, log T-05); dòng `#12160 - #12167` có Work range = `""` và Default = `"0"`; dòng `#12200 - #12207` (169 t0) có Work range = `""` và Default = `"0"` (không phải Work range = "0"); mọi dòng đủ 4 cell; không mất dòng nào so với nguồn (167: 21 dòng dữ liệu, 168: 32, 169 t0: 17) | T-01…T-05 |
| GT-03 | 169 t1 → 170 t0; 170 t1 → 171 t0 | Nối đúng 2 bảng logic; header kế thừa; dòng `#4136` (LCD sleep) có Work range = `""`, Default = `"15"`; dòng `#8050, #8052 …` (170 t0) thuộc bảng 5.2 Spindle | T-03, T-04 |
| GT-04 | 168, 169 | `#8030, #8032 #8034, #8036` → `list`, codes `[8030, 8032, 8034, 8036]`, `range_*` = null; tra `#8033` khớp dòng `#8031, #8033 #8035, #8037`, **không** khớp dòng `#8030 …`; `#0000 - #0007` → `range`, codes 0…7; `#3` và `#0003` khớp cùng dòng; `M1920` không khớp `#1920`; trong mỗi bảng logic, codes giữa các dòng không giao | T-12 |
| GT-05 | 171 | `#0136` có `applicability.status = not_available`, note chứa `F54`; `#4132`, `#4133`, `#4134` có `status = conditional` ("touch controller"); picture logo cuối bảng → `watermark_candidate` (không bị xóa) | T-13, T-10 |
| GT-06 | 18 | Figure 15 → `screenshot` có caption `Figure 15. Homing sensor status configuration parameters…`; Figure 14 → `picture` có caption; không còn bảng 0×0 nào | T-09, T-11 |
| GT-07 | 19 | 4 list_item cha `M1920:`…`M1923:`, mỗi cha đúng 2 con (`= 0`, `= 1`); con trỏ `parent_element_id` đúng cha; `text` của con M1921 giữ nguyên `(NC` thiếu `)` | T-08 |
| GT-08 | 14 | Bảng X40–X57: 16 dòng dữ liệu + header `Add \| Name \| Function`; `label_heading` của bảng = `Input devices connection address table on F54 controller`; list "DO NOT connect both high-level and low-level…" có `normalized_type = warning`, `section_path` kết thúc bằng `2.3.1 Sensor Input wiring` | T-07, phân loại warning |
| GT-09 | 40 | Bảng Y40–Y45 (6 dòng dữ liệu); cell cột Function có `lang = vi`, cột Name `lang = en`; 3 list_item dưới `Note:` là `warning`, cùng section với Figure 45 | T-07, lang |
| GT-10 | 9 | Vùng crop original chứa trọn bounds bitmap của bản vẽ (x 54,8–561,7; y 96,0–454,5 pt) cộng padding, kẹp trong trang; caption `Figure 3. F54 controller dimension drawing`; **không** có text số đo nào trong `text` của element (số đo chỉ có trong bitmap) | T-14 |
| GT-11 | tất cả | `printed_page.value`: 9→`2`, 11→`4`, 14→`7`, 18→`11`, 19→`12`, 40→`33`, 167→`160`, 168→`161`, 169→`162`, 170→`163`, 171→`164`; `source = furniture_sequence` (không cần regex trong manifest); header/footer có `content_layer = furniture` | T-06 |
| GT-12 | 167–169, 18, 19 | Mọi dòng của bảng logic 5.1 có `section_path` kết thúc bằng `5.1 Axis parameters` (mang từ 167 sang trang không có heading); bảng 169 t1 có `5.2 Spindle parameters`; `Note:` / `Notes:` / `Parameter stauts description:` là `label_heading`, không vào `section_path` | T-07 |
| GT-17 | 167–171 | Biến đổi là deterministic: chạy normalize hai lần trên cùng fixture cho `elements.jsonl`, `tables.jsonl`, `normalization_log.jsonl` giống hệt (so sha256) | tất cả |
| GT-18 | 167–171 | Không mất provenance: mọi cell không rỗng có `raw_cell_ref` trỏ tới đúng một cell Docling; mọi cell Docling xuất hiện đúng một lần trong `LogicalTable` | T-01, T-02 |

### Pipeline chung (rev 2)

GT-01…GT-12 phải đạt với profile `default`. Ca nào cần profile miền thì ghi rõ
trong test. V-01/V-02 cần token text layer kèm toạ độ, nên fixture bổ sung
`p{n}.words.json` do `make_fixture` sinh từ PDF (BL-02b); test vẫn không cần PDF.

| ID | Trang | Khẳng định | Biến đổi / kiểm |
|---|---|---|---|
| GT-19 | 168 | Với profile `default` (không có `code_patterns`), `#4140 - #4147` vẫn thành dòng dữ liệu nhờ hình dạng token `#9 - #9` trùng các dòng dữ liệu cột 0 của 167; log T-05 ghi bước (b) | T-05 |
| GT-20 | tất cả | V-01: trên Docling output đã chuẩn hóa, độ phủ token ≥ ngưỡng ở mọi trang. Xóa giả lập một element text khỏi fixture trang 14 → `text_coverage_gap` blocking cho trang 14 | V-01 |
| GT-21 | 11, 169 | V-02: chạy trên lưới Docling **thô** (bỏ qua T-01/T-04) → `table_crosscheck_mismatch` ở bảng trang 11 và bảng nối trang 169 t0; sau T-01/T-04 → đạt | V-02 |
| GT-22 | tổng hợp | Fixture tổng hợp có dòng mô tả xuống dòng (cột khóa rỗng): T-15 gộp vào dòng trên; khoảng cách dọc vượt ngưỡng → `orphan_row`. V-03: cột trộn hình dạng token → `column_type_inconsistent` | T-15, V-03 |
| GT-23 | — | Không luật T-xx nào chứa hằng số riêng của tài liệu hay miền: quét mã nguồn `doc_ingest/normalize/` không có `doc_id`, tên file, tên model, regex mã (`#\d`, `M\d{4}`…); các giá trị này chỉ có trong profile | §0, §9 |

## 3. Golden test HITL (V1, sau khi có knowledge unit)

| ID | Khẳng định |
|---|---|
| GT-13 | Unit bảng logic 5.1 (167–169) không chuyển được `approved` khi còn mục review_queue blocking (vd. đặt giả lập `column_count_mismatch`) |
| GT-14 | Unit sơ đồ output CN5 (trang 40, Figure 45) không xuất bản được khi unit warning "…connect the output signal to an intermediate relay…" chưa `approved` |
| GT-15 | Chạy lại pipeline không đổi nội dung → unit đã `approved` giữ nguyên; đổi một ô (vd. Default của `#8010` trên fixture sửa tay) → unit về `pending_review` |
| GT-16 | Conflict F86 (port table vs Figure 2.1, `source_note` của baseline) được biểu diễn bằng một `conflict_group` giữ **cả hai** bên ở `conflict`; không bên nào xuất bản được |

## 4. Chunk assertion (CQ)

Chạy trên chunk do builder V1 sinh ra. Với baseline F86 chỉ chạy ở chế độ **báo
cáo**, không fail, không sửa file.

| ID | Khẳng định | Cách kiểm |
|---|---|---|
| CQ-01 | Chunk bảng có dòng header khớp `columns` của bảng logic; mọi dòng có đúng `len(columns)` ô | Parse lại content bảng của chunk, so với `tables.jsonl` |
| CQ-02 | Không cắt giữa một dòng; mã, mô tả, work range, default nằm trên cùng một dòng | Mọi `row_id` của bảng xuất hiện trọn vẹn trong đúng một chunk |
| CQ-03 | `content` ≤ 2500 ký tự (dưới giới hạn 3000 của `answer_composer.py:96`); chunk dài hơn phải chia theo ranh giới dòng và lặp header | Đo độ dài; kiểm header ở mọi phần |
| CQ-04 | Chunk warning có `related_chunk_keys` không rỗng, trỏ tới chunk tồn tại cùng `section_path` | Resolve key |
| CQ-05 | Provenance đủ: `doc_id`, `pdf_page_index` start/end, `printed_page`, `element_ids`; fact có ≥ 1 evidence verbatim | Kiểm null; với `text_span` / `table_cell` so chuỗi |
| CQ-06 | Mọi asset ref resolve được; không asset nào có `normalized_type ∈ {watermark_candidate}`; visual chunk có caption hoặc title nguyên văn | Resolve + kiểm loại |
| CQ-07 | Không chunk/fact nào có `applicability.status = not_available` được render thành câu khẳng định "có trên {model}" | Kiểm template render |
| CQ-08 | `parent_key` của mọi chunk resolve được; không chu trình | Đồ thị cha–con |

## 5. Regression baseline F86

| ID | Khẳng định |
|---|---|
| RB-01 | `sha256(backend/app/modules/chunking_loader/documents/doc_chunks_f86.csv) == a8629f5878fc1d4f16c2706d7b0440a46fe9ecfe098e0b7ec525f16c878f02aa`. Test fail nếu file bị sửa; muốn đổi baseline phải đổi hash có chủ đích trong cùng commit |
| RB-02 | Chạy CQ-01…CQ-08 ở chế độ báo cáo trên 92 chunk; lưu kết quả làm mốc. Kỳ vọng đã biết: CQ-08 **đạt** về dữ liệu (42 `parent_key` resolve đủ), nhưng DB không có `parent_id` (E-01); 7 chunk có `embed_text` > 600 token; 146 asset đều là ảnh cả trang |
| RB-03 | Bộ eval retrieval C0 (khi tới phạm vi 3) chạy trên baseline trước, để có mốc so sánh với chunk V1 |

## 6. Bộ test theo nhóm quyết định C1 (rev 3)

Mỗi nhóm kiểm một quyết định đã chốt. Nguồn dữ liệu: **F54** = fixture golden 11
trang; **SYN** = fixture tổng hợp sinh bằng `backend/tests/doc_ingest/synthetic.py`
(dạng DoclingDocument JSON, bbox phần tử BOTTOMLEFT, cell TOPLEFT) cho các ca F54
không có. Cột "Trạng thái": **đạt** = có test và đang pass; **chờ BL-xx** = cần
bước chưa có code.

Chạy (thư mục `backend`): `.\venv\Scripts\python.exe -m pytest tests\doc_ingest`
hoặc `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest`. Không test
nào trong 5 nhóm cần Docling hay PDF.

### 6.1 LogicalTable integrity (D-02) — `test_logical_table.py`

| ID | Dữ liệu | Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|---|---|
| LT-01 | F54, mọi bảng | Mỗi dòng đúng `len(columns)` ô; ô trống `text=""`, `raw_cell_ref=null`, `empty_fill` | 100% dòng | đạt |
| LT-02 | SYN (gộp T-15 + cell lạc) | Cell nguồn = `raw_cell_ref` ∪ `merged_cell_refs` ∪ `unassigned_cells`, ba tập rời nhau | Cân bằng tuyệt đối | đạt |
| LT-03 | F54 | `logical_table_id` dạng `{doc_id}:t\d{3}`, liên tiếp, theo (trang, y) | Không trùng, đúng thứ tự | đạt |
| LT-04 | SYN | `row_id` giữ sau T-15 (`r0, r1, r3`), `merged_row_ids=[r2]`, log T-15 | Đúng | đạt |
| LT-05 | F54 | Segment trên trang liên tiếp; không segment nào thuộc 2 bảng | 100% | đạt |
| LT-06 | F54 169 + SYN | Không nối qua heading (5.1 kết thúc ở 169 t0, 5.2 là bảng mới); bảng không header lệch biên → `ambiguous_continuation` | Không nối sai | đạt |
| LT-07 | SYN | 2 dòng header → `"Group / Key"`…, `complex_header` chặn chunk của đúng bảng đó | Chặn đúng phạm vi | đạt |
| LT-08 | SYN | Cell có tâm ngoài bbox bảng → `unassigned_cells` (`outside_columns`) + `unassigned_cell` blocking | Cell còn nguyên | đạt |
| LT-09 | F54 | `LogicalTable` round-trip JSON; field lạ bị từ chối | 100% | đạt |
| LT-T01 | SYN | Cell tràn qua khe trắng → biên dự phòng theo header + `column_count_mismatch` | Đúng cột, có cờ | đạt |
| LT-10 | Chunk/fact nháp | Mọi tham chiếu `(logical_table_id, row_id)` resolve được | 0 tham chiếu hỏng | chờ BL-16, BL-17 |
| LT-11 | F54 | V-02 đạt trên mọi bảng đã chuẩn hóa | 100% bảng | chờ BL-02b, BL-25 |

Kèm GT-01 (trừ phần caption T-11), GT-02, GT-03, GT-17 (phần bảng), GT-18: đạt.
Trên F54 với `default` không có mục review cấu trúc nào (`unassigned_cell`,
`column_count_mismatch`, `ambiguous_continuation`, `header_demotion_unsure`,
`orphan_row`, `complex_header`).

### 6.2 Header classification (D-03) — `test_header_classification.py`

| ID | Dữ liệu | Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|---|---|
| HC-01 | SYN | Header lặp ở segment nối trang → `repeated_header`, log bước a, không review | Đúng | đạt |
| HC-02 | F54 168, `default` | `#4140 - #4147` thành dữ liệu ở bước b (= GT-19) | Log bước b | đạt |
| HC-03 | SYN (2 dòng dữ liệu) | Dưới 3 dòng: `qs_controller` → bước c; `default` → bước d, giữ cờ header, `header_demotion_unsure` | Đúng theo profile | đạt |
| HC-04 | SYN | Bước d chỉ chặn chunk bảng của nó; bảng khác không có review | Đúng phạm vi | đạt |
| HC-05 | SYN | Hình dạng 3/5 = 60% → dữ liệu; 2/4 = 50% → review | Đúng tại biên | đạt |
| HC-06 | F54 11, 14, 40 | Header thật không bị hạ; 0 `header_demotion_unsure` trên F54 | 0 lần hạ nhầm | đạt |
| HC-07 | F54 | Cờ `header_inherited` ở t004 seg 1–2, t005 seg 1, t006 seg 1 | 4/4 | đạt |
| HC-08 | SYN | Bảng không header: `header_text=null`, `header_source=none`, `header_missing` chặn fact | Không bịa header | đạt |
| HC-09 | SYN | T-03: số cột Docling lớn hơn → `ambiguous_continuation`; heading chen giữa → bảng mới, không review; header khác nhưng thẳng hàng → nối + `header_demotion_unsure` (không im lặng) | 3/3 ca (ca lệch biên ở LT-06) | đạt |
| HC-10 | F54 167–171 × 1,5 | Phóng to tọa độ: nội dung bảng, cờ, review không đổi | Giống hệt | đạt |

### 6.3 Applicability (D-04) — `test_applicability.py`

Lớp chuẩn hóa chỉ sinh **ứng viên** (`Row.applicability_candidates`, `ApplicabilityCandidate`);
fact và `Applicability` của fact thuộc BL-17. AP-01…AP-07 kiểm ứng viên.

| ID | Dữ liệu | Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|---|---|
| AP-01 | Schema + F54 | `status` ngoài enum / field lạ bị từ chối; `models` ⊆ registry, `interfaces` ⊆ `control_interface` | 100% | đạt |
| AP-02 | F54 171 `#0136` | `not_available`, `models=[F54]`, `condition_text="F54 controller"`, `note` là chuỗi con của cell | Khớp tuyệt đối | đạt |
| AP-03 | F54 171 `#4132`–`#4134` | `conditional`, `models=[]`, `interfaces=[]`, `condition_text="touch controller"`, `applicability_note` + `applicability_model_unmatched` (chặn fact) | 3/3 | đạt |
| AP-04 | F54, `qs_controller` | Mọi dòng dữ liệu bảng parameter có `param_ref`; 7 dòng mang applicability vẫn còn | Không mất dòng | đạt |
| AP-05 | SYN (chuỗi) | EN + VI + alias (`Astro 6AV` → `6AV`) + nhiều model; interface `EtherCAT` → `ethercat` | 5/5 | đạt |
| AP-06 | SYN | `Not available on Z99` → `models=[]`, cờ unmatched | Fact giữ, có cờ | đạt |
| AP-07 | SYN | "available memory", "available options", "Unavailable on", "available once" không sinh applicability | 0 dương tính giả | đạt |
| AP-08 | DB test | Chunk `not_available` cho F54 vẫn có `F54` trong `product_models`; `match_doc_chunks(p_models=['F54'])` trả về | Truy xuất được | chờ BL-16, phạm vi 3 |
| AP-09 | Template trả lời | Fact `not_available` không bao giờ thành câu "có trên {model}" (CQ-07) | 0 câu sai | chờ BL-16, runtime |
| AP-10 | S3 (LLM) | `note` do LLM trích là chuỗi con nguyên văn của evidence | 100% | chờ BL-17 |

Kèm GT-04 (`qs_controller`: list/range/single, `#8033` chỉ khớp đúng dòng, `#3` =
`#0003`, `M1920` ≠ `#1920`, không giao mã trong bảng, mẫu không parse được,
`range_too_long`) và GT-05 phần applicability: đạt. Với `default` không dòng nào
có `param_ref`.

### 6.4 Approval / HITL (D-08) — `test_approval.py`

| ID | Dữ liệu | Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|---|---|
| HA-01 | Unit test | Mọi cặp (trạng thái, trạng thái): chỉ cặp khai báo trong `TRANSITIONS` chuyển được | 25/25 cặp | đạt |
| HA-02 | Unit test | Chỉ (`active`, `approved`) được phục vụ | 1/15 ô | đạt |
| HA-03 | F54 167–169 | Mục blocking chặn duyệt (= GT-13); khớp id con, không khớp tiền tố lẫn (`t004` ≠ `t0041`) | Đúng | đạt |
| HA-04 | SYN unit | Wiring phụ thuộc warning chưa duyệt → không xuất bản | Đúng | đạt (unit giả lập; gán unit thật chờ BL-19) |
| HA-05 | F54 167–169 | Chạy lại không đổi → giữ approval; sửa Default của `#8010` → `pending_review`; unit khác không ảnh hưởng (= GT-15) | Chỉ unit đổi mất approval | đạt |
| HA-05b | F54 + SYN | Thêm một bảng phía trước làm id bảng 5.1 đổi `t001` → `t002`: vẫn `approved` (`matched_by` hash); hai unit cùng nội dung tranh một bản ghi → cả hai `pending_review` (`ambiguous`); khác `unit_type` → không khớp | Đúng | đạt |
| HA-06 | SYN unit | Conflict group: không bên nào xuất bản | Đúng | đạt (dữ liệu F86 GT-16 chờ BL-13) |
| HA-07 | SYN unit | Duyệt hàng loạt theo section: unit `parameter` và unit có cờ → `high_risk`; còn blocking → từ chối; ngoài section không đụng | 0 unit rủi ro cao lọt | đạt |
| HA-08 | SYN unit | Chỉ unit `approved` của document `active` xuất bản được | Đúng | đạt |
| HA-09 | Unit test | Duyệt cần reviewer có tên (rỗng, khoảng trắng, `system:*` bị từ chối); bản ghi có reviewer, thời điểm, hai hash | 100% | đạt (CLI `--reviewer` chờ BL-21) |
| HA-10 | F54 | Admin sửa = annotation có ký tên, bản gốc giữ, chunk sửa cần embed lại | — | chờ BL-21 |
| HA-11 | DB test | Publish chỉ ghi unit đã duyệt, có `unit_id`, không đụng unit khác | — | chờ BL-22, phạm vi 3 |
| HA-12 | Embedder giả | Publish lại không đổi → 0 lời gọi embed; đổi 1 chunk → 1 | — | chờ BL-22 |

### 6.5 Profile isolation (D-11) — `test_profile_isolation.py`, `tests/chatbot/test_registry_snapshot.py`

| ID | Dữ liệu | Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|---|---|
| PI-01 | Profile YAML | `default`, `qs_controller` nạp được (kế thừa lexicon, thresholds); key lạ bị từ chối; `extends` vòng bị từ chối | 100% | đạt |
| PI-02 | `default` | `code_patterns`, `param_prefixes` rỗng; lexicon không chứa tên model | Đúng | đạt |
| PI-03 | F54 | Mọi GT/nhóm trên chạy với `default`, trừ GT-04/AP-04 khai báo `qs_controller` | Đúng | đạt |
| PI-04 | Mã nguồn | GT-23: chuỗi trong code (trừ docstring) của `normalize/`, `technical_refs/`, `review/`, `schemas/` không có tên model, `f54_om`, "touch controller", regex mã; không luật nào import `yaml` hay đọc `profiles/`. Đã thử chèn `"F54"` và `r"^#\d"` → test fail | 0 vi phạm | đạt |
| PI-05 | F54 | `default` ↔ `qs_controller`: chỉ `param_ref` và cờ `param_table` khác; review giống hệt | Diff đúng phạm vi | đạt |
| PI-06 | F54 167–169 | Thêm từ khóa caption vào profile → `profile_hash` đổi, unit bảng giữ approval | Giữ approval | đạt |
| PI-07 | Venv chính | `registry_snapshot.json` = `product_models`, `aliases`, `control_interface` của `REGISTRY` | Khớp tuyệt đối | đạt |
| PI-08 | F54 | Đổi `doc_id` → output giống hệt trừ định danh | Diff = 0 | đạt |
| PI-09 | F86 | Luật F54 + `default` trên F86 không sửa code: không crash, LT-01/LT-02 đạt, bất thường thành cờ | 3 điều kiện | chờ BL-13 |

### 6.6 CLI `run` + báo cáo HTML (BL-32) — `test_run_report.py`

| Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|
| `run --raw-dir` fixture F54 sinh đúng bố cục contract §1; jsonl validate bằng schema; `run_report.json` có `profile_hash`, trạng thái bước = `step_states()` | Đủ file, validate 100% | đạt |
| Trạng thái bước lấy từ module có thật (S1 bảng `implemented`; T-12/T-13, review `partial`; S0, V-xx, build, fact, publish `not_implemented`) | Đúng | đạt |
| HTML: đủ 6 bảng; ô `#4140 - #4147` ghi T-05; `#0136` là "ứng viên T-13 · not_available · … · chưa phải fact · chờ duyệt"; mục Fact "chưa triển khai (BL-17)"; V-xx "chưa triển khai" | Đúng | đạt |
| Tập trang con `168-169` → bảng 5.1 gắn nhãn "có thể bị cắt" (trang 167 không được chọn); `167-169` → bảng liền 3 segment | Đúng | đạt |
| Chạy hai lần → `normalized/*` giống hệt từng byte (GT-17) | Giống hệt | đạt |
| Text tài liệu chứa `<script>` → escape trong HTML | Không có thẻ thô | đạt |
| Chạy Docling thật (`--pdf` F54, trang 11, 14, 167–171) cho `tables.jsonl` cùng content hash, cell, cờ, review với `--raw-dir` trên fixture | Kiểm tay 2026-11-03: trùng hoàn toàn | kiểm tay (PDF không commit) |

### 6.7 Lưới an toàn: nhãn Docling + V-01 (BL-33, BL-25 phần V-01) — `test_coverage.py`

| Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|
| GT-20 phần 1: V-01 trên 11 trang fixture F54 (có `words.json`) | Mọi trang đạt, không `text_coverage_gap` | đạt |
| GT-20 phần 2: xóa text một list_item trang 14 | `text_coverage_gap` blocking chunk cho đúng `f54:p014`, có mẫu token thiếu | đạt |
| Caption được đọc như con của picture/table (`Figure 5. F54 controller I/O ports` trang 11) | Có trong phần tử | đạt |
| SYN `document_index` → T-16: giữ 4 cell, không thành bảng logic, log T-16, V-01 tính nội dung | Đúng | đạt |
| SYN I-37: tiêu đề "CONTENT" + dòng có chấm dẫn và số trang nằm ngoài `document_index` → cả hai `toc`, phần tử sau không mang nhãn "CONTENT"; tiêu đề không đứng trước mục lục giữ là label heading | Đúng | đạt |
| SYN nhãn `formula` → `unsupported_element` (blocking chunk) và V-01 không tính → `text_coverage_gap` | Không bỏ im lặng | đạt |
| SYN phần tử nhân đôi → `duplicate_ratio=0.5`, không đạt | Đúng | đạt |
| Từ trong header/footer không tính | `page_tokens` chỉ gồm thân trang | đạt |
| Trang không có từ text layer → `passed=null`, không review; không có words → không chạy | Đúng | đạt |
| `item_id` review liên tục qua các bước (nhãn, bảng, V-01) | `rq-0001…` không trùng | đạt |
| `page_words` từ PDF = `p014.words.json` của fixture | Giống hệt | đạt ở `.venv-ingest` (skip khi không có pypdfium2/PDF) |
| `validation.jsonl` deterministic; báo cáo HTML có V-01 theo trang, mục lục, nhãn lạ; raw không có words → "V-01 không chạy" | Đúng | đạt (`test_run_report.py`) |

### 6.8 S0 hồ sơ tài liệu + OCR (BL-24) — `test_s0.py`

| Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|
| `decide`: 0 / 19 ký tự → `missing`, OCR; 20 → `ok`; ký tự lỗi 20% → `poor`, OCR; ngưỡng đọc từ profile | 5/5 | đạt |
| `--ocr auto/off/force` chọn đúng trang OCR; `docling_config` ghi cấu hình thực tế | Đúng | đạt |
| Trang không có text layer → `ocr_required` blocking chunk; V-01 `passed=null` lý do "OCR page" | Đúng | đạt |
| `--ocr off` vẫn gắn `ocr_required` (nội dung thiếu) | Đúng | đạt |
| Trang F54 có text layer → không `ocr_required`, V-01 đạt | Đúng | đạt |
| Bảng Docling 0 cell (F54 trang 18) → `empty_table` không blocking | Đúng | đạt |
| `raw/profile.json` round-trip; báo cáo có bảng S0, cảnh báo "cả tài liệu được vẽ bằng hình", badge OCR | Đúng | đạt (`test_run_report.py`) |
| `measure_pages` trên PDF thật: F54 trang 14 `ok`, F86 trang 5 `missing` (0 ký tự) | Đúng | đạt ở `.venv-ingest` (skip khi thiếu PDF) |
| F86 trang 1–17 chạy `--ocr auto` | Kiểm tay 2026-11-03: 17/17 trang OCR, 235 s; caption Figure 1-1…2-11 và heading có; vấn đề I-21…I-23 | kiểm tay |

### 6.9 T-17 header/footer, T-06 trang in, T-07 section — `test_furniture.py`, `test_printed_page.py`, `test_sections.py`

| Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|
| Footer lặp 3 trang → furniture `furniture_repeated`, không review; `PAGE3`/`PAGE 4` cùng khóa `page #` | Đúng | đạt |
| Dòng gộp `ACME CO.,LTD PAGE 4` → `furniture_composed` | Đúng | đạt |
| `page_header` duy nhất `1.1 APPERANCE` → body `heading` + `furniture_reclassified` (không chặn); phần tử sau có section path | Đúng | đạt |
| `page_header` duy nhất `320 mm` → furniture + `furniture_unconfirmed` (không chặn) | Đúng | đạt |
| `text` lặp ở dải dưới 3 trang → furniture + `furniture_promoted`; `section_header` lặp ("Notes:") → không | Đúng | đạt |
| Con của picture (`page_header` logo, `section_header` rác) → `figure_text`, `parent_element_id` = picture, không làm heading | Đúng | đạt |
| `furniture_patterns` của profile bắt đoạn 2 trang (luật lặp không áp dụng) | Đúng | đạt |
| T-06: chuỗi `PAGE n`; `PAGEO` → `null` không nội suy; số lệch chuỗi → `null` + `printed_page_conflict`; < 3 trang → `null`; số cố định (`Rev 2`) không phải số trang; /PageLabels ưu tiên | Đúng | đạt |
| T-06 F54 (`Page \| N`): trang 9 → "2", 167 → "160"; F86 OCR trang 5–17 → 3…15 (kể cả footer gộp trang 6, 11) | Đúng | đạt |
| T-07: `parse_heading` (số nhiều đoạn, từ khóa, số dính chữ, `320 mm` yếu, `Notes:` không phải heading); cấp theo tiền tố số, mang qua trang, `label_heading`, `section_parent_missing`, `section_path_source` | Đúng | đạt |
| F54 trang 167–169: `PART 5 …` › `5.1 …`; bảng trang 168 có section path và `table_ref` | Đúng | đạt |
| F86 OCR (fixture `f86_ocr`, trang 5–17): 5 heading I-21 thành heading, `2.1 POWER SUPPLY` nằm dưới `CHAPTER 2.`; > 300 `figure_text` | Đúng | đạt |
| Hồi quy F54: content hash 6 bảng không đổi, review không đổi, V-01 11/11 | Đúng | đạt (kiểm tay + `test_run_report.py`) |

### 6.10 Hình: T-18, T-14, T-09, T-10, T-11 (BL-10) — `test_figures.py`

| Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|
| T-18: `page_header` `320 mm` cách hình 3 pt ở dải trên → `figure_text` của hình, không `furniture_unconfirmed`; `text` đè mép hình → `figure_text`; nhãn giữa hai hình → hình gần hơn | Đúng | đạt |
| T-18 không gắn: câu văn, heading đánh số, `Notes:`, caption, chữ cách hình 40 pt, dòng bắt đầu ở lề trái văn bản (I-25, F54 `INDEX homing type`); chuỗi lặp 3 trang sát hình vẫn là furniture | Đúng | đạt |
| T-14: crop mở rộng theo bitmap ≥ 50%, nét vector kéo ra ≤ 36 pt, nhãn của hình; khung trang không mở rộng; không có `objects.json` → bbox + padding, log `no_object_info` | Đúng | đạt |
| T-09: bảng 0 cell phủ bitmap → `screenshot` có caption, không `empty_table`, không vào bảng logic; không có bitmap → `empty_table` | Đúng | đạt |
| T-10: picture nằm trong bitmap lặp 3 trang (IoU 0,53, phủ 100%) → `watermark_candidate`; có caption → `watermark_conflict`; hình thật lớn hơn watermark → giữ; bitmap 2 trang → không; watermark xác định bằng cùng `hash` + cùng vị trí (I-24): ảnh cùng nội dung ở vị trí khác → picture + cờ `repeated_image`; screenshot cùng khung px/cỡ/vị trí nhưng khác nội dung → không cờ; `objects.json` thiếu `hash` → T-10 không chạy | Đúng | đạt |
| T-11: `Figure 5` gắn bảng → chuyển sang hình phía trên (`caption_relinked`, `source = rule`); dải hình lề phải cùng hàng caption không phải đích; caption không có parent được gắn; không ứng viên → `caption_ambiguous`; hòa giữa picture và screenshot trùng vùng → giữ liên kết Docling; `Table 3` → bảng gần nhất | Đúng | đạt |
| F54 (có `objects.json`): GT-10 crop trang 9 phủ bitmap 54,8–561,7; GT-01/I-10 Figure 5 trang 11; GT-06 Figure 15 trang 18 → screenshot; GT-05 trang 171 → watermark; V-01 11/11; hash bảng không đổi khi có/không có `objects.json` | Đúng | đạt |
| F86 OCR: `320 mm` trang 8, 9 → `figure_text` đúng hình; chỉ 2 caption gắn lại (trang 17, Docling không gắn) | Đúng | đạt |
| F86 trang 5–17 qua CLI (PDF + fixture `f86_ocr`): logo trang 9, 10, 13, 14, 15 → picture + `repeated_image` (không phải watermark); 7 nhãn T-18; 0 `watermark_conflict`, 0 `caption_ambiguous`; crop trang 8, 9 chứa `320 mm` | Đúng | đạt (kiểm tay, `data/ingest_runs/f86/fix-i24-26`) |
| F54 171 trang qua CLI (PDF + raw run `20261103-144432`): 8 `watermark_candidate` đều là watermark thật; 7 screenshot trở lại picture; `watermark_conflict` 1; `caption_ambiguous` 1 (trang 38, Docling gộp hai hình); `PART 1:CONTROLLER OVERVIEW` là heading; hash 11 bảng và trang in không đổi; V-01 168/0/3 | Đúng | đạt (kiểm tay, `data/ingest_runs/f54/fix-i24-26`) |
| Render (venv ingest + PDF F54): `normalized/images/f54_p009_e003/original.png`, `preview.png`, scale 3–4 | Đúng | đạt (tự skip khi thiếu PDF) |
| T-19: picture + bảng 0 cell cùng bbox, caption Docling ở bảng → giữ screenshot, picture `duplicate_image` + `duplicate_of`, không crop; không caption → giữ screenshot; chồng một phần (IoU ≈ 0,33) → hai hình | Đúng | đạt |
| F54 171 trang (run `fix-i27`): 5 cặp trùng trang 64, 81, 85, 96, 98 → mỗi trang một ảnh; ảnh render 247 → 242; caption, review, hash bảng, trang in, V-01 không đổi; F86 trang 5–17 không có cặp trùng | Đúng | đạt (kiểm tay) |
| Ảnh ở Form XObject (F54 trang 18) lấy bounds form (141,492–500,695), không phải góc 0,720 | Đúng | đạt (`test_f54_fixture.py`) |

### 6.12 List cha–con: T-08 v1 (BL-09) — `test_lists.py`

| Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|
| GT-07 (fixture F54 trang 19): 4 cha `M1920:`…`M1923:` × 2 con `o … = 0/1`, `depth` 1, `marker` `o`; text con M1921 giữ `(NC` thiếu `)`; không review | Đúng | đạt |
| Thụt ≥ 18 pt không glyph → con; thụt 10 pt có glyph → con; anh em cùng lề không glyph (`a)`, `b)`) cùng cha; ba cấp (`depth` 2); list cấp 1 thụt khác (x 121) sau label heading không có cha | Đúng | đạt |
| `operation` (không có khoảng trắng sau `o`) không phải glyph → `list_level_ambiguous` khi thụt 10 pt | Đúng | đạt |
| `text` hoặc label heading chen giữa ngắt khối: mục thụt sâu không glyph → cấp 1, không review; mục có glyph → `list_orphan`, anh em của nó `list_level_ambiguous`, lùi về lề cấp 1 không review | Đúng | đạt |
| Qua trang (có/không furniture đầu trang) → cha ở trang trước, cờ `list_cross_page`; trang trước kết thúc bằng text → không nối, `list_orphan`; hai trang không liền nhau → không nối | Đúng | đạt |
| Tài liệu lộn xộn: `- ` dùng cho cấp 1 → không thành con, không review; lùi lề về x không khớp cấp nào → `list_level_ambiguous`; anh em khác marker → `list_marker_mixed`; marker Docling dùng khi text không có glyph | Đúng | đạt |
| F54 171 trang (run `bl09-t08`: raw run `20261109-063902` + PDF): 482 list_item, 103 con, 0 mồ côi, 2 `list_cross_page` (trang 67), 3 `list_level_ambiguous` (trang 71); review 21 → 24; hash 11 bảng, trang in, V-01, hình, 242 ảnh crop không đổi | Đúng | đạt (kiểm tay) |
| F86 trang 5–17 (run `bl09-t08`): 7 list_item, 0 con, review không đổi | Đúng | đạt (kiểm tay) |

### 6.13 Mã parameter, ghi chú áp dụng trong text: T-12/T-13 + T-08 v1.1 (BL-11 phần text) — `test_text_refs.py`

| Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|
| Đơn, danh sách `(#12010, #12011, …)`, dải `#4140 - #4147`, dải xuống dòng `#8090\n- #8097`; `text[start:end] == label` | Đúng | đạt |
| Vai trò: `M1920: …` định nghĩa; `o M1920 = 0`, `o #4141= 0` giá trị; trong câu → nhắc tới | Đúng | đạt |
| `and` tách danh sách; khác prefix → ref riêng | Đúng | đạt |
| Không phải parameter (near-miss): `M100`, `M8`, `M100H3`, `M195..` (lỗi đánh máy F54 trang 94), `M4` | Đúng | đạt |
| Dải ngược, trộn dải với danh sách → `param_unparseable`; dải > 64 → `range_too_long` | Đúng | đạt |
| Profile `default` không quét; chữ trong hình không quét; heading, text, list có ref | Đúng | đạt |
| T-13 trên text: `not available on F54 controller` → ứng viên `not_available` + `applicability_note` | Đúng | đạt |
| T-08 v1.1: cha `M1951:`, con `o M1950 = 0/1` → 2 `list_param_mismatch`; cùng mã → không review | Đúng | đạt |
| Fixture F54 trang 19: 4 định nghĩa, 8 giá trị, không mismatch | Đúng | đạt |
| F54 171 trang (run `bl11-text`): 227 ref ở 220 phần tử (98/75/54), phủ 302/302 token `#` 4–5 và `M` 4 chữ số; 0 unparseable; near-miss 9; `list_param_mismatch` 2 (trang 96, lỗi soạn thảo của tài liệu); review 24 → 26; hash bảng, trang in, V-01, hình, list không đổi | Đúng | đạt (kiểm tay) |
| F86 trang 5–17 (run `bl11-text`): 0 ref, review không đổi | Đúng | đạt (kiểm tay) |

### 6.14 Đánh giá đa tài liệu (BL-34) — `test_eval.py`

| Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|
| B1: `code_shape` (`#4140` → `#9`, `P01-02` → `P9-9`); profile `default` + 25 mã → `default_profile_with_codes`, `unknown_code_shapes`; `qs_controller` nhận `#`, `P01-01` vẫn là dạng lạ; 6 near-miss → `near_miss_high` | Đúng | đạt |
| B1: picture ≥ 50% trang chứa ≥ 2 câu văn → `picture_swallows_text`; nhãn sơ đồ ngắn không cảnh báo; fixture F54 không có tín hiệu OCR | Đúng | đạt |
| B3: chấm TP/FP/FN (M0100 là FP), vai trò, cha list, cụm áp dụng, nội dung thân; vai trò sai và cha sai có trong chi tiết; nhãn chưa xác nhận → `provisional` | Đúng | đạt |
| B4: cổng = tỷ lệ trang OCR ≤ 0,5 + trên trang text layer: T-12 precision ≥ 0,99, recall ≥ 0,95, vai trò ≥ 0,95, T-08 cha sai = 0, T-13 recall = 1, nội dung thân ≥ 0,95 | Đúng | đạt |
| 4 file nhãn hợp lệ, `verified: false` | Đúng | đạt |
| Chạy thật (run `eval-b`, nhãn **tạm**): F54 13 trang: T-12 67/0/0, vai trò 1,0, list 26/0/0, T-13 4/4, nội dung 3/3 → **đạt**. F86 Installation 4 trang: 0 mã bịa, nội dung 4/4 → **đạt**. F86 Operation (13/13 trang OCR) → **không đạt** (OCR). F10T (101/105 trang OCR): trang OCR T-12 precision 0,5 (M0100 ×3, I-30), nội dung thân 0/4 (I-28, I-29) → **không đạt** | Đúng như mong đợi | đạt (kiểm tay) |

### 6.15 Chunk builder (BL-16) + kiểm 2b (BL-15) — `test_chunker.py`, `test_chunk_quality.py`

| Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|
| Manifest: 3 file nạp được, `doc_version` là chuỗi, tìm theo `run_doc_ids` | Đúng | đạt |
| Parameter: định nghĩa + giá trị con cùng chunk, list lồng, scope thêm `configuration`, mã vào `keywords`; nhóm tách theo ranh giới định nghĩa ≤ 1.200 ký tự (CQ-10 đạt) | Đúng | đạt |
| Chuỗi "Stage n:" + khối dẫn → 1 `procedure` (kèm ảnh); ghi chú "The cause is…" → `alarm` liên kết hai chiều, scope thêm `maintenance` | Đúng | đạt |
| Thủ tục > 2.500 ký tự tách ở ranh giới bước, phần 2…n có tiêu đề `(phần i/n, bước a–b)`, không mất/lặp bước | Đúng | đạt |
| Chunk hình: caption + tiêu đề, ảnh, nhãn hình lọc vào `keywords`; furniture, `figure_text`, ảnh trùng không vào chunk; mục chỉ có heading không sinh chunk | Đúng | đạt |
| I-37: heading + hình không caption gộp vào khối bước sau (1 `procedure`, ảnh vào `assets`); cuối mục thì vào khối trước; mục chỉ có heading + hình vẫn ra chunk hình; trước bảng không gộp | Đúng | đạt |
| R-04: heading + dòng dẫn kết thúc bằng ":" ngay trước bảng thành dòng dẫn của bảng; câu thường thì không | Đúng | đạt |
| R-02: khối thủ tục không nhãn ("Step 1:" là text) nối với các khối bước sau thành 1 `procedure`; nhãn "Step 1:" + một dòng "Step 2: …" là `procedure`, một bước đơn lẻ thì không | Đúng | đạt |
| I-38: bảng 70 dòng chia theo ngân sách token của `embed_text` (800 − 150), mỗi dòng đúng một lần, mọi phần lặp tiêu đề `(phần i/n)` + header, số dòng các phần lệch ≤ 2, không phần nào `embed_truncated`; bảng ngắn giữ một chunk | Đúng | đạt |
| I-38: dòng nhóm không đứng cuối phần, phần bắt đầu giữa nhóm lặp dòng nhóm dưới header (không tính vào `row_ids`); một dòng dài hơn ngân sách thành phần riêng, CQ-11 không tính lỗi | Đúng | đạt (dữ liệu tổng hợp; F54/F86 chưa có bảng có dòng nhóm) |
| Cửa sổ cha: `content` = nối nguyên văn các con, assets = hợp ảnh con | Đúng | đạt |
| Review cấp trang (`ocr_required`) chặn chunk trên trang đó; `extraction = ocr` | Đúng | đạt |
| `control_interface`/`spec_attributes` từ từ vựng registry + profile | Đúng | đạt |
| Nhãn OCR ảnh crop → `figure_labels` (`crop_ocr`) + `keywords`, không vào `content`; trang OCR toàn trang không OCR lại | Đúng | đạt |
| Fixture F54 qua `cli run`: CQ đạt, độ phủ 1,0, adapter không lỗi ràng buộc, `run_report.chunks`, `chunks.html`; trang 19 parameter M1920–M1923; bảng parameter chia phần lặp header, mỗi dòng đúng 1 lần | Đúng | đạt |
| CQ-01/02/03/06/08/09/10/11 bắt được vi phạm cố ý (CQ-11: chunk bảng nhiều dòng có `embed_truncated`) | Đúng | đạt |
| Ranh giới theo nhãn (precision/recall/loại), so với CSV tay, tổng hợp duyệt (ok/fix/cũ), cổng 2b, adapter `doc_chunks_v1` đúng cột + ràng buộc | Đúng | đạt |
| Chạy thật (nhãn **tạm**): F54 323 chunk (62 cha), CQ đạt, độ phủ 1,0, ranh giới P 1,0 / R 1,0 / đúng loại 0,9 (10 đơn vị, 5 trang); F86 Installation 26 chunk, CQ đạt, độ phủ 1,0, P/R 1,0, đúng loại 0,71; so với 27 chunk tay: 7/27 có ≥ 60% token trong một chunk builder | Báo cáo | đạt (kiểm tay), cổng 2b chờ team duyệt |

### 6.16 T-20 khung chữ (I-36) + chép verdict khi build lại — `test_text_frames.py`

| Kiểm | Điều kiện đạt | Trạng thái |
|---|---|---|
| Khung "Instructions" trên trang text layer: `Step 1:`, câu, caption "Step 2: …" về text thân theo thứ tự đọc, `parent_element_id = null`, cờ `frame_text_released`; picture cờ `text_frame`; tiêu đề khung ("Instructions", "Model: F54") vẫn `figure_text` | Đúng | đạt |
| Khung ảnh chỉ có "Description images / Model: …" giữ `figure_text`; caption "Figure 9. …" trong khung giữ là caption | Đúng | đạt |
| Sơ đồ có heading bị nuốt + mảnh "(" ")" (F54 trang 50) và ảnh chụp có caption bước + mảnh chữ (F54 trang 95): không phải khung | Đúng | đạt |
| Trang OCR hoặc không có S0: không trả chữ | Đúng | đạt |
| I-37, nhãn khung không được gom: "Instructions" + "Model: F54" ngoài picture → `figure_text` của picture trên trang, cờ `frame_label_attached`, bước sau giữ nhãn "Step 1:"; "Instructions:" + danh sách, trang OCR, trang không có picture: không đổi | Đúng | đạt |
| I-37: "Model: F54 controller" ngay trên picture hoặc bảng 0 cell → `figure_text` của hình đó, hình không mở khối nhãn mới; câu bắt đầu bằng "Model:" không đứng trên hình giữ là `text` | Đúng | đạt |
| `carry_review`: khớp theo `content_hash` + `section_path` khi key dịch; chunk mới/đổi nội dung/đổi mục → `pending`; mục cũ stale hoặc `pending` không chép | Đúng | đạt |
| Chạy thật F54 `eval-c` (2026-11-11): 342 chunk (70 cha), đúng 13 mục đổi so với `eval-b`, mọi mục có đủ Step; CQ-01…CQ-10 đạt, độ phủ 1,0, ranh giới P/R 1,0; BL-34 đạt; `figure_text` loại trừ 518 → 449; chép 306/342 verdict. F86 Installation/Operation, F10T: 0 khung | Báo cáo | đạt (kiểm tay) |
| Chạy thật F54 `eval-d` (2026-11-11, I-37): 296 chunk (54 cha), 36 mục đổi so với `eval-c`, 34/34 chunk `fix` của I-37 không còn; CQ-01…CQ-10 đạt, độ phủ 1,0, ranh giới P/R 1,0; BL-34 đạt; `figure_text` loại trừ 449 → 500, `toc` 5 → 7; chép 230/296 verdict. Hồi quy (`eval-c-regress`): F86 Installation 26 → 21 chunk (4 mục đổi: bìa, mục lục, 2.5, 2.6), CQ và ranh giới đạt; F86 Operation 0 chunk đổi; F10T chỉ đổi tiêu đề "CONTENT" → `toc` | Báo cáo | đạt (kiểm tay); mục 4.4.3 xấu đi (I-42) |
| Chạy thật F54 `eval-e` (2026-11-11, I-38, build bằng venv chính có tiktoken): 300 chunk; chỉ 3 mục PART 5 đổi so với `eval-d`; bảng 5.1 → 5 phần, 5.2 → 2, 5.3 → 2, mọi phần ≤ 584 token, mỗi dòng đúng một lần; 0 chunk `embed_truncated`; CQ-01…CQ-11 đạt, độ phủ 1,0, ranh giới P/R 1,0, BL-34 đạt; chép 291/300 verdict. Hồi quy (`eval-d-regress`): F86 Installation 21 → 23 chunk (bảng cổng 3 → 6 phần), F86 Operation 0 chunk đổi | Báo cáo | đạt (kiểm tay) |
| I-39 (R-12): khối dài có "Case n"/"Example n" chỉ chia ở đầu phần; phần 2…n lặp `(phần i/n)` + phần dẫn; ảnh đi cùng Case; Case một mình quá dài → chia theo phần tử, không trộn với Case khác, cờ `block_part_oversize`; không có đầu phần → chia như cũ; glyph Private Use đầu dòng → `- ` | Đúng | đạt (`test_chunker.py`) |
| Chạy thật F54 `eval-f` (2026-11-12, I-39, venv chính): 301 chunk (55 cha); chỉ mục 2.6.4.7 đổi so với `eval-e`: B0116/B0117 → 2 phần (551, 410 token), Case 3 cùng kết luận, phần 2 lặp công thức, 0 glyph ``; phần 1 cùng ghi chú mục thành cửa sổ cha mới; CQ-01…CQ-11 đạt, độ phủ 1,0, ranh giới P/R 1,0, BL-34 đạt; chép 298/301 verdict. Hồi quy (`eval-f-regress`): F86 Installation, F86 Operation 0 chunk đổi | Báo cáo | đạt (kiểm tay) |
| I-40a (T-07): hình + caption nằm trên heading đầu trang nhưng xếp sau → lên trước phần tử đầu tiên nằm dưới nó, thuộc mục trước, cờ `reading_order_fixed`; trang OCR, hình khác cột, có phần tử giữa nằm trên heading: không đổi | Đúng | đạt (`test_sections.py`) |
| I-42 (R-02): "Step 1" sau "Step 2" mở thủ tục mới; câu dẫn + sơ đồ trang sau đi theo thủ tục mới; khối tiêu đề + sơ đồ + câu dẫn gộp vào thủ tục đầu | Đúng | đạt (`test_chunker.py`) |
| I-40b: nhãn OCR crop vào `keywords` khi có trong từ vựng tài liệu hoặc khớp `figure_label_trusted_patterns`; nhãn khác `verified = false`, không vào `embed_text` | Đúng | đạt (`test_chunker.py`) |
| Chạy thật F54 `eval-g` (2026-11-12, I-40a/b, I-42; chuẩn hóa lại từ raw `eval-f`, build venv chính): 301 chunk; chỉ 2.4.3, 2.4.4, 4.4.3 đổi nội dung; 45 chunk đổi từ khóa; Figure 52 về 2.4.3; 4.4.3 thành 2 thủ tục; CQ-01…CQ-11 đạt, độ phủ 1,0, ranh giới P/R 1,0, BL-34 đạt; chép 295/301 verdict. Hồi quy (`eval-g-regress`): F86 Installation, F86 Operation 0 chunk đổi, 0 hình bị dời | Báo cáo | đạt (kiểm tay) |
| I-43 (D-008, CQ-12): chunk cha dài không mang `embed_truncated`/`embed_over_budget`; chunk lá vượt 800 − 150 mang `embed_over_budget`; CQ-12: phần bảng nhiều dòng vượt → không đạt, lá khác → ghi chú, cha không tính | Đúng | đạt (`test_chunk_quality.py`) |
| Chạy thật F54 `eval-h` (2026-11-13, I-43, chỉ build từ `normalized` của `eval-g`, venv chính): 301 chunk, 0 nội dung đổi, chỉ cha B0036 bỏ cờ `embed_truncated`; 0 chunk lá vượt ngân sách; CQ-01…CQ-12 đạt, độ phủ 1,0, ranh giới P/R 1,0; chép 301/301 verdict, cổng 2b đạt (tạm). Hồi quy (`eval-h-regress`): F86 Installation, F86 Operation 0 đổi | Báo cáo | đạt (kiểm tay) |
| Manifest `exclude_pages`/`exclude_sections` → phần tử lý do `manifest_excluded`, không vào chunk, độ phủ không thiếu; khung chữ `text_frame` không là asset, khối chỉ có khung không thành chunk hình (I-44); T-20 nhận khung "Instructions" chỉ còn caption bước, ảnh chụp có caption bước mà không có tiêu đề khung giữ nguyên; nhãn OCR chỉ vào từ khóa chunk wiring/pinout/dimension; ghi chú ngắn sau hình gộp vào chunk hình, ghi chú dài tách (I-45) | Đúng | đạt (`test_chunker.py`, `test_text_frames.py`) |
| Chạy thật F54 `eval-j` (2026-11-13; chuẩn hóa lại từ raw `eval-i`, build venv chính, carry + chép `enrichment.jsonl`): 296 chunk (trước 301); B0000 (trang 1–2) loại theo manifest (9 phần tử); 2.2 và 2.4.1 gộp ghi chú vào chunk hình; asset lá 234 → 208; 74 lá đổi từ khóa (bỏ nhãn OCR khỏi chunk không phải wiring/pinout/dimension); CQ-01…CQ-12, độ phủ 1,0, ranh giới P/R 1,0; chép 294/296 verdict. Hồi quy (`eval-j-regress`): F86 0 chunk/asset đổi, 1 + 5 chunk đổi từ khóa | Báo cáo | đạt (kiểm tay) |

### 6.11 Trạng thái GT/CQ hiện có

| ID | Trạng thái |
|---|---|
| GT-01 | Đạt (bảng; caption `Figure 5` thuộc picture qua T-11) |
| GT-02, GT-03, GT-18, GT-19 | Đạt |
| GT-04 | Đạt (profile `qs_controller`) |
| GT-05 | Đạt (applicability; `watermark_candidate` trang 171, T-10 đã sửa điều kiện) |
| GT-06, GT-10 | Đạt khi có `objects.json` (fixture F54 có); crop render khi có PDF |
| GT-07 | Đạt (T-08 v1, `test_lists.py`) |
| GT-08, GT-09, GT-12 | Phần section path đạt (BL-08); `lang` theo element chờ I-16 |
| GT-11 | Phần trang in (T-06) đạt; manifest ghi đè, `doc_version_mismatch` chưa có |
| GT-13, GT-15 | Đạt ở mức lõi approval (HA-03, HA-05); gán unit từ builder chờ BL-19 |
| GT-14 | Lõi phụ thuộc đạt (HA-04); unit trang 40 chờ BL-16, BL-19 |
| GT-16 | Lõi conflict đạt (HA-06); dữ liệu F86 chờ BL-13 |
| GT-17 | Đạt cho `tables`, `review_queue`, `normalization_log` của bước bảng; toàn pipeline chờ BL-23 |
| GT-20 | Đạt (V-01 trên phần tử Docling đã phân loại; chạy lại trên `NormalizedElement` khi có BL-04 đầy đủ) |
| GT-21 | Chờ BL-25 (V-02) |
| GT-22 | Phần T-15 đạt (LT-02, LT-04); V-03 chờ BL-25 |
| GT-23 | Đạt (PI-04) |
| CQ-01…CQ-08 (+ CQ-09, CQ-10, CQ-RB) | Có code (BL-15, 2026-11-09); đạt trên F54 và F86 Installation (§6.15); RB-02 trên CSV F86 chưa chạy |
| RB-01 | Đạt (`test_f86_baseline.py`) |
