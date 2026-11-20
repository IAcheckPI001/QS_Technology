# Kế hoạch Đợt 1 crm-agent: context phiên, điều khiển vòng lặp, nguồn và so sánh (2026-11-20)

Trạng thái: **Toma duyệt Q1–Q5 theo đề xuất (2026-11-20)**. Bước 1 (Gói E + D) xong ở mức code + test
(commit `ccc5f5a`, nhánh `claude/dot1-e-d`, chưa merge), chờ kiểm thật.

- Nền: `feature/deploy_ai_service` `8261a79`, đã gồm Đợt 0.
- Nguồn đề xuất: [báo cáo thảo luận 2026-11-16](crm_agent_architecture_discussion_2026-11-16.md)
  (E2–E5), lượt kiểm thật 2026-11-19/20 ([LOG crm-agent](../flows/crm-agent/LOG.md)), và các tài
  liệu tham khảo ở mục 8.

## 1. Vấn đề cần giải quyết

| ID | Vấn đề | Bằng chứng |
|---|---|---|
| P1 | Kết quả tool, nguồn, định danh không được lưu qua lượt. Lượt sau chỉ thấy 6 tin chữ thô, nên agent suy lại username và trả lời lại từ lịch sử | LOG 2026-11-12 (username thiếu `@qstcnc.com`). Lượt "F54 có bao nhiêu trục" với gpt-4o-mini: `answered_without_tools`, 2 trích nguồn bị xoá |
| P2 | Nạp **toàn bộ** history của phiên mỗi lượt (190 tin), cắt theo số tin chứ không theo lượt; `summary` không dùng | `ContextLoader.list_for_context`, `Prune` (2.048 token), `AGENT_HISTORY_MESSAGES=6` |
| P3 | Chạm trần thì trả lời "thử lại sau"; không có tín hiệu nào để hỏi lại người dùng trước khi cạn ngân sách | LOG 2026-11-12; `runner.py` chỉ dừng theo số bước, số lần gọi, deadline |
| P4 | Giá trị định danh trong `crm_query` không được kiểm nguồn gốc | `compile_raw` chỉ kiểm kiểu |
| P5 | Câu so sánh gọi tool 3 lần (22,8k token) mà vẫn kết luận sai khác biệt (bù rơ, PLC, ATC) và bỏ sót khác biệt thật (EtherCAT, I/O, tuổi dao) | Lượt "F86 khác F54 thế nào?" 2026-11-19 |
| P6 | Ngưỡng chunk duy nhất là cosine ≥ 0,25 (config ghi "cần đo lại"); chunk chỉ có tiêu đề hình vẫn lọt | Lượt F86 "cấu hình" 2026-11-19 |

## 2. Mục tiêu đo được (điều kiện đóng Đợt 1)

| # | Tiêu chí | Cách đo |
|---|---|---|
| G1 | Eval `run_crm_agent_eval.py` (gpt-4.1-mini) **≥ mốc trước Đợt 1**, và không case nào trượt vì username sai | Toma chạy mốc trước khi merge Đợt 1, chạy lại sau |
| G2 | Câu nghiệp vụ không có trích nguồn hợp lệ: **0 lượt** trả lời mà không gọi tool | Test + 5 câu lặp lại thật (cả gpt-4o-mini và gpt-4.1-mini) |
| G3 | Chạm trần, chững lại, mơ hồ: câu trả lời có cấu trúc (đã xác minh / còn thiếu / câu hỏi làm rõ). Không còn "thử lại sau" | Test runner + case eval nhiều sale |
| G4 | Câu so sánh 2 model: **1** lần `product_docs_ask`; không kết luận khác biệt nào thiếu nguồn ở cả hai phía; nêu đủ các khác biệt có trong bảng chọn model | 5 câu so sánh thật (F54/F86, F86/F10T, …), Toma chấm |
| G5 | Câu so sánh ≤ khoảng 12k token vào (hiện 22,8k) | `usage` trong `/history` |
| G6 | Token vào của lượt agent không vượt trần lượt (đề xuất 15k), và DB chỉ đọc N lượt gần nhất | Trace, test |

## 3. Các gói việc

Ngưỡng ghi dưới đây là đề xuất ban đầu, đặt thành biến cấu hình và chỉnh sau khi đo.

### Gói A. Context phiên ba lớp (E3, giải P1, P2)

| Lớp | Thay đổi | Ngưỡng / cấu hình |
|---|---|---|
| L1. Hội thoại gần | `ContextLoader` chỉ đọc N lượt gần nhất (thêm `limit` ở `list_for_context`). Vòng lặp agent lấy history theo **lượt**, không tách câu hỏi khỏi câu trả lời | `CONTEXT_HISTORY_TURNS=10` (đọc DB, dùng chung với website-qa); `AGENT_HISTORY_TURNS=3` thay `AGENT_HISTORY_MESSAGES` (giữ biến cũ tương thích một bản) |
| L2. Trạng thái phiên có cấu trúc | Thêm `facts` vào `ConversationState`: `entities` (kind `person`/`customer`/`model`, nhãn, giá trị username/id/mã, tool tạo ra, số lượt) và `last_lookups` (tool, tóm tắt ≤ 200 ký tự: bảng, điều kiện, tổng, `source_id` + `chunk_id`). **Chỉ ghi từ output tool**, không từ câu trả lời của LLM. Đưa vào prompt agent dưới dạng `<session_state>` | ≤ 20 thực thể, ≤ 5 lookup, ≤ khoảng 500 token; mục không dùng sau 10 lượt bị xoá |
| L3. Tóm tắt cuộn | **Không làm trong Đợt 1**, chỉ ghi điều kiện kích hoạt cho Đợt 2: > 10 lượt hoặc history > 4k token | |

Cách ghi L2:
- `crm_query` có hàm thuần trích cặp tên ↔ username/id từ `rows`, khi `select` có cả cột tên và cột định danh (vd `user_profiles` + `user_id.username`).
- `product_docs_ask` ghi model và `source_id`/`chunk_id` của nguồn đã trả.
- `update_agent_conversation_state` gộp các mục này. `load_conversation_state` đã bỏ qua trường lạ hoặc hỏng, nên dữ liệu cũ không gây lỗi.

File:
- `schemas/system/run_context.py`, `stages/context_loader.py`, `repositories/history_repository.py`;
- `clarification/state_update.py`;
- `agent/runner.py` (`build_messages`), `agent/prompts.py`;
- `tools/crm_query.py`, `tools/product_docs.py`; `core/config.py`.

### Gói B. Kiểm nguồn gốc giá trị (E2, giải P4; cần Gói A)

- Trong `crm_query`, filter `eq`/`in` trên cột định danh (`*.username`, cột uuid, `code`) chỉ nhận giá trị thuộc một trong các nguồn sau:
  - giá trị trong rows của các lần gọi tool trước, cùng lượt (`QueryTurnState` thu thập);
  - `facts.entities` (L2);
  - `known_values`;
  - chuỗi có nguyên văn trong tin nhắn của nhân viên.
- Cờ `CRM_QUERY_PROVENANCE`:
  - `warn` (mặc định Đợt 1): vẫn gửi CRM; ghi `unverified_values` (chỉ số lượng, không ghi giá trị) lên span và audit.
  - `reject`: trả `tool_invalid_args` kèm hướng sửa ("tra `user_profiles` theo tên trước"), không tốn lượt gửi CRM.
- Đo ở chế độ `warn` 1–2 tuần (số lượt có `unverified_values` > 0, và query nào sau đó ra rỗng) rồi mới chuyển `reject`.
- File: `tools/crm_query.py`, `reporting/raw/compile.py` hoặc module mới `reporting/raw/provenance.py`, `reporting/raw/audit.py`.

### Gói C. Điều khiển vòng lặp và hỏi lại (E4, E5, giải P3)

1. **Tín hiệu do code phát hiện** (runner trung lập với tool):
   - `ToolSpec` thêm hook `progress(output) -> ok | empty | ambiguous`.
     - `crm_query`: `empty` khi 0 dòng; `ambiguous` khi tra người ra > 1 kết quả còn hoạt động.
     - `product_docs_ask`: `needs_clarification` → `ambiguous`; `no_docs` → `empty`.
   - Runner dừng sớm, chuyển sang bước chốt khi có một trong các điều kiện:
     - **mơ hồ**: một tool báo `ambiguous`;
     - **chững lại**: 2 kết quả `empty`/lỗi liên tiếp của cùng tool;
     - **cạn ngân sách**: đã dùng ≥ 50% số lần gọi mà chưa có kết quả `ok`;
     - **trần token lượt**: tổng token vào > `AGENT_TURN_INPUT_BUDGET` (đề xuất 15k).
2. **Báo ngân sách cho LLM:** mỗi message `role=tool` kèm số bước và số lần gọi còn lại.
3. **Bước chốt có cấu trúc** theo lý do dừng (`final_reason` ∈ `answered`, `limit`, `plateau`, `ambiguous`, `budget`), với chỉ dẫn riêng cho bước cuối:
   - phần đã xác minh (có [S#] hoặc số liệu từ tool);
   - phần chưa lấy được, và vì sao;
   - một câu hỏi làm rõ kèm 2–4 lựa chọn (bắt buộc khi `ambiguous`).

   Ghi `final_reason` vào `retrieval_snapshot.agent_*` và root span. Lượt kết thúc bằng câu hỏi thì lưu câu hỏi dở vào `facts` để lượt sau nối tiếp, theo mẫu "hỏi người dùng là kết thúc hợp lệ" (OpenClaw `ask_user`, LangGraph interrupt).
4. **Một lần gọi, nhiều query** (fan-out): `crm_query` thêm `split_by` (một cột, ≤ 5 giá trị). Code chạy song song mỗi giá trị một query `limit` nhỏ; cả nhóm tính **1 lần thử, 1 lượt gửi CRM**. Áp cho câu kiểu "bản ghi đầu tiên của từng sale".
5. Không thêm bước lập kế hoạch bằng LLM trong Đợt 1. `plan()` giữ làm điểm gắn; fan-out ở bước 4 thay cho phần lớn nhu cầu.

File: `agent/runner.py`, `agent/prompts.py`, `tools/base.py`, `tools/crm_query.py`, `tools/product_docs.py`, `schemas/system/agent.py`, `schemas/system/raw_query.py`, `core/config.py`.

### Gói D. Bắt buộc tra nguồn và đường ngoài phạm vi (E5b, giải một phần P1)

- **Luật bằng code:** lượt kết thúc mà **không gọi tool nào** và (câu trả lời bị xoá trích nguồn không hợp lệ **hoặc** câu hỏi nhắc mã model trong registry) → chạy lại một bước với `tool_choice="required"`, rồi bỏ ép ngay sau đó (như `reset_tool_choice` của Agents SDK). Chỉ chạy lại một lần.
- Không thêm cache câu trả lời giữa các lượt trong Đợt 1. Dùng lại nguồn của lượt trước (qua `last_lookups`) để Đợt 2 xét, sau khi đo Gói A.
- **Ngoài phạm vi:** giữ 4 điểm dừng hiện có (SecurityStage → agent bước 1 → analysis `out_of_scope`/`handoff` → `no_docs`). Ghi thêm root span `out_of_scope_stage` để đo tỉ lệ từng điểm.
- File: `agent/runner.py`, `extraction/registry.py` (chỉ đọc).

### Gói E. Câu so sánh (E5c, giải P5; chạm website-qa)

- **Retriever:** chế độ `comparison` chia hạn mức **theo từng model**, ví dụ 3 chunk mỗi model; luôn giữ chunk bảng chọn model (selection table) nếu khớp. Không còn cắt chung top 6 → 5 nhóm như hiện nay.
  - Biến mới: `RETRIEVAL_COMPARE_PER_MODEL=3`.
  - Áp cho cả pipeline website, nên phải chạy `run_retrieval_eval.py` (`dual_source`, `routing_intent`).
- **Guide `product_docs_ask` và mô tả tool:** câu so sánh gọi **một lần**, `question` nêu đủ các model.
- **Tổng hợp theo khung:** lập bảng thuộc tính → giá trị từng model, chỉ từ nguồn. Chỉ ghi "khác" khi cả hai giá trị có trích nguồn và khác nhau; giống thì ghi "giống". Không kết luận "nhiều hơn" khi thiếu nguồn.
- File: `retrieval/retriever.py`, `core/config.py`, `tools/product_docs.py`.

### Đo ngưỡng chunk (P6; website-qa, chỉ đo, chưa đổi)

- Chạy `run_retrieval_eval.py` với `RETRIEVAL_MIN_SIMILARITY` ∈ {0,25; 0,35; 0,45}, ghi Recall@k và số chunk chỉ có tiêu đề lọt vào top 5.
- Quyết định ngưỡng sau khi có số đo. Việc gộp chunk chỉ có tiêu đề thuộc doc-ingest.

## 4. Thứ tự triển khai

| Bước | Gói | Kiểm được không cần CRM | Phụ thuộc |
|---|---|---|---|
| 0 | Toma chạy eval mốc trước Đợt 1 (G1), đối chiếu `cost_usd` | – | – |
| 1 | E (so sánh) + D (bắt buộc tra nguồn) | Có | – |
| 2 | C1–C3 (tín hiệu, ngân sách, bước chốt có cấu trúc) | Có (một phần) | – |
| 3 | A (context ba lớp, L1 + L2) | Có (phần tài liệu) | – |
| 4 | B (kiểm nguồn gốc, chế độ `warn`) | Không | A |
| 5 | C4 (fan-out `split_by`) | Không | – |
| 6 | Đo ngưỡng chunk (P6) | Có | – |

Mỗi bước:
1. Tách nhánh riêng từ `feature/deploy_ai_service` và commit tại đó.
2. Chạy `pytest tests` và `check_ai_docs.py`; ghi nhật ký bằng skill `flow-log`.
3. Toma chạy 3–5 câu thật, agent đọc trace và history để đánh giá theo mục 2.
4. Merge khi đạt.

## 5. Ảnh hưởng contract, cấu hình, dữ liệu

- **Biến mới:** `CONTEXT_HISTORY_TURNS`, `AGENT_HISTORY_TURNS`, `AGENT_TURN_INPUT_BUDGET`, `CRM_QUERY_PROVENANCE`, `RETRIEVAL_COMPARE_PER_MODEL` (cập nhật `deploy-rules.md`, `.env.example`).
- **Schema tool:** `RawQuery` thêm `split_by` (OpenAI strict bắt điền mọi field, nên phải có giá trị null); output `crm_query`/`product_docs_ask` không đổi nghĩa.
- **History:** `conversation_state.facts` chứa username/id nhân viên và id khách (mục 7, Q2). `retrieval_snapshot` thêm `final_reason`. Không cần SQL (cột JSON có sẵn).
- **HTTP/SSE:** không đổi.

## 6. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Dừng sớm quá mức (chững lại / ≥ 50% ngân sách) làm giảm điểm eval | Ngưỡng là biến cấu hình; so eval trước/sau; tắt được từng tín hiệu |
| `facts` lưu sai định danh rồi dùng mãi | Chỉ ghi từ output tool; có số lượt và TTL 10 lượt; chế độ `warn` của E2 đo trước |
| Ép gọi tool (Gói D) làm câu chào hỏi tốn tiền | Chỉ kích hoạt khi có mã model hoặc trích nguồn bị xoá; chạy lại tối đa 1 lần |
| Đổi retriever so sánh làm lệch kết quả website | Chạy `run_retrieval_eval.py` trước khi merge |

## 7. Quyết định cần Toma duyệt

Kết quả: Toma duyệt cả năm mục theo cột "Đề xuất" (2026-11-20).

| # | Câu hỏi | Đề xuất |
|---|---|---|
| Q1 | Thứ tự mục 4 (E + D trước, B sau A) | Đồng ý thứ tự trên |
| Q2 | Lưu username/id nhân viên và id khách trong `conversation_state.facts` (nằm trong `chat_history`, như câu trả lời hiện nay theo D-005) | Cho phép, chỉ giá trị lấy từ output tool, TTL 10 lượt |
| Q3 | E2 bắt đầu ở chế độ `warn` hay `reject` | `warn` 1–2 tuần rồi `reject` |
| Q4 | Ngưỡng ban đầu: 3 lượt cho agent, 10 lượt đọc DB, 15k token mỗi lượt, 50% ngân sách, 3 chunk mỗi model khi so sánh | Dùng làm giá trị khởi đầu, chỉnh sau eval |
| Q5 | Tóm tắt cuộn (L3) và dùng lại nguồn lượt trước để sang Đợt 2 | Đồng ý dời |

## 9. Bộ câu kiểm cho quyết định tạm D-014 (so sánh)

D-014 (2 chunk riêng + 4 chunk chung, cắt cột bảng theo model được hỏi) mới kiểm trên 2 câu. Trước khi
chốt, chạy bộ câu dưới với `AGENT_MODEL=gpt-4.1-mini`; ghi kết quả vào LOG crm-agent (loại `kiểm chứng`).

| # | Câu | Phải có (đúng nguồn) | Lỗi cần bắt |
|---|---|---|---|
| C1 | F86 khác F54 thế nào? | 6/4 trục, EtherCAT, kích thước, màn hình, I/O, spindle 2/1, trục PLC 0 so với 6 (tùy chọn 8), spindle đồng thời 2/4, quản lý tuổi dao | Bỏ sót dòng bảng General; Look-Ahead xếp sai mục |
| C2 | So sánh F86 và F10T | Màn hình 8 so với 10,4 inch cảm ứng, kích thước từng chiều; trục PLC, spindle đồng thời **giống nhau** | Đọc nhầm cột; "nhỏ gọn hơn" |
| C3 | F10T và ASTRO-10S khác nhau gì? | Cột ASTRO-10S (trục PLC 14, I/O 16/16, kích thước 254×210×40) | Alias "ASTRO-10S" → 10S không giữ được cột |
| C4 | So sánh F54, F86 và F10T | 3 model trong một lần gọi, đủ cột của cả 3 | Một model thiếu chunk riêng |
| C5 | F86 và F86E khác nhau thế nào? | Nói rõ khi tài liệu không có F86E; không gán cột F86 cho F86E | Nhầm model gần tên |
| C6 | Nên chọn F54 hay F86 cho máy 5 trục? | Dựa trên số trục 4/6, không tự kết luận ngoài nguồn | Khuyến nghị không có nguồn |
| C7 | (website) So sánh F86 và F54 qua widget | Như C1, qua pipeline website | Lệch giữa website và agent |

Đạt khi: mỗi câu 1 lần `product_docs_ask` (agent), không có giá trị gán sai model, không bỏ sót dòng
khác biệt của bảng General/Tool Manager/Multi axis khi chunk có trong nguồn, token vào ≤ khoảng 12k.

## 8. Tham khảo

- OpenAI Agents SDK: [Running agents](https://openai.github.io/openai-agents-python/running_agents/) (`max_turns`, xử lý khi chạm trần), [Agents](https://openai.github.io/openai-agents-python/agents/) (`tool_choice`, `reset_tool_choice`, `tool_use_behavior`).
- OpenAI Cookbook: [Short-term memory management with sessions](https://developers.openai.com/cookbook/examples/agents_sdk/session_memory.md) (cắt theo lượt, tóm tắt có cấu trúc).
- Anthropic: [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) (điều kiện dừng, checkpoint cho người); [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (ghi chú có cấu trúc, compaction); [Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing); [Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool).
- LangGraph: [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts); [GRAPH_RECURSION_LIMIT](https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT). LangChain: [Plan-and-execute agents](https://www.langchain.com/blog/planning-agents).
- Aliannejadi et al. 2019, [Asking Clarifying Questions in Open-Domain Information-Seeking Conversations](https://arxiv.org/abs/1907.06554).
- OpenClaw (`ask_user`, memory flush), GoClaw (compaction): [báo cáo thảo luận 2026-11-16](crm_agent_architecture_discussion_2026-11-16.md) mục 1.
