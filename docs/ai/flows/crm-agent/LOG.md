# Nhật ký luồng crm-agent

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính. Sau khi thêm mục, viết lại [STATE.md](STATE.md).
Mẫu mục: [../_template/LOG.md](../_template/LOG.md).

Các mục tới 2026-11-10 (nguyên văn từ `current-state.md` và `architecture.md`):
[LOG-archive-2026-11-11.md](LOG-archive-2026-11-11.md). Các mục 2026-11-10 đến 2026-11-19: [LOG-archive-2026-11-19.md](LOG-archive-2026-11-19.md).

## 2026-11-20 · Tổng hợp ngày: Đợt 1 bước 1–3 và LC-2/4/7 đã merge; trần token lượt môi trường kiểm thử 30000 · loại: quyết định, tài liệu

- Quyết định: Toma đặt `AGENT_TURN_INPUT_BUDGET=30000` ở môi trường kiểm thử (`.env.example` của Toma, chưa commit);
  mặc định code giữ 40000 (`0561487`); tinh chỉnh tiếp theo kết quả kiểm thử (duyệt: Toma, 2026-11-20; căn cứ: lượt
  CRM 3 bước ~20k, 4 bước ~30k token vào, lần kiểm 09:57).
- Tổng hợp luồng xử lý hiện tại, 7 quyết định trong ngày, kết quả kiểm thử (so sánh C1–C7; 7 câu CRM 1/7 → 5/7),
  chi phí và vấn đề mở: [báo cáo 2026-11-20](../../reports/crm_agent_status_2026-11-20.md). Quyết định liên luồng
  về context phiên ghi ở `decisions.md` (D-015).
- Viết lại STATE theo trạng thái trên `0561487`; dòng crm-agent trong `current-state.md`; mục ngắn ở chat-platform
  và website-qa (ContextLoader chỉ đọc 10 lượt gần nhất, `conversation_state.facts`).
- Chưa kiểm / mở tiếp: chạy lại 7 câu sau LC-7 với trần 30000 khi tunnel CRM hoạt động lại; LC-8, LC-6 chờ Toma.

## 2026-11-20 · Trần token lượt 40k; bước chốt khi hết lượt gọi không còn nói thiếu dữ liệu (LC-7) · loại: thay đổi

- Vấn đề: lượt thật 09:57 (mục dưới): câu 5, 6 dừng `budget` ở ~21–24k vì trần 15k, và chỉ dẫn bước chốt ("… mà chưa
  đủ kết quả", khung "phần chưa lấy được") khiến LLM nói sai "chưa lấy được" và hỏi lại dù dữ liệu đủ.
- Thay đổi (Toma duyệt 2026-11-20): `AGENT_TURN_INPUT_BUDGET` mặc định 15000 → 40000 (lượt CRM 3 bước ~20k, mỗi bước
  ~6–8k). Lý do `budget` nêu trung tính ("đã dùng hết ngân sách gọi tool"). Với `budget`/`limit`, chỉ dẫn đặt điều
  kiện trước: kết quả đã đủ thì trả lời bình thường, không nhắc giới hạn, không nói thiếu, không hỏi lại; chỉ khi thiếu
  mới theo khung. `ambiguous`/`plateau` giữ khung cũ.
- File: `agent/prompts.py`, `core/config.py`, `agent/runner.py`; test `test_agent_loop_control.py` (+1).
- Kiểm chứng: `pytest tests` → 1165 passed, 14 skipped, 1 failed có sẵn (CSV CRLF). Chưa kiểm thật.
- Ảnh hưởng cấu hình: mặc định mới; `.env` đang đặt `AGENT_TURN_INPUT_BUDGET=15000` thì phải sửa tay.
- Chưa kiểm / mở tiếp: hỏi lại câu 5, 6; LC-8, LC-5, LC-6.

## 2026-11-20 · Kiểm lại 7 câu sau LC-2/LC-4: thử lại cứu được lượt hết giờ, gợi ý cột được LLM tự sửa; trần token lượt 15k quá thấp · loại: kiểm chứng

- Dữ liệu: phiên `45efd790…` 09:57–09:59 UTC, backend `a8da3c9`, gpt-4.1-mini; đối chiếu Reporting API (tunnel CRM
  offline từ 10:00, chưa đối chiếu được tên sale ở câu 6).
- 5/7 có số liệu đúng (trước: 1/7): 18 tin chờ (định nghĩa "mọi tin", LC-6); 7 tin mới nhất; 2 phiếu tháng 11 đều
  `closed`; 5 khách mới nhất đúng thứ tự (C000612…C000608) kèm sale; "khách thứ 2" = C000611, 0 thiết bị (ordinal
  của facts dùng đúng).
- LC-2: 1 lần hết giờ (câu 1, bước 2) có `timeout_phase=read` (request đã tới OpenAI, chờ phản hồi 19 s); thử lại
  xong 1,5 s (`provider_processing_ms` 863). Nguồn: phía OpenAI, không phải mạng hay CRM. 20 lần gọi còn lại 0,7–3,4 s.
- LC-4: câu 6 `name` bị chặn trước CRM với gợi ý `full_name`; câu 5 `created_at` đặt trong filters bị chặn; cả hai
  LLM tự sửa ở bước sau, không cần `forced_repair`.
- Sai 1 (câu 3, 4): lọc `title eq "<nội dung>"` thay vì `content`; 0 dòng nên kết luận "không tìm thấy". Facts có
  id của tin #3 nhưng **không có nhãn**: lượt liệt kê chỉ chọn `content` (không lưu vào facts) nên nhân viên gọi
  bằng nội dung thì LLM không khớp được.
- Sai 2 (câu 5, 6): `final_reason=budget` vì token vào cộng dồn 21–24k > `AGENT_TURN_INPUT_BUDGET=15000`; một lượt
  CRM 3 bước đã khoảng 20k (mỗi bước ~6–8k vì guide). Khung bước chốt khiến LLM nói sai "chưa lấy được…" và hỏi lại
  thừa dù dữ liệu đủ.
- Mở tiếp: (LC-7) nâng trần token lượt (đề xuất 40k) và sửa chỉ dẫn bước chốt khi dừng vì ngân sách; (LC-8) nhãn
  cho bản ghi không có cột tên/tiêu đề trong lượt liệt kê; LC-5, LC-6.

## 2026-11-20 · LLM hết giờ được đo và thử lại; lỗi cột bị chặn trước CRM, kèm gợi ý, và bắt sửa một lần (LC-2, LC-4) · loại: thay đổi

- Vấn đề: lượt thật 2026-11-20 (mục dưới): 4 lần gọi gpt-4.1-mini treo đúng 20 s (gửi lại cùng nội dung xong
  2–5 s); LLM đoán cột (`customers.name`, `product_ownerships.customer_id`) rồi trả lời ngay, không sửa.
- Nguồn LC-2: span hết giờ là `llm.chat_tools`, không phải tool CRM; client OpenAI để mặc định SDK (timeout 600 s,
  tự thử lại 2 lần) nên runner cắt ở 20 s không biết là OpenAI chậm, 429 hay mạng.
- Thay đổi (Toma duyệt hướng 2026-11-20, tham khảo `ModelRetry` của Pydantic AI, `sql_db_query_checker` của
  LangChain; không dùng `enum` cột động vì làm mất prompt cache):
  - LC-2: `OpenAIProvider(tool_call_timeout_s=AGENT_LLM_TIMEOUT_S − 1, max_retries=0)` cho `chat_complete_tools`;
    span ghi `provider_request_id`, `provider_processing_ms`, `timeout_phase` (connect/read). 429/5xx/mất kết nối →
    `ProviderTransientError`. Runner thử lại **một lần** mỗi bước (kể cả bước chốt) khi hết giờ hoặc lỗi tạm thời,
    nếu deadline còn đủ; hết lượt thử ở bước chốt thì ném lỗi gốc như trước.
  - LC-4 (chính): `crm_query` tải schema sống của bảng gốc nếu chưa cache, `compile_raw(known_columns=…)` báo
    `tool_invalid_args` khi cột không có, kèm cột gần đúng (`name` → `full_name, company_name`; `customer_id` →
    `owner_customer_id`) và danh sách cột; không gửi CRM. Chỉ dùng schema sống (index tĩnh có thể lệch); không tự sửa.
  - LC-4 (lưới an toàn): `ToolSpec.repairable_errors` (mặc định `tool_invalid_args`; `crm_query` thêm
    `crm_query_invalid`). LLM trả lời ngay sau lỗi đó mà chưa gọi lại thành công → bỏ câu trả lời, chèn `REPAIR_NOTE`,
    một bước `tool_choice=required`; chỉ một lần mỗi lượt (vẫn lỗi thì C1 dừng `plateau`).
- File: `providers/{base,openai}.py`, `agent/{runner,prompts}.py`, `tools/{base,crm_query}.py`,
  `reporting/raw/compile.py`, `core/config.py` (`agent_request_timeout_s`), `main.py`; test mới
  `test_agent_lc_fixes.py` (13).
- Kiểm chứng: `pytest tests` → 1164 passed, 14 skipped, 1 failed có sẵn (CSV CRLF). Chưa kiểm trên server thật.
- Ảnh hưởng contract: thuộc tính trace mới (api_guidelines mục trace); không đổi route, SSE, biến môi trường.
  Request tool-calling không còn được SDK tự thử lại ngầm (runner thử lại, thấy được trong trace).
- Chưa kiểm / mở tiếp: chạy lại 7 câu; khi còn hết giờ, tra `provider_request_id` trên OpenAI Dashboard; LC-5, LC-6.

## 2026-11-20 · Gói A: facts của phiên và lịch sử theo lượt; kiểm thật 7 câu, facts dùng đúng UUID qua lượt · loại: thay đổi, kiểm chứng

- Thay đổi (Toma duyệt thiết kế 2026-11-20: trần 10 dòng/danh sách, nhãn từ cột cho phép, 8 luật chống dùng nhầm):
  - L1: `list_for_context(limit)` đọc `CONTEXT_HISTORY_TURNS` (10) lượt gần nhất; agent lấy `AGENT_HISTORY_TURNS` (3)
    lượt hỏi + đáp, thay `AGENT_HISTORY_MESSAGES` (giữ trong config, không dùng).
  - L2: `ConversationState.facts` (`schemas/system/facts.py`): thực thể (kind, table, id, keys username/code,
    label ≤ 80 ký tự, ordinal, turn) + 5 lookup + `pending_reason`. Tool ghi qua `ToolSpec.remember`
    (`crm_query`: 10 dòng đầu của list, cột cho phép; `product_docs_ask`: chỉ lookup). `merge_facts`: danh sách
    mới xoá ordinal cũ, trùng thì cập nhật, TTL 10 lượt, tối đa 20, đổi `acting_user_id` thì xoá. Prompt
    `<session_state>` ≤ 500 token kèm luật chỉ dùng cho lời tham chiếu, không thêm điều kiện, nêu nhãn khi dùng.
  - Guide `crm_query`: UUID lấy được từ `<session_state>`; answer_rules: liệt kê đúng thứ tự tool.
- File: `schemas/system/{facts,run_context,agent,__init__}.py`, `tools/{base,crm_query,product_docs}.py`,
  `agent/{runner,prompts}.py`, `clarification/state_update.py`, `stages/context_loader.py`,
  `repositories/history_repository.py`, `services/chat_service.py`, `core/config.py`; test mới
  `test_agent_session_facts.py` (17), fake `list_for_context` nhận `limit`.
- Kiểm chứng: `pytest tests` → 1151 passed, 14 skipped, 1 failed có sẵn (CSV CRLF). Lượt thật 09:19–09:21 UTC (phiên
  `38f77fbd…`, qua route kiểm thử widget-backend, backend `98f2db4`), đối chiếu Reporting API:
  - Đúng nhờ facts: "Nội dung F54_…382 có ai phản hồi chưa" lọc `message_id eq <UUID>` lấy từ lượt trước, ra 9 phản
    hồi (đúng: 4 của chính khách, 5 của nhân viên; câu trả lời gộp thành "nhiều người khác nhau").
  - Hết giờ LLM 20 s (LC-2): 2/7 lượt (+1 lượt thử trước đó) → không có số liệu, bước chốt hỏi lại vô ích.
  - LLM không thử lại sau lỗi tham số (LC-4): `customers.name` (cột là `full_name`), `product_ownerships.customer_id`
    (cột là `owner_customer_id`); cả hai lượt đoán cột, không gọi hoặc gọi `crm_schema` song song với `crm_query`.
  - Suy luận sai (LC-5): "người nhắn có thuộc khách hàng công ty" lấy 10/562 khách bất kỳ rồi kết luận "có trong
    danh sách"; `customer_id` của tin nhắn là tài khoản (không khoá ngoại), đường đúng là `product_item_id.customer_id`.
  - Định nghĩa "hộp tin nhắn chờ" (LC-6): lượt này 18 tin (mọi tin), phiên trước 7 tin (`staff_deleted_at` null).
- Ảnh hưởng contract/cấu hình: biến mới `AGENT_HISTORY_TURNS`, `CONTEXT_HISTORY_TURNS`; `conversation_state` có khoá
  `facts` (nội bộ, không SQL). Website cũng chỉ đọc 10 lượt gần nhất.
- Chưa kiểm / mở tiếp: câu dùng ordinal ("khách thứ 2") chưa kiểm được vì lượt liệt kê lỗi; LC-2, LC-4, LC-5, LC-6;
  Gói B (kiểm nguồn gốc giá trị) dùng facts làm nguồn hợp lệ.

## 2026-11-20 · Lượt CRM thật sau C1–C3: mất UUID qua lượt và hết giờ LLM; thêm luật tìm lại bản ghi bằng cột chữ · loại: kiểm chứng, thay đổi

- Dữ liệu: phiên `8de1e4b1…` 07:56–08:16 UTC, `CRM_REPORT_ENABLED=true`, gpt-4.1-mini, backend `4a636b2`. Đối chiếu
  bằng Reporting API của CRM dev (chỉ đọc, token của Toma). Không ghi nội dung tin nhắn, tên hay email vào LOG.
- Đúng với CRM: đếm ticket, khách của một sale (lượt đó dừng `final_reason=budget`: 4 lần gọi, 2 `crm_schema`
  song song, chưa trả `ok` trước nửa trần), chia theo `customer_type`, đếm và liệt kê 7 tin nhắn chờ.
- Sai 1, "có ai phản hồi câu 1 chưa?" (08:12): CRM có **1 phản hồi** của nhân viên (19/11), tin đã `handled`.
  Agent đặt nội dung tin nhắn vào `message_id` (uuid) → `tool_invalid_args` (detail gợi ý lọc cột chữ qua quan hệ),
  không thử lại, hỏi nhân viên UUID. Nguồn: (a) P1: lượt 08:02 có `select id` nhưng câu trả lời không in id,
  lượt sau không còn UUID; (b) LLM bỏ qua gợi ý trong lỗi. Query đúng chỉ một lần:
  `support_waiting_message_replies`, filter `message_id.content contains "<đoạn chữ>"`.
- Sai 2, "ai nhắn câu hỏi đó, có thuộc khách hàng công ty không?" (08:16): hai lần gọi LLM (bước 1 `auto`, bước chốt
  `none`) cùng hết giờ 20 s → `agent_timeout`, history `error`, không gọi tool; usage ước tính (~3,6k token vào mỗi
  lần, bình thường). Nguồn: độ trễ nhà cung cấp hoặc mạng (không có log server để phân biệt). Đáp án đúng trên
  CRM: người gửi là tài khoản khách; tin gắn với máy F54 thuộc khách loại `official`. Câu này cần 3–4 query vì
  `created_by`/`customer_id` của tin nhắn không có khoá ngoại.
- Thay đổi: guide `crm_query` thêm luật: bản ghi đã nhắc ở lượt trước mà chưa có UUID thì không hỏi nhân viên UUID,
  lọc lại bằng cột chữ (trên bảng đó hoặc qua quan hệ từ bảng con); `tool_invalid_args` vì đặt chữ vào cột uuid
  sửa theo cách này. Test: `test_crm_query_tool.py` (1 test).
- Kiểm chứng: `pytest tests` → 1134 passed, 14 skipped, 1 failed có sẵn (`test_f86_baseline`, CSV CRLF).
- Chưa kiểm / mở tiếp: hỏi lại hai câu trên; Gói A (L2 `facts` lưu id bản ghi tool đã trả) mới giải gốc P1;
  (LC-2) hết giờ LLM: theo dõi, nếu lặp thì tăng `AGENT_LLM_TIMEOUT_S` hoặc thử lại một lần khi bước đầu hết giờ.

## 2026-11-20 · Vòng lặp agent dừng sớm theo tín hiệu tool, báo ngân sách, bước chốt có khung (Đợt 1 C1–C3) · loại: thay đổi

- Vấn đề: P3 của [kế hoạch Đợt 1](../../reports/crm_agent_dot1_plan_2026-11-20.md): vòng lặp chỉ dừng theo số bước,
  số lần gọi, deadline; chạm trần thì LLM hay trả "thử lại sau"; không có tín hiệu để hỏi lại khi mơ hồ.
- Thay đổi (theo kế hoạch đã duyệt Q1–Q5):
  - C1: `ToolSpec.progress(output) -> ok|empty|ambiguous`. `product_docs_ask`: `needs_clarification` → ambiguous,
    `no_docs` → empty. `crm_query`: 0 dòng → empty; `user_profiles` lọc `first_name`/`last_name contains` ra
    > 1 người không có `user_id.is_active=false` → ambiguous (khớp luật "trùng tên thì hỏi lại" của guide).
    Runner dừng khi: tool báo ambiguous; một tool rỗng/lỗi ở 2 bước liên tiếp (call song song cùng bước không
    tính); đã dùng ≥ 50% `AGENT_MAX_TOOL_CALLS` mà chưa có kết quả ok; tổng token vào của các bước LLM trong
    vòng lặp > `AGENT_TURN_INPUT_BUDGET` (mới, mặc định 15000, 0 = tắt; không tính analysis trong tool).
  - C2: mọi message role=tool kèm `turn_budget: {steps_left, tool_calls_left}`; phần token của khoá này được trừ
    khỏi budget trước khi tool tự cắt output.
  - C3: `final_reason` ∈ answered, limit, plateau, ambiguous, budget, no_answer ghi vào `AgentRun`, root span,
    span `agent.run`, `retrieval_snapshot` và `GET /retrieval` (trường mới, null với lượt cũ). Dừng không phải
    answered/no_answer thì chèn chỉ dẫn bước chốt: đã xác minh / chưa lấy được và lý do (cấm "thử lại sau") /
    một câu hỏi làm rõ 2–4 lựa chọn (bắt buộc khi ambiguous, trừ khi nhân viên chỉ cần danh sách).
- File: `agent/runner.py`, `agent/prompts.py`, `tools/base.py`, `tools/crm_query.py`, `tools/product_docs.py`,
  `schemas/system/agent.py`, `schemas/system/__init__.py`, `schemas/history.py`, `services/chat_service.py`,
  `services/turn_sources.py`, `core/config.py`; test mới `tests/chatbot/test_agent_loop_control.py` (16);
  `agent_fakes.tool_messages` bỏ `turn_budget` khi so nội dung (test cũ không đổi ý nghĩa).
- Kiểm chứng: `pytest tests` (worktree, `DATABASE_URL` giả) → 1133 passed, 14 skipped, 1 failed có sẵn
  (`test_f86_baseline`, CSV CRLF trong worktree); `check_ai_docs.py` đạt. Chưa kiểm trên server thật.
- Ảnh hưởng contract/API/schema/cấu hình: có. `GET /retrieval` thêm `final_reason` (bổ sung, không phá);
  biến mới `AGENT_TURN_INPUT_BUDGET` (Toma thêm vào `.env.example`); nội dung message tool gửi LLM có thêm
  `turn_budget`. Không cần SQL.
- Chưa kiểm / mở tiếp: lưu câu hỏi dở vào `facts` để lượt sau nối tiếp chờ Gói A; ngưỡng 15k và 50% là đề
  xuất, cần đo bằng `run_crm_agent_eval.py` (rủi ro: câu "liệt kê nhân viên tên X" giờ dừng ở bước tra tên,
  trả danh sách hoặc hỏi lại thay vì đi tiếp); Toma chạy 3–5 câu thật (CRM nhiều sale, tên trùng, model lạ)
  và kiểm `final_reason` trong `/retrieval`. Nhánh `claude/dot1-c` chưa merge.

## 2026-11-20 · Bộ câu so sánh C1–C7: cắt cột đạt cả 7 câu; lỗi còn lại do LLM gán nhãn và chọn bảng chung (D-014) · loại: kiểm chứng, đánh giá

- Dữ liệu: phiên `8de1e4b1…` 07:14–07:26 UTC và `97fa9b85…` 07:29 (website). Backend `14196d6`, Toma đặt
  hạn mức **3 + 2** qua env (mặc định trong code vẫn 2 + 4). Agent gpt-4.1-mini; pipeline gpt-4o-mini.
- Đáp án chấm: `doc_ingest/curated/selection_matrix.yaml` (Toma duyệt 2026-11-14), so dòng khác nhau giữa các
  model, cộng số trục điều khiển ở trang riêng của từng model.
- Kết quả từng câu (token vào / USD, 1 lần `product_docs_ask` ở mọi lượt agent):
  - C1 F54–F86 kèm tư vấn: 9.686 / 0,00331 (V4 2 + 4 cùng câu: 11.133 / 0,00429). 9/17 khác biệt; thiếu bảng
    Tool Manager, Multi axis (không lấy được); bỏ qua trục PLC, spindle đồng thời, block time dù có trong nguồn.
  - C2 F86–F10T kèm tư vấn: 11.256 / 0,00319 (V4: 3 lần gọi, 22.860 / 0,00486). Đủ 2/2; còn "F86 nhỏ gọn hơn".
  - C3 F10T–ASTRO-10S: 11.233 / 0,00353. Alias giữ đúng cột ASTRO-10S; đủ 4/4, không sai.
  - C4 F54, F86, F10T: 11.827 / 0,00351, 11 nguồn (~2.890 token, sát trần 2.968 của output tool). Giữ đúng 3 cột;
    không sai; phía F54 thiếu spindle đồng thời, Look-Ahead, block time, tuổi dao, đa trục.
  - C5 F86–F86E: 10.209 / 0,00253. F86E không có trong registry → 1 lần tra, không cắt cột, bảng 4 cột; không gán
    cột F86 cho F86E, nhưng **bịa** "F86E là bản mở rộng/nâng cấp".
  - C6 F54 hay F86 cho máy 5 trục: 11.745 / 0,00233. Kết luận đúng theo 4/6 trục.
  - C7 F86–F54 qua pipeline: kênh CRM `flow=pipeline` 7.744 / 0,00108 (6 điểm); website 7.063 / 0,00085 (chỉ
    số trục, màn hình, RTCP, kèm câu "không có tài liệu chi tiết"). Chunk chung lấy Compensation (mọi dòng giống
    nhau) và Tool Manager hoặc Multi axis, không lấy General/Hardware như lượt agent.
- Lỗi hệ thống: "spindle đồng thời" bị gán giá trị "Max. Spindle" 1/2 (đúng là 2/4) ở **4/5** lượt F54–F86 (V4, C1,
  C6, C7 CRM), kể cả khi bảng General có dòng đúng trong nguồn → lỗi tổng hợp, không phải lỗi lấy chunk.
- Kết luận (chờ Toma chốt D-014): cắt cột bảng đạt ở cả 7 câu, kể cả alias, 3 model, model lạ, website; cột bị cắt
  chỉ là bản sao trong lượt, không ảnh hưởng lượt sau. Hạn mức 2 + 4 hay 3 + 2 không quyết định chất lượng; điểm
  quyết định là chọn **bảng nào** làm chunk chung.
- Chưa kiểm / mở tiếp: (CMP-1) chọn chunk chung theo số dòng khác nhau giữa các model được hỏi; (CMP-2) code tính
  sẵn danh sách khác/giống từ bảng đã cắt cột; (CMP-3) câu hỏi model không có tài liệu vẫn suy đoán; (CMP-4) so
  từ 4 model sẽ vượt trần output tool. Chưa kiểm: cặp khác trang (F86–10i), cột chung "ASTRO 6AV/H", câu so sánh
  kèm "có dòng nào tốt hơn"; `run_retrieval_eval.py`. Toma chuyển sang bước 2 của kế hoạch Đợt 1 (C1–C3).

## 2026-11-20 · Phân loại lỗi câu so sánh: phần lớn do LLM tổng hợp, phần nhỏ do thiếu chunk · loại: đánh giá

- Cách kiểm: với 6 lượt so sánh 05:44–06:15 (phiên `fd5e7814…`), tính token từng nguồn đưa vào tool (tiktoken
  gpt-4.1-mini): 1.751–2.166 token, dưới ngân sách `AGENT_TOOL_OUTPUT_TOKENS=3000` → LLM nhận **đủ** mọi nguồn,
  không bị cắt. Sau đó đối chiếu từng lỗi với nội dung nguồn của lượt đó.
- Do LLM (nguồn có đủ dữ liệu), 9 lỗi: bỏ sót trục PLC 0 so với 6/8 (3 lượt, bảng General có), bỏ sót spindle
  đồng thời 2/4 (2 lượt), gán spindle 2 cho F86 (06:15), Look-Ahead xếp vào "Giống nhau" (05:59), dòng "Cả hai…"
  trong "Khác nhau" (06:15), "nhỏ gọn hơn" (05:45, 06:15), đọc nhầm cột bảng 4 cột (05:59, đã hết sau khi cắt cột).
- Do thiếu chunk, 4 lỗi: thiếu Tool Manager và Multi axis (05:44, cấu hình 3 + 2), thiếu Hardware nên mất "cảm ứng"
  F10T (05:45), thiếu Multi axis (05:59, 06:15 F54–F86): suất chunk chung chọn theo điểm tìm kiếm, lấy bảng giống
  nhau (Compensation, Operation) thay bảng có khác biệt.
- Không có trong tài liệu (trả lời "không có" là đúng): độ bền màn hình cảm ứng, giá.
- Đề xuất: (1) code tính sẵn dòng khác/giống từ bảng đã cắt cột, đưa vào output tool; (2) khi chọn chunk chung cho
  câu so sánh, ưu tiên bảng có dòng khác nhau giữa các model được hỏi.

## 2026-11-20 · Kiểm D-014 trên 2 câu so sánh kèm tư vấn: hết đọc nhầm cột, còn lỗi tổng hợp · loại: kiểm chứng

- Dữ liệu: phiên `fd5e7814…`, 06:15 UTC, gpt-4.1-mini, backend `0f69b58` (mặc định 2 + 4, cắt cột).
- Cắt cột chạy đúng: mọi bảng chọn model chỉ còn cột của hai model được hỏi.
- "So sánh F54 và F86, nên lấy con nào, F54 có yếu không": 1 lần gọi, 11.133 token vào (không cache),
  694 ra, 0,004292 USD, 15,4 s. Đúng: 4/6 trục, kích thước, màn hình, I/O, Look-Ahead 250/500 và thời gian
  xử lý block 250/500 (đã ở "Khác nhau"), tuổi dao, EtherCAT. Lỗi: câu spindle ghi "F86 … đồng thời 2 spindle,
  F86 … 4" (2 là của F54); vẫn bỏ sót trục PLC 0 so với 6/8. Tư vấn chọn model dựa vào số trục, có điều kiện.
- "F86 khác gì F10T, cảm ứng có bền không, bằng giá nên chọn cái nào": 3 lần gọi trong một bước (2 lần so sánh
  gần trùng + 1 `handoff` về giá), 22.860 token vào (cache 15.488), 0,00486 USD, 9,7 s. Hết lỗi đọc nhầm cột
  (bảng General của F86/F10T giống nhau, không còn gán sai); độ bền cảm ứng nói rõ tài liệu không có; giá chuyển
  bộ phận kinh doanh. Lỗi: dòng "Cả hai đều…" nằm trong "Khác nhau"; còn "kích thước nhỏ gọn hơn thì chọn F86".
- Chưa chạy: C3 (ASTRO-10S), C4 (3 model), C5 (F86E), C7 (website).
- Kết luận: cắt cột bảng đạt mục tiêu; hạn mức 2 + 4 vẫn tạm (câu F54–F86 lấy bảng Compensation giống nhau,
  thiếu Multi axis). Lỗi còn lại là bước tổng hợp của LLM. Đề xuất: code tính sẵn dòng khác/giống từ bảng đã cắt
  cột và đưa vào output tool; gộp lần so sánh trùng model trong cùng lượt.

## 2026-11-20 · So sánh: cắt cột bảng theo model được hỏi, mặc định 2 + 4 (quyết định tạm D-014) · loại: thay đổi, quyết định

- Vấn đề: kiểm thật 2 + 4 (mục bên dưới): bảng chọn model 4 cột làm LLM ghi giá trị cột F54 cho F86;
  "Thời gian xử lý block 500/500" xếp vào "Khác nhau"; vẫn bỏ sót dòng của bảng General.
- Quyết định (Toma, 2026-11-20): làm cả hai (cắt cột + mặc định 2 + 4), **đánh dấu tạm** để kiểm trên các
  câu sau ([D-014](../../decisions.md); bộ câu C1–C7: [kế hoạch](../../reports/crm_agent_dot1_plan_2026-11-20.md) mục 9).
- Thay đổi (commit `15c9c6e`, nhánh `claude/dot1-e-d`):
  - `retrieval/table_columns.py` (mới) `trim_model_columns`: cột có tiêu đề chỉ ra đúng một model của
    registry (mã/alias, vd ASTRO-10S → 10S) mà không thuộc model được hỏi thì bị bỏ; cột khác giữ; bảng lệch
    số cột hoặc không có cột của model được hỏi giữ nguyên. `Retriever` chỉ áp khi so sánh.
  - Mặc định `RETRIEVAL_COMPARE_PER_MODEL=2`, `RETRIEVAL_COMPARE_SHARED=4` (`config.py`, `RetrieverConfig`).
  - Guide `product_docs_ask`: so từng cặp trước khi xếp "Khác/Giống"; đọc theo tiêu đề cột, đọc hết dòng
    bảng; không kết luận "lớn/nhỏ/gọn hơn" từ nhiều số đo.
- File test: `test_retrieval.py` (+4). Kiểm chứng: `pytest tests` → 1117 passed, 14 skipped, 1 failed có sẵn
  (CSV CRLF). Mức chín: code + test fake.
- Ảnh hưởng: mặc định retriever so sánh đổi cho cả website (website-qa LOG); D-014 mới.
- Chưa kiểm / mở tiếp: chạy C1–C7; Toma có thể bỏ hai biến trong `.env` để dùng mặc định mới.

## 2026-11-20 · Thử so sánh 2 chunk riêng + 4 chunk chung: nguồn đa dạng hơn, lộ lỗi đọc nhầm cột bảng · loại: kiểm chứng

- Dữ liệu: phiên `fd5e7814…`, 05:59 UTC, gpt-4.1-mini, `.env` của Toma đặt `RETRIEVAL_COMPARE_PER_MODEL=2`,
  `RETRIEVAL_COMPARE_SHARED=4` (code mặc định vẫn 3 + 2).
- Nguồn: bỏ được hai trang tóm tắt lặp lại; mỗi câu có tổng quan + thông số của từng model và 4 mục bảng
  chọn model (F86–F54: Hardware, General, Tool Manager, Operation; F86–F10T: Hardware, General, Tool
  Manager, Multi axis). Token: 10.876 và 11.175 vào; 0,003566 và 0,003395 USD; 1 lần gọi tool mỗi câu.
- "F86 khác F54": thêm đúng quản lý tuổi dao; đã tách "Khác nhau"/"Giống nhau". Vẫn bỏ sót số trục PLC
  (0 so với 6/8) và spindle đồng thời (2 so với 4) trong bảng General; xếp Look-Ahead 500/250 vào "Giống nhau".
- "So sánh F86 và F10T": **sai số liệu do đọc nhầm cột**: "F86 không có trục PLC", "spindle đồng thời F86 là 2"
  lấy từ cột F54; bảng General ghi F86 và F10T giống hệt nhau (6, tùy chọn 8; 4 spindle). "Thời gian xử lý
  block 500 so với 500" bị xếp vào "Khác nhau". Màn hình cảm ứng của F10T đã có.
- Nhận định: bảng chọn model có 4 cột (F54, F86, F10T, ASTRO-10S); khi so sánh 2 model, các cột thừa làm
  LLM gán nhầm cột. Đề xuất: khi so sánh, cắt bảng chỉ còn cột tên thuộc tính và cột của các model được hỏi;
  guide: dòng nào giá trị giống nhau thì không đưa vào "Khác nhau". Chờ Toma quyết.

## 2026-11-20 · Kiểm lại so sánh với gpt-4.1-mini: một lần gọi, đủ thông số chính · loại: kiểm chứng

- Dữ liệu: phiên `fd5e7814…`, 05:44–05:45 UTC, `AGENT_MODEL=gpt-4.1-mini`, backend `f8fc979`.
- "F86 khác F54": 1 lần `product_docs_ask`, 8 nguồn (đủ chunk tổng quan hai model); 11.996 token vào
  (cache 6.272), 560 ra, 0,003356 USD, 11,2 s. Đúng nguồn: 6/4 trục, EtherCAT, kích thước, màn hình,
  I/O, spindle 2/1, Look-Ahead 500/250, điểm giống nhau. Thiếu quản lý tuổi dao, đa trục tùy chọn (bảng
  Tool Manager/Multi axis không vào 2 suất chung lần này).
- "So sánh F86 và F10T": 1 lần gọi, 11.811 token, 557 ra, 0,003294 USD, 9,0 s. Đúng nguồn (kể cả RTCP
  tùy chọn), trừ suy luận "F10T nhỏ gọn hơn F86" (F10T ngắn hơn nhưng rộng, dày hơn); thiếu "cảm ứng".
- Cả hai chưa tách mục "Khác nhau"/"Giống nhau" nhưng mỗi dòng ghi rõ "cả hai" hoặc giá trị từng model.
- Kết luận: G4 đạt trừ một suy luận kích thước tổng hợp; G5 sát ngưỡng (11,8–12,0k). Mở tiếp: guide cấm
  kết luận "lớn/nhỏ/gọn hơn" từ nhiều số đo; cân nhắc `RETRIEVAL_COMPARE_SHARED=3`.

## 2026-11-20 · Kiểm thật bản sửa so sánh (`f8fc979`): đủ số trục, nhưng chạy gpt-4o-mini · loại: kiểm chứng

- Dữ liệu: phiên `fd5e7814…`, 2 lượt 05:38–05:39 UTC; **`AGENT_MODEL` vẫn là gpt-4o-mini** (đặt khi kiểm G2),
  không phải model mục tiêu gpt-4.1-mini.
- Chọn chunk đúng thiết kế: lần so sánh trả 8 nguồn, có chunk tổng quan "6 AXIS"/"4 AXIS" của từng model.
- "F86 khác F54": đủ số trục 6/4, kích thước, màn hình, I/O, [S#] sau từng giá trị. Nhưng agent gọi
  `product_docs_ask` 4 lần trong 3 bước (2 lần bị từ chối `based_on_sources` dùng S# của lượt trước, rồi
  so sánh + tra riêng F54): 19.051 token vào, 0,002931 USD, 24,5 s. Thiếu spindle 2/1, quản lý tuổi dao,
  đa trục tùy chọn (có trong chunk); không tách "Khác nhau"/"Giống nhau".
- "So sánh F86 và F10T": 1 lần gọi, 11.774 token, 0,001589 USD, 8,2 s; đúng nguồn, hết "µs", [S#] theo giá
  trị. Sai một suy luận: "F86 có kích thước tổng thể lớn hơn" (326×185×30 so với 254×195×40: F86 dài hơn,
  hẹp hơn, mỏng hơn). Thiếu "cảm ứng" của F10T; không tách "Khác nhau"/"Giống nhau".
- Mở tiếp: kiểm lại với `AGENT_MODEL=gpt-4.1-mini`; guide cấm suy luận so sánh tổng hợp (lớn/nhỏ hơn) từ
  nhiều số đo; cân nhắc chặn bằng code lần tra riêng một model đã có trong lần so sánh cùng lượt.

## 2026-11-20 · Câu so sánh: chunk riêng của từng model không còn bị bảng chung đẩy ra · loại: thay đổi

- Vấn đề: kiểm thật (mục cùng ngày bên dưới) thiếu số trục/kích thước F86–F54: chunk chung (bảng chọn
  model, khớp cả hai model, điểm cao) chiếm hết hạn mức của mỗi model; [S#] chỉ gom ở cuối; tự thêm "µs".
- Thay đổi (commit `a627bd8`, nhánh `claude/dot1-e-d`): `Retriever._select_comparison`:
  chunk khớp ≥ 2 model là chunk chung; mỗi model giữ `RETRIEVAL_COMPARE_PER_MODEL` (3) chunk riêng, xen kẽ;
  chunk chung giữ `RETRIEVAL_COMPARE_SHARED` (2) + suất riêng chưa dùng. Guide `product_docs_ask`: [S#] ngay
  sau từng giá trị, tách "Khác nhau"/"Giống nhau", mở đầu bằng số trục/giao tiếp/kích thước, không thêm
  đơn vị nguồn không ghi.
- Kiểm chứng: `pytest tests` → 1113 passed, 14 skipped, 1 failed có sẵn (CSV CRLF). Mức chín: code + test fake.
- Ảnh hưởng: biến mới `RETRIEVAL_COMPARE_SHARED` (deploy-rules); website so sánh dùng chung cách chọn.
- Chưa kiểm / mở tiếp: Toma hỏi lại "F86 khác F54 thế nào?", "So sánh F86 và F10T"; `run_retrieval_eval.py`.

## 2026-11-20 · Kiểm thật gói E+D: so sánh một lần gọi, token giảm 63%, còn thiếu số trục · loại: kiểm chứng

- Dữ liệu: phiên `fd5e7814…`, backend local chạy `5685901`, đọc qua `/history`, `/trace`, `/retrieval`.
- "F86 khác F54 thế nào?" (gpt-4.1-mini): 1 lần `product_docs_ask` (trước 3), 8.324 token vào (trước
  22.804), 0,00267 USD. Đối chiếu toàn văn 6 chunk: mọi ý đúng nguồn (EtherCAT, spindle 2/1, Look-Ahead
  500/250, I/O, tuổi dao, màn hình). **Thiếu số trục 6/4 và kích thước**: 6 chunk là bảng chọn model và
  trang thông số, không có chunk tổng quan "BỘ ĐIỀU KHIỂN n AXIS" của từng model.
- "So sánh F86 và F10T": 1 lần gọi, 10.530 token; nội dung đúng nguồn, trừ đơn vị "µs" của Block
  Processing Time (bảng không ghi đơn vị) và mục "Khác biệt" lẫn thuộc tính giống nhau.
- Cả hai câu chỉ ghi [S1]…[S6] ở cuối, chưa trích theo từng thuộc tính như guide yêu cầu.
- "F54 có bao nhiêu trục" (gpt-4o-mini, câu lặp lại): gọi tool ngay bước 1, đúng "4 trục" [S2][S3];
  đường ép gọi tool (`forced_tool_call`) chưa phát sinh nên chưa kiểm thật được.
- Một lượt lỗi 401 `invalid_api_key` lúc khởi động lại backend (cấu hình khóa), lượt gửi lại thành công.
- Kết luận theo kế hoạch: G4 đạt một phần (1 lần gọi, không kết luận sai; thiếu số trục), G5 đạt, G2 đạt
  trên mẫu này. Mở tiếp: thử `RETRIEVAL_COMPARE_PER_MODEL=4` hoặc ưu tiên chunk tổng quan khi so sánh;
  guide: trích nguồn theo thuộc tính, không thêm đơn vị không có trong nguồn.

## 2026-11-20 · Đợt 1 gói E+D: câu so sánh gọi một lần, bắt buộc tra nguồn · loại: thay đổi

- Vấn đề: P5 (câu "F86 khác F54" gọi tool 3 lần, 22,8k token, kết luận sai bù rơ/PLC/ATC) và lượt
  "F54 có bao nhiêu trục" (gpt-4o-mini) trả lời từ lịch sử, không có nguồn ([kế hoạch](../../reports/crm_agent_dot1_plan_2026-11-20.md)).
- Thay đổi (commit `ccc5f5a`, nhánh `claude/dot1-e-d`):
  - Gói E: retriever giữ `RETRIEVAL_COMPARE_PER_MODEL=3` chunk/nhóm mỗi model khi so sánh; mô tả
    `product_docs_ask` yêu cầu so sánh gọi MỘT lần; guide thêm khung so sánh theo thuộc tính, chỉ nói
    "khác" khi cả hai giá trị có nguồn, đọc ✓/✗/(Option) của bảng chọn model.
  - Gói D: `ToolSpec.requires_call`; `AgentRunner` bỏ câu trả lời không gọi tool nào khi có trích nguồn
    không hợp lệ hoặc tool khai báo `requires_call` khớp tin nhắn (`product_docs_ask`: nhắc model trong
    registry), chạy lại một bước `tool_choice="required"` (ép một lần, như `reset_tool_choice`). Root
    span `forced_tool_call`. `ToolChoice` thêm `required`.
- File: `retrieval/retriever.py`, `core/config.py`, `tools/{base,product_docs}.py`,
  `agent/{runner,prompts}.py`, `schemas/system/agent.py`; test `test_retrieval.py` (+2),
  `test_agent_guards.py` (+3, sửa 1).
- Kiểm chứng: từ `backend/`, `pytest tests` → 1112 passed, 14 skipped, 1 failed có sẵn (CSV CRLF trong
  worktree). Mức chín: code + test bằng fake.
- Ảnh hưởng: biến mới `RETRIEVAL_COMPARE_PER_MODEL` (deploy-rules); hành vi website so sánh đổi (website-qa
  LOG cùng ngày). Không đổi HTTP/SSE.
- Chưa kiểm / mở tiếp: chưa merge; Toma kiểm thật G2/G4/G5 (5 câu so sánh, câu lặp lại với gpt-4o-mini) và
  `run_retrieval_eval.py`; bước tiếp theo C1–C3.

## 2026-11-20 · Duyệt kế hoạch Đợt 1 (Q1–Q5) · loại: quyết định

- Quyết định (duyệt: Toma, 2026-11-20; căn cứ: [kế hoạch](../../reports/crm_agent_dot1_plan_2026-11-20.md) mục 7):
  - Q1 thứ tự: E + D → C1–C3 → A → B → C4 → đo ngưỡng chunk;
  - Q2 lưu username/id nhân viên, id khách trong `conversation_state.facts`, chỉ từ output tool, TTL 10 lượt;
  - Q3 kiểm nguồn gốc bắt đầu `CRM_QUERY_PROVENANCE=warn`, 1–2 tuần sau chuyển `reject`;
  - Q4 ngưỡng khởi đầu: 3 lượt agent, 10 lượt đọc DB, 15k token/lượt, 50% ngân sách, 3 chunk/model khi so sánh;
  - Q5 tóm tắt cuộn và dùng lại nguồn lượt trước dời sang Đợt 2.
- Mở tiếp: Toma chạy eval mốc trước khi merge Đợt 1.

## 2026-11-20 · Kế hoạch Đợt 1: context phiên, điều khiển vòng lặp, nguồn và so sánh · loại: đánh giá

- Vấn đề: P1–P6 ([kế hoạch](../../reports/crm_agent_dot1_plan_2026-11-20.md) mục 1): kết quả tool và
  định danh không lưu qua lượt; nạp toàn bộ history; chạm trần trả "thử lại sau"; định danh không kiểm
  nguồn gốc; câu so sánh gọi 3 lần mà sai; ngưỡng chunk cosine 0,25 chưa đo.
- Đề xuất: 5 gói (A context ba lớp, B kiểm nguồn gốc `warn`→`reject`, C tín hiệu dừng + bước chốt có
  cấu trúc + fan-out, D bắt buộc tra nguồn, E so sánh theo hạn mức từng model), tiêu chí G1–G6,
  thứ tự triển khai; tham khảo Agents SDK, Anthropic, LangGraph, OpenAI Cookbook.
- Chưa kiểm / mở tiếp: chờ Toma duyệt Q1–Q5; Toma chạy eval mốc trước khi bắt đầu.

## 2026-11-20 · Đợt 0 hoàn tất trên nền B3: model của agent, sổ usage, cached tokens, luật username (E1) · loại: thay đổi

- Vấn đề: sau B3 (D-013, chat-platform LOG 2026-11-18), nhánh chính còn thiếu bốn điểm của Đợt 0:
  history ghi `OPENAI_MODEL` cả ở lượt agent; usage cộng từ span nên mất khi vượt
  `CHAT_TRACE_MAX_SPANS`, lời gọi hết giờ/bị huỷ không được tính; bước agent không ghi cached tokens;
  guide `crm_query` chưa cấm tự suy username.
- Quyết định: Toma yêu cầu làm tiếp Đợt 0 trên nền B3 (2026-11-20). Giữ `core/pricing.py`,
  `LLM_PRICES_JSON`, `turn_usage.py` của B3; bỏ bản Đợt 0 cũ trên nhánh
  `claude/agent-crm-development-29f518` (commit `e8223e9`, `8351d71`: trùng B3, không merge).
- Thay đổi (commit `e77f08e`, nhánh `claude/dot0-on-b3` tách từ `6e1f465`):
  - `core/tracing.py`: `UsageEntry`, `Trace.usage`, `record_usage`; `usage_by_model` đọc sổ (sổ rỗng
    thì đọc span như cũ), thêm `estimated_calls`.
  - `providers/openai.py`: mọi lời gọi ghi sổ qua `_metered`; hết giờ, bị huỷ, stream ngắt → mục ước
    tính; lỗi HTTP/kết nối không ghi. `chat_complete_tools` đọc cached tokens, ghi lên span
    `llm.chat_tools` của runner.
  - `services/turn_usage.py`, `turn_sources.py`, `schemas/history.py`: `estimated_calls` trong
    `retrieval_snapshot.usage` và `usage` của `/history`.
  - `services/chat_service.py`: `_turn_model` → `AgentRunner.model` ở lượt CRM chạy agent (3 nhánh
    ghi history và `snapshot.model`).
  - `tools/crm_query.py`: luật "username, mã, UUID chỉ dùng nguyên văn từ kết quả tool…".
  - Test: `test_usage_ledger.py` (mới, 8), `test_retrieval_snapshot.py` (fake service).
- Kiểm chứng: từ `backend/`, `pytest tests` → 1107 passed, 14 skipped, 1 failed có sẵn
  (`test_f86_baseline`, CSV CRLF trong worktree). Mức chín: code + test bằng fake.
- Ảnh hưởng contract/API/schema/cấu hình: `/history` thêm `usage.estimated_calls` (chỉ thêm);
  `model` của lượt agent đổi sang `AGENT_MODEL`. Không biến môi trường mới, không SQL.
- Chưa kiểm / mở tiếp: chưa merge; chưa chạy trên server thật; chưa eval tác động của luật username.

## 2026-11-20 · Lượt thật trên kênh CRM: pipeline vs agent, chất lượng câu trả lời F86/F54 · loại: kiểm chứng

- Dữ liệu: phiên `c999efd3…`, đọc qua `/chatbot/sessions/{id}/trace|retrieval` của backend local.
- Hai lượt F86 (2026-11-19 22:41, 22:52) chạy `flow=pipeline` (backend lúc đó đặt
  `CRM_CHAT_FLOW=pipeline`): "các trục" đúng ý (6 trục) nhưng tên trục X–C lấy từ lịch sử, không
  có nguồn; "cấu hình, cách sử dụng" chỉ có Installation Manual F86, phần "cách sử dụng" không có
  trong tài liệu; 4/6 chunk chỉ là tiêu đề trang hình (doc-ingest).
- Lượt F54 (2026-11-19 23:08) sau khi bật lại agent: `flow=agent`, 2 bước LLM + 1
  `product_docs_ask`, đúng "4 trục" [S2][S3]; 9.914 token vào (analysis trong tool 5.107, không
  cache), 9,2 s, một `delta`.
- Mở tiếp: E7/E8 (giảm prompt analysis), doc-ingest gộp chunk chỉ có tiêu đề; nạp tài liệu vận hành F86.
