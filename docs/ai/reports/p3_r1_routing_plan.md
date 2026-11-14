# R-1: tối ưu bước phân tích (intent, mô tả, model LLM) và định tuyến tra cứu

## Context
- Bước phân tích chọn intent → registry đổi intent thành nơi tìm (domain, scope). Chọn sai intent là mất hẳn nguồn
  đúng. Dữ liệu thật (eval 2026-11-14): D21 "#12100", D30 "cài ở đâu", Q9 "công thức", Q8 "cổng CN10" đều bị xếp
  `lookup.product_info` → chỉ tìm catalog → trả chunk catalog sai với điểm vector 0,53–0,65 (cao hơn ngưỡng 0,25, nên
  fallback "khi rỗng" và fallback theo ngưỡng điểm đều không cứu được).
- Nguyên nhân gốc đã xác định:
  1. Intent trộn hai trục: việc người dùng muốn làm và nơi câu trả lời nằm. LLM không biết nội dung tài liệu.
  2. Hai nguồn định nghĩa lệch nhau: `desc` (registry) và `<intent_rules>` (khung prompt; quy tắc 4 chỉ đưa "tham số"
     về cấu hình khi hỏi "CÁC BƯỚC", nên "#12100 là gì" rơi xuống quy tắc 5).
  3. Nhãn intent là bộ lọc cứng theo domain.
  4. D26: `orchestration/planner.held_sub_query_ids` giữ lại (không tìm) mọi sub-query có `unresolved_mentions` trùng
     câu hỏi làm rõ. LLM coi tên board "08_RLTR" là model lạ → không tra cứu dù câu đã nêu F54.
- Đã có (2026-11-14): `PROMPT_VERSION = "v1"`, `INTENT_DESC_VERSION = "v1"`, eval chọn bản bằng `--prompt-version`,
  `--intent-desc-version`. Model phân tích đang chạy: `gpt-4.1-mini` (`OPENAI_MODEL`), temperature 0, vẫn dao động.
- Mục tiêu: định tuyến đúng và ổn định hơn, đo được bằng số; mọi thay đổi hành vi đều có phiên bản, production giữ
  nguyên cho tới khi Toma chốt từng bản.

## Ràng buộc
- Production không đổi hành vi trong cả kế hoạch: bản mặc định giữ `v1` / `v1` / `r0`; bản mới chỉ công cụ eval chọn.
  Đổi mặc định = quyết định của Toma ở cuối mỗi giai đoạn (cổng duyệt).
- Không đổi SQL, không ghi Supabase (eval chỉ đọc). Không thêm dependency. Không đổi contract HTTP/SSE.
- `registry.py` + `validate_registry.py` dùng chung cho website-qa và tool `product_docs_ask` (crm-agent): chạy cả
  `tests\chatbot`; ghi crm-agent LOG khi đổi mặc định.
- Kết quả eval ghi thư mục mới, không ghi đè. Bộ câu hỏi và nhãn sửa: Toma duyệt trước khi dùng.

## Giai đoạn A — Công cụ đo và bộ câu hỏi (làm trước; chưa đổi hành vi)

### A1. `backend/evals/run_retrieval_eval.py`
| Thêm | Chi tiết |
|---|---|
| `--repeat N` | Chạy bước phân tích N lần mỗi câu mỗi lượt (mặc định 1). `RoutingResult`/`CaseResult` thêm `run`. Bảng tổng = trung bình các lần; thêm **ổn định** = tỉ lệ câu cho cùng (intent, route, domain) ở mọi lần; liệt kê câu không ổn định kèm intent từng lần |
| `--analysis-model <tên>` | `OpenAIProvider` riêng cho `AnalysisStage` (embedding giữ provider của settings); ghi `meta.analysis_model` |
| Độ trễ + lỗi | Bọc provider phân tích bằng proxy đo thời gian `chat_complete_json` → p50/p95; `AnalysisError` (timeout 8 s, output sai) không làm dừng eval: ghi `loi_phan_tich` cho câu đó |
| `--mode routing` | Chỉ chấm định tuyến: pipeline thật với retriever giả (trả rỗng), không phát lại biến thể tìm kiếm → vòng lặp sửa prompt nhanh, rẻ |
| Bảng nhầm lẫn | Intent mong đợi × intent thực tế; bảng theo cặp dễ nhầm (tag `cap:<a>~<b>`) |
| `split` | Trường `split: dev\|test` của câu (mặc định `dev`), cờ `--split dev\|test\|all` |
| Sửa coverage | `load_index`: chỉ thêm coverage `technical_docs` cho model có chunk **domain technical_docs** (hiện thêm nhầm 10S, 10i, 6AH, 6AV, F10T) |
- Test hàm thuần trong `tests/chatbot/test_retrieval_v2.py` (trung bình theo lần chạy, ổn định, bảng nhầm lẫn, split).

### A2. Bộ câu chỉ chấm định tuyến `evals/retrieval_cases/routing_intent.yaml` (~120 câu)
- Mỗi câu: `question`, `models`, `expected_intent`, `expected_domain`, `expected_route`, `tags`, `split`. Không cần
  gán chunk đúng (rẻ, soạn nhanh).
- Phân bổ theo cặp dễ nhầm (mỗi cặp ≥ 10 câu, cân hai phía): thông số sản phẩm ↔ tham số cài đặt; cổng có sẵn ↔
  cổng dùng làm gì/đấu thế nào; thông tin một model ↔ danh mục/tư vấn; vận hành ↔ xử lý sự cố; vận hành ↔ cấu hình;
  lắp đặt ↔ cấu hình; công ty ↔ chuyển người; cộng nhóm đối chứng (chào hỏi, ngoài phạm vi, giá).
- Dạng câu: có mã (`#…`, `CN…`, `X…`, `M…`, `G…`), không dấu, tiếng Anh, giọng nhân viên ("khách hỏi…"), có/không model,
  có tên board/phụ kiện (08_RLTR, RBT-01).
- `split`: 60% `dev` (dùng để sửa luật và prompt), 40% `test` (chỉ đo, không dùng để soạn ví dụ mẫu).
- Quy trình: Claude soạn → **Toma duyệt** (nên thêm/sửa 20–30 câu `test` bằng cách hỏi thật của khách và nhân viên) →
  đóng băng.

### A3. Hai câu D01, K09: sửa hệ thống thay vì nới nhãn (Toma hỏi 2026-11-14)
Hai câu thuộc hai loại khác nhau:

| Câu | Thực tế đang xảy ra (mốc 3 lần) | Bản chất | Xử lý |
|---|---|---|---|
| D01 "F54 cấp nguồn bao nhiêu volt?" | 3/3 lần `lookup.product_info` → chỉ tìm catalog → trả chunk catalog C0000 có "Voltage input: 24VDC"; không lấy được mục 2.2 của manual (cách cấp nguồn) | Câu trả lời nằm ở **hai nguồn**, hệ thống chỉ tìm một → trả lời đúng nhưng thiếu | **Sửa hệ thống bằng RT-1** (giai đoạn B). Nhãn: chỉ thêm C0000 vào `acceptable` (nó trả lời được câu hỏi); **giữ** `expected` = chunk manual và `expected_domain` = `technical_docs`, để câu này là phép đo của RT-1 (không nới domain) |
| K09 "Trọn bộ hệ thống của F54 gồm những thiết bị gì?" | `lookup.product_catalog` thay vì `lookup.product_info`; cùng domain, cùng bộ lọc model → **kết quả tìm y hệt** (chunk đúng hạng 3, có trong ngữ cảnh). Kênh CRM cũng không khác: `CatalogLookupStage` chỉ chạy khi không có model | Hai intent **tương đương về hành vi** khi câu đã nêu model → không phải lỗi hệ thống | Nhãn chấp nhận cả hai intent. Phần đáng sửa là **thứ hạng** (hạng 3): câu tiếng Việt, chunk "trọn bộ" chỉ có nhãn tiếng Anh → `--vi-keywords` (đang chờ Toma), cùng nhóm với K10, K19 |

- Hệ quả cho RT-1: định nghĩa theo **điều kiện**, không theo tên intent (xem B2) → bao luôn câu kiểu K09/D39 bị xếp
  `lookup.product_catalog` nhưng có model.
- Q12, D39: giữ nguyên nhãn (đang là lỗi thật, RT-1 nhắm tới).

### A4. Mốc so sánh
- Chạy `v1` / `v1` / `r0` / `gpt-4.1-mini`, `--repeat 3`: `routing_intent.yaml` (dev + test) và 3 bộ tra cứu (14, 40,
  catalog 20). Biên dao động giữa các lần chạy của mốc = "nhiễu"; chênh lệch nhỏ hơn nhiễu không coi là cải thiện.

### A5. Bộ câu "hai nguồn" để đo RT-1 có giúp câu tương tự không
- `evals/retrieval_cases/dual_source.yaml`, 12–15 câu **có gán chunk đúng** (Claude soạn từ chunk đã nạp, Toma duyệt):
  câu thông số/đặc điểm của F54, F86 mà câu trả lời nằm ở manual hoặc ở cả manual lẫn catalog. Ví dụ: kích thước lắp
  đặt, nguồn cấp và dòng tiêu thụ, số ngõ vào/ra và địa chỉ I/O, các cổng trên bộ điều khiển, board I/O link dùng được,
  loại tay quay/cảm biến hỗ trợ. Khác cách hỏi với D01, Q12, D39 (không lặp câu cũ).
- Cùng 4 câu đối chứng thuần catalog (số trục, look-ahead, giao tiếp điều khiển) để bắt trường hợp RT-1 làm chunk
  manual chen lên trên chunk catalog đúng.

### Trạng thái giai đoạn A (2026-11-14)
- A1 xong (eval: `--repeat`, `--mode routing`, `--analysis-model`, `--split`, bảng nhầm intent, "không tìm").
- A2 đã soạn `routing_intent.yaml` (120 câu, 72 dev / 48 test), chờ Toma duyệt.
- A4 đã có mốc: 40 câu đúng cả ba 0,867 (nhiễu 2,5–5 điểm %); 120 câu 0,936 / 0,942; nhóm tên board/phụ kiện 0,29 /
  0,71 (lỗi D26 có hệ thống). Còn: mốc bộ 14 câu, catalog 20 câu, và bộ "hai nguồn" sau khi duyệt.

**Cổng A:** Toma duyệt `routing_intent.yaml`, `dual_source.yaml`, nhãn D01/K09; có bảng mốc đủ các bộ.

## Giai đoạn B — Luật định tuyến bằng code, có phiên bản (R-1 a, G1, G4, D26)

### B1. Cơ chế phiên bản
- `extraction/registry.py`: `ROUTING_VERSION = "r0"` (production = hành vi hiện tại), `ROUTING_RULES = {"r0": …, "r1":
  …, "r2": …}` (cờ từng luật). Tham số `routing_version` (None = mặc định) truyền qua
  `validate_registry.resolve_sub_query` → `resolve_with_raw` → `analysis/analyzer.build_analysis` →
  `stages/analysis_stage.AnalysisStage` và `stages/clarification_resume_stage.ClarificationResumeStage`.
- Mỗi luật chạy thì thêm `routing_rule:<mã>` vào `warnings` của sub-query (đã có sẵn trường) → trace và báo cáo eval
  biết luật nào đã tác động. Eval: `--routing-version`, ghi `meta`.

### B2. Luật
| Mã | Bản | Luật | Xử lý được |
|---|---|---|---|
| RT-1 | r1 | Theo **điều kiện**, không theo tên intent: sub-query có target chính là `product_catalog` **và** có model đã xác định với coverage kỹ thuật (`lookup.product_info`, hoặc `lookup.product_catalog` có model; không áp cho `compare.product_models`) → tìm thêm `technical_docs` (không scope); kết quả gộp theo điểm, target chính (catalog) được cộng `target_boost` | D01, Q12 (G1), D39; D21, Q8, Q9, D30 có chunk đúng trong ngữ cảnh dù intent vẫn sai; mọi câu "thông số có trong manual" tương tự |
| RT-2 | r1 | Câu có mã kỹ thuật (mở rộng `MODEL_SPECIFIC_PATTERN`: `#số`, `CNn`, `Xn`, `Yn`, `ALn`, `Mn`, `Gn`; **không** nhận `RS485`, `USB2`…) mà intent là `lookup.product_info`/`lookup.product_catalog` → `technical_docs` thành target chính, catalog thành phụ | D21, Q8, D30 lên hạng đầu |
| RT-3 | r1 | Tên board/phụ kiện đã biết (`REGISTRY["non_model_terms"]`: 08_RLTR, RBT-01…; lấy từ tên mục chunk + catalog trang 22–23, Toma duyệt danh sách) bị loại khỏi `unresolved_mentions` trước `resolve_models` | D26 (không còn bị giữ lại) |
| RT-4 | r2 | Cụm cấu hình/cách làm (so trên câu đã bỏ dấu: "tham so", "cai o dau", "cong thuc", "thiet lap"…) + intent `lookup.product_info` → đổi target chính sang `technical_docs` | Q9, D30 lên hạng đầu; rủi ro bắt nhầm → đo riêng ở r2 |
- Thực hiện RT-1/RT-2: `schemas/system/analysis.py` `RetrievalTarget.boost: float = 0`; `schemas/system/retrieval.py`
  `RetrievalRequest` mang `boost`; `orchestration/handlers.build_retrieval_requests` chuyển tiếp;
  `retrieval/retriever.Retriever._merge` sắp theo `fused_score + boost` của lần tìm (nhánh so sánh giữ nguyên).
  `Retriever` vốn đã gộp nhiều target theo điểm → không đổi SQL.
- `target_boost`: dò bằng eval (0 / 0,003 / 0,005) như đã làm với scope; chốt một giá trị.
- R-2 (đã chốt): mặc định `MatchV2Options` → `scope_mode="boost"`, `scope_boost=0.003`
  (`repositories/doc_chunk_v2_repository.py`; chỉ công cụ eval đang dùng repository này). Giảm tác hại G4
  (`troubleshoot.error` lệch scope `maintenance`).
- Không làm: fallback "khi kết quả yếu" theo ngưỡng điểm (dữ liệu cho thấy vùng điểm chồng nhau; RT-1 thay thế).

### B3. Test + đo
- Test mới `tests/chatbot/test_routing_rules.py`: từng luật bật/tắt theo phiên bản; `r0` cho kết quả y như hiện tại
  (so với `resolve_sub_query` trước thay đổi trên bộ đầu vào mẫu); RT-2 không bắt `RS485`; RT-3 để D26 đi tiếp tra cứu.
  Cập nhật `test_analysis_contract`, `test_retrieval*`, `test_orchestration_*` theo trường `boost`.
- Đo `r0` / `r1` / `r2` × `--repeat 3` trên 5 bộ (thêm `dual_source.yaml`). Chỉ số quyết định: `ngu_canh` và MRR
  web2, `domain đúng`.
- Trả lời câu "sửa D01 có giúp câu tương tự không": so `r0` ↔ `r1` trên `dual_source.yaml` (kỳ vọng `ngu_canh` tăng rõ)
  và trên catalog 20 câu + 4 câu đối chứng (kỳ vọng không giảm: nếu chunk manual chen lên trên chunk catalog đúng thì
  tăng `target_boost`). Giới hạn đã biết của RT-1: chỉ có tác dụng với model có tài liệu kỹ thuật (hiện F54, F86); thêm
  một lần truy vấn DB cho mỗi câu thông số.

**Cổng B:** Toma chọn `r1` hoặc `r2` và giá trị `target_boost`. Đổi `ROUTING_VERSION` mặc định cùng lúc tích hợp
`doc_chunks_v2` vào chat (bước 6), vì bảng `doc_chunks` cũ không có tài liệu kỹ thuật.

## Giai đoạn C — Mô tả intent `v2` và khung prompt `v2`

### C1. Tổng hợp nội dung thật của từng nguồn (chỉ đọc)
- Script tạm đọc `doc_chunks_v2` (hoặc `doc_chunks_v2.jsonl` của các run đã nạp): theo từng (domain, scope) liệt kê tên
  mục cấp 1–2, số chunk theo `chunk_type`, mã tiêu biểu. Ra bảng markdown gửi Toma: "mỗi nguồn trả lời được câu gì".

### C2. Mô tả intent `v2` (`INTENT_DESC_VARIANTS["v2"]`, `extraction/registry.py`)
- Tiêu chí (ghi vào README website-qa): (1) intent chỉ tồn tại khi làm hệ thống hành xử khác (nguồn tìm, chính sách
  model/hỏi lại/chuyển người, dạng trả lời); (2) mô tả = "câu hỏi mà câu trả lời nằm trong loại nội dung này", chủ đề
  lấy từ C1; (3) mỗi cặp dễ nhầm có một câu ranh giới chỉ sang intent kia; (4) registry là nguồn định nghĩa duy nhất.
- Mẫu mỗi intent, tối đa 2 dòng: "Trả lời: … Gồm: … Không phải: … → `<intent khác>`". Ví dụ ranh giới: thông số in
  trong catalog (kích thước, số trục, nguồn) ↔ tham số cài trong máy (`#số`, giá trị cài, công thức); "có cổng gì" ↔
  "cổng CN10 dùng làm gì / đấu thế nào". Bao G2, G3 (mô tả vận hành/cấu hình thiếu chủ đề).
- **Toma duyệt câu chữ** trước khi đo.

### C3. Khung prompt `v2` (`_frame_v2` trong `analysis/prompt/prompt_builder.py`, ví dụ trong `registry_render.py`)
- `<intent_rules>`: chỉ còn thứ tự ưu tiên khi nhiều intent cùng khớp, không định nghĩa lại intent; bỏ điều kiện
  "CÁC BƯỚC" gây lỗi D21 (hỏi về tham số/mã cài đặt → cấu hình kể cả khi hỏi "là gì").
- `<entity_rules>` 2: `unresolved_mentions` chỉ cho cụm giống tên **bộ điều khiển**; tên board, phụ kiện, servo giữ
  nguyên trong `standalone_query`, không ghi vào trường này (bổ sung cho RT-3).
- Ví dụ mẫu: thêm 4–5 cặp đối chiếu cho các cặp dễ nhầm (soạn mới, không lấy câu của phần `test`); `_render_examples`
  nhận danh sách ví dụ theo khung. Theo dõi kích thước prompt (bản lean `n_examples=4`) và độ trễ.
- Thêm dấu nội dung `v2` vào `tests/chatbot/test_analysis_prompt_version.py`.

### C4. Đo
- Trên `dev`, `--mode routing --repeat 3`: (khung v1, mô tả v1) · (v1, v2) · (v2, v2), mỗi tổ hợp với `r0` và bản
  routing đã chọn ở B. Sửa lặp chỉ dựa trên `dev`. Khi ổn: đo **một lần** trên `test` + 3 bộ tra cứu.

**Cổng C:** Toma chọn tổ hợp; đổi `PROMPT_VERSION` / `INTENT_DESC_VERSION` mặc định (ảnh hưởng ngay cả web và
`product_docs_ask` → ghi LOG hai luồng).

## Giai đoạn D — So sánh model LLM cho bước phân tích
- Ứng viên: Toma chốt 2–3 model có trên tài khoản (model hiện tại `gpt-4.1-mini` làm mốc; một model rẻ hơn, một model
  mạnh hơn).
- Chạy `--analysis-model <m> --repeat 3` với tổ hợp prompt + routing đã chọn, trên `test` + 3 bộ tra cứu.
- Bảng quyết định: đúng cả ba (intent, route, domain), ổn định, p50/p95 độ trễ, số lần timeout 8 s, chi phí ước tính
  mỗi 1.000 lượt (số token prompt × giá model). Quy tắc chọn: model rẻ nhất nằm trong 1–2 điểm % của model tốt nhất và
  p95 dưới timeout.
- Nếu model phân tích khác model trả lời: thêm cấu hình `ANALYSIS_MODEL` (rỗng = `OPENAI_MODEL`) ở `app/core/config.py`,
  cập nhật `docs/ai/rules/deploy-rules.md`. Chỉ làm khi Toma chọn model khác.

**Cổng D:** Toma chốt model.

## Tiêu chí đạt (đề xuất, Toma chỉnh)
- Phần `test`: đúng cả ba ≥ 0,93 (trung bình 3 lần), ổn định ≥ 0,95.
- D21, D30, Q8, Q9: chunk đúng nằm trong ngữ cảnh ở web2, cả 3 lần chạy; D26 luôn tra cứu.
- Không hồi quy vượt biên nhiễu của mốc trên bộ 14, 40 và catalog 20 câu (catalog web2 recall@5 giữ 1,0).

## Ngoài phạm vi
- Tách hẳn hai trục "việc cần làm" / "nơi tìm" (đổi contract bước phân tích): chỉ xét nếu sau B + C chưa đạt tiêu chí.
- Bật nhánh mã (`codes`) và `type_boost` (G7), bộ từ `spec_attributes` (G5), `--vi-keywords` cho catalog, tích hợp
  `doc_chunks_v2` vào chat (bước 6), ghi phiên bản prompt vào trace production.

## File chính
- Sửa: `backend/evals/run_retrieval_eval.py`; `app/modules/chatbot/extraction/{registry,validate_registry}.py`;
  `analysis/{analyzer.py,prompt/prompt_builder.py,prompt/registry_render.py}`;
  `stages/{analysis_stage,clarification_resume_stage}.py`; `orchestration/handlers.py`; `retrieval/retriever.py`;
  `schemas/system/{analysis,retrieval}.py`; `repositories/doc_chunk_v2_repository.py`.
- Mới: `evals/retrieval_cases/routing_intent.yaml` (đã soạn), `evals/retrieval_cases/dual_source.yaml`;
  `tests/chatbot/test_routing_rules.py`.
- Dùng lại: `MODEL_SPECIFIC_PATTERN` (registry), `retrieval/codes.extract_codes`, `Retriever._merge`,
  `intent_descriptions()` / `INTENT_DESC_VARIANTS`, `analysis_prompt_info()`, `WEB_VARIANTS` + cơ chế phát lại của eval.
- Tài liệu mỗi giai đoạn: website-qa `README.md` (tiêu chí intent, phiên bản routing), `STATE.md`, `LOG.md`; crm-agent
  `LOG.md` khi đổi mặc định.

## Kiểm tra
- Từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests` (gồm `tests\chatbot`, test phiên bản prompt, test luật
  định tuyến); sửa tài liệu: `.\venv\Scripts\python.exe scripts\check_ai_docs.py`.
- Bất biến `r0`/`v1`: sau mỗi giai đoạn, chạy eval mặc định trên bộ 14 câu → định tuyến và hạng nằm trong biên nhiễu
  của mốc A4; prompt `v1` giữ nguyên dấu sha256 (`8e431a735a4c` với `n_examples=4`).
- Mỗi cổng: báo cáo `data/retrieval_eval/<thời điểm>-<nhãn>/report.md` có đủ nhãn (khung, mô tả intent, routing, model,
  số lần lặp) và bảng so với mốc.
