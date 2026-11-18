# Truy vết luồng thực thi crm-agent (2026-11-16)

Phạm vi: code trên `feature/deploy_ai_service`, commit `671fe22`. Báo cáo chỉ mô tả cái code
đang chạy, không dựa vào kiến trúc dự kiến. Mọi đường dẫn tính từ `backend/app/modules/chatbot/`
trừ khi ghi khác. Trạng thái và tồn đọng chi tiết: [STATE.md](../flows/crm-agent/STATE.md).

> **Cập nhật sau đợt dọn cùng ngày (D-010):** phương án A (`crm_report`, `crm_records`, `CRM_TOOLS`)
> đã xoá; `crm_credential`/`query_all` chuyển sang `tools/crm_common.py`; T1 và T4 ở mục 6 đã xử lý.
> Số dòng trong báo cáo vẫn theo commit `671fe22`.

## 1. Kiến trúc tổng thể

Luồng **thử nghiệm**. CRM backend gọi `POST /chat/crm` bằng service key. Dịch vụ AI chạy một
vòng lặp tool-calling (OpenAI) và trả câu trả lời qua SSE.

```text
CRM backend ──service key──▶ FastAPI route (routers/chat.py)          transport
                               │ auth, session, lease, trace
                               ▼
                         ChatbotService.stream_reply                    orchestration lượt
                         (services/chat_service.py)
                         security → context → prune → [agent | pipeline] → ghi history
                               ▼
                         AgentRunner.run (agent/runner.py)              vòng lặp agent
                               │ provider.chat_complete_tools ◀──▶ ToolRegistry.invoke
                               ▼
              ┌────────────────┼──────────────────┬───────────────────┐
     product_docs_ask     crm_schema          crm_query         (crm_report / crm_records:
     (RetrievalPipeline   (CrmSchemaCache)    (compile_raw +     phương án A, đã xoá
      của website-qa)                          policy)           2026-11-16, D-010)
              │                 └───────── providers/crm_api.py ─────────┘
           Supabase                             CRM Reporting API (Bearer token nhân viên)
```

| Tầng | File | Trách nhiệm |
|---|---|---|
| Wiring lúc khởi động | `app/main.py:38-57`, `agent/setup.py` | Chỉ dựng agent khi `CRM_CHAT_FLOW=agent` và có OpenAI. `AGENT_MODEL` khác `OPENAI_MODEL` thì tạo provider riêng cho vòng lặp. Đăng ký `crm_schema` + `crm_query` khi `CRM_REPORT_ENABLED` (`CRM_TOOLS` đã bỏ, D-010). Thiếu capability hoặc schema sai thì `ToolConfigurationError` dừng khởi động |
| Transport | `routers/chat.py`, `routers/sse.py`, `dependencies.py` | Xác thực, phiên, lease, trace, SSE, ánh xạ lỗi |
| Lượt chat | `services/chat_service.py` | Security, nạp context, prune, rẽ nhánh agent/pipeline, ghi `chat_history` |
| Agent | `agent/runner.py`, `prompts.py`, `deadline.py` | Vòng lặp, giới hạn, deadline, gộp call trùng, lọc citation |
| Tool | `tools/base.py`, `registry.py`, `schema.py`, `tools/*.py` | Contract `ToolSpec`, validate input, timeout, quy mọi lỗi về mã |
| Truy vấn CRM (C) | `reporting/raw/` (`compile`, `policy`, `values`, `schema`, `hints`, `audit`) | Dịch `RawQuery` ra body Reporting API, chặn bảng/cột, áp luật ngày và luật nghiệp vụ |
| Client ngoài | `providers/openai.py`, `providers/crm_api.py` | Gọi LLM; gọi CRM, ánh xạ HTTP ra mã lỗi |

## 2. Trình tự một request

1. **Middleware** (`app/api/middleware/request_context.py`) gắn `request_id` và mốc thời gian.
2. **Xác thực** (`dependencies.py:134-210`, `services/service_auth.py`).
   - Bearer service key được tra theo `key_id` và so hash secret.
   - Key bị thu hồi, hết hạn hoặc integration bị tắt trả **401** `invalid_service_key`; client luôn nhận cùng một 401 dù lý do nào.
   - Key cấp cho kênh khác trả **403** `service_key_channel_mismatch`; lỗi DB trả **503**.
   - Kết quả là `PrincipalContext` loại `service`.
3. **Gắn nhân viên** (`routers/chat.py:99`). `principal.acting_for(user_id, crm_access_token)` lấy hai giá trị này từ body. Token là `SecretStr` và bị loại khỏi `model_dump`, nên không đi vào snapshot hay history.
4. **Phiên** (`services/session_access.py`).
   - Request không có `session_id`: tạo phiên mới.
   - Có `session_id`: chỉ dùng lại khi khớp cả principal, tenant, `acting_user_id` và kênh, phiên chưa thu hồi và chưa hết hạn; ngược lại trả **404** `session_not_found`.
5. **Lease** (`SessionTurnLease`). Chỉ áp cho phiên đã có: mỗi phiên chỉ chạy một lượt một lúc, lượt thứ hai trả **409** `session_busy`. Lease được nhả trong `finally` của stream, có shield khi bị huỷ.
6. **Dựng `InboundRequest`** qua `adapters/crm.py`, rồi mở `StreamingResponse` (`routers/sse.py:81`) với header `X-Request-ID` và `X-Session-ID`.
7. **`ChatbotService.stream_reply`** (`chat_service.py:86`):
   1. `SecurityStage.inspect`: luật injection/nội dung, không gọi LLM. Tin bị chặn được ghi history `blocked` và client nhận SSE `error` `request_blocked`.
   2. `ContextLoader.execute`: đọc `chat_history` của phiên, dựng lịch sử user/assistant và `ConversationState` từ lượt hoàn tất gần nhất.
   3. `Prune`: cắt lịch sử theo `CONTEXT_TOKEN_BUDGET`.
   4. Nếu `ConversationState.mode` khác `BOT` (đã chuyển nhân viên): trả câu cố định và dừng.
   5. Kênh CRM có `agent_runner` thì chạy **`AgentRunner.run`**; không có thì chạy pipeline website-qa.
8. **`AgentRunner._run`** (`agent/runner.py:159`):
   1. Tạo `Deadline(AGENT_TURN_TIMEOUT_S)` và chờ slot `AGENT_MAX_CONCURRENT_RUNS` (semaphore trong tiến trình).
   2. `registry.allowed(principal)` lấy danh sách tool, `provider_tools()` chuyển chúng sang JSON Schema dạng `openai_strict`.
   3. `build_messages` ghép: system prompt chung, `<now>`, guide của các tool được phép, gợi ý ngôn ngữ, `AGENT_HISTORY_MESSAGES` tin gần nhất, rồi câu hỏi.
   4. Lặp tối đa `AGENT_MAX_STEPS` lần: gọi `chat_complete_tools(tool_choice="auto")`.
      - Không có tool call: có nội dung thì đó là câu trả lời; rỗng thì sang bước cuối.
      - Có tool call: chạy qua `_execute_unique`, mỗi `tool_call_id` nhận đúng một message `role=tool`.
   5. Bước cuối gọi `tool_choice="none"` khi hết bước, hết lượt tool, hết giờ hoặc lần đầu trả rỗng.
   6. `_drop_unknown_citations` bỏ `[S#]` không thuộc nguồn của lượt.
   7. Câu trả lời được trả về thành **một** chunk.
9. **Kết thúc lượt** (`chat_service.py:180-259`).
   - `update_agent_conversation_state` chỉ cập nhật `active_model`/`last_models` theo các lần gọi `product_docs_ask`.
   - Ghi `chat_history` `completed`, kèm `retrieval_snapshot` (`agent_steps`, `answered_without_tools`, `invalid_citations`).
   - SSE gửi `delta`, rồi `done`.
10. **Trace** (`routers/sse.py:116`): đóng trace, log một dòng `chat_trace` và lưu `public.chat_traces` khi `CHAT_TRACE_PERSIST=true`.

## 3. Cách agent dùng từng thành phần

| Thành phần | Thực tế trong code |
|---|---|
| **LLM** | `OpenAIProvider`, capabilities cố định: `parallel_tool_calls`, `openai_strict` (`providers/openai.py:19`). Có `AGENT_MODEL` thì vòng lặp dùng model đó; `AnalysisStage` bên trong `product_docs_ask` vẫn dùng `OPENAI_MODEL`. Model thường gửi `temperature=0` và `max_tokens`; model suy luận gửi `max_completion_tokens` và `reasoning_effort`. Không stream token. |
| **Context** | System prompt (`agent/prompts.py`) chứa luật chung, `<now>` đặt trước guide (sửa lỗi năm, 2026-11-12) và `<tool_guide>` riêng của tool được phép. Lịch sử là N tin cuối của `chat_history` sau prune. |
| **Memory** | Chỉ có memory hội thoại. Lịch sử đọc từ DB mỗi lượt. `ConversationState` lưu trong cột `conversation_state` của lượt cuối, agent chỉ ghi `active_model`/`last_models`. State riêng của tool trong một lượt nằm ở `AgentRun.tool_states`, ví dụ `QueryTurnState.crm_queries`, và mất khi hết lượt. Không có memory dài hạn: module learning chưa được nối. |
| **Tools** | `ToolSpec` khai báo `read_only`, `concurrency_safe`, `deduplicate`, `max_calls_per_turn`, `timeout_s`, `required_scope`, `on_invalid_args`. Call chạy song song (tối đa `AGENT_PARALLEL_TOOLS`, trong `TaskGroup`) chỉ khi mọi tool trong batch đều read-only và concurrency-safe. Output vượt `AGENT_TOOL_OUTPUT_TOKENS` thì `to_llm` cắt hoặc trả `tool_output_too_large`. |
| `product_docs_ask` | Chạy `RetrievalPipeline` (clarification → analysis → `CatalogLookupStage` → execution) trên một RunState con và không compose câu trả lời. Model trong câu hỏi phải có bằng chứng; không có thì trả `model_not_evidenced`. |
| `crm_schema` | Mô tả 1–4 bảng: cột, quan hệ, `known_values`, `person_filter`. Schema sống được cache `CRM_SCHEMA_CACHE_S`; index tĩnh dùng làm dự phòng. |
| `crm_query` | Validate `RawQuery`, rồi `compile_raw`: kiểm đường dẫn qua `policy.check_path`, kiểm kiểu giá trị, áp luật năm/kỳ, filter mặc định, `DROP_WITH_DATE_RANGE`. Sau đó gửi `POST /reports/query`, kèm một query `count` song song khi ở mode list. Trần mỗi lượt: 6 lần thử, trong đó 4 lần gửi CRM (`tools/crm_query.py:47-48, 267`). |
| **CRM client** | Header `Authorization: Bearer <crm_access_token>`; thiếu token thì dùng `acting_user_id` (`tools/crm_common.py` `crm_credential`). Ánh xạ: 401 → `crm_auth_failed`, 403 → `crm_forbidden`, 400 của query do LLM dựng → `crm_query_invalid` (LLM tự sửa), còn lại → `crm_unavailable`. |
| **Observability** | Span `agent.run`, `llm.chat_tools`, `tool.<name>`, `query.fetch`, `http.crm_report`. Log chỉ chứa metadata. Audit `crm_query` có giá trị filter nằm sau `CRM_QUERY_AUDIT_LOG`, mặc định tắt. |

## 4. Điều phối, phân quyền, xác thực, lỗi, handoff

**Điều phối.** Không có planner: LLM tự chọn tool ở mỗi bước, còn `AgentRunner.plan()` để trống. Code giữ các trần cứng:
- `AGENT_MAX_STEPS` (mặc định 6) và `AGENT_MAX_TOOL_CALLS` (mặc định 8). Call bị `tool_call_limit` không bị trừ vào trần chung.
- Trần riêng của từng tool (`max_calls_per_turn`).
- Deadline chung cho cả lượt, với `AGENT_FINAL_RESERVE_S` giữ lại thời gian cho bước trả lời cuối.
- Call trùng argument dùng lại kết quả thành công trước đó.
- `CancelledError` khi client ngắt luôn được truyền lên, không bị bắt thành lỗi tool.

**Xác thực.** Có hai lớp:
- Service key theo kênh xác thực hệ thống gọi tới.
- Nhân viên do CRM khẳng định qua `user_id` trong body; dịch vụ tin vì đã tin key.

**Phân quyền.**
- Phiên được ràng buộc theo `acting_user_id`.
- Tool: `registry.allowed()` lọc theo `required_scope`, nhưng **chưa tool nào khai báo scope và `principal.scopes` luôn rỗng**, nên mọi nhân viên dùng mọi tool.
- Dữ liệu CRM do CRM kiểm theo token; dịch vụ AI chỉ chặn bảng/cột trong `reporting/raw/policy.py`.

**Xử lý lỗi.** Có ba tầng:

| Tầng | Cơ chế |
|---|---|
| Trước khi stream | JSON `{"detail": {code, message, request_id}}`: 401, 403, 404 `session_not_found`, 409 `session_busy`, 503 `database_unavailable`, 503 `provider_not_configured` |
| Trong stream | SSE `error` (`routers/sse.py:151-202`): `request_blocked`, `context_error`, `analysis_error`, `agent_error` (`agent_timeout`, `agent_empty_answer`, `agent_context_missing`), `provider_error`. History ghi `error`; client ngắt thì history ghi `cancelled` bằng một ghi có shield |
| Trong tool | Không ném exception lên runner: `ToolRegistry.invoke` quy mọi lỗi về mã (`tool_invalid_args`, `tool_timeout`, `tool_failed`, `tool_call_limit`, `crm_*`…) và gửi lại cho LLM. Prompt yêu cầu LLM sửa argument tối đa một lần, hoặc trả lời phần đã có |

**Handoff.** Nhánh agent **không chuyển người thật**:
- `_transfer_handoff` chỉ chạy ở nhánh pipeline, với `DisabledHandoffProvider` mặc định (scaffold).
- `product_docs_ask` có thể trả status `handoff`; LLM chỉ hướng nhân viên tới bộ phận phụ trách.
- Phiên đã ở chế độ nhân viên (`Mode` khác `BOT`) thì bot trả câu cố định trước khi tới agent.

## 5. Quyết định đã duyệt gần nhất

| Ngày | Quyết định | Nguồn |
|---|---|---|
| 2026-11-10 | D-005: phương án C (`crm_schema` + `crm_query`) thay phương án A; mở mọi dữ liệu nghiệp vụ, chỉ chặn khóa và bí mật; dữ liệu CRM được phép đi tới nhà cung cấp LLM | [decisions.md](../decisions.md) |
| 2026-11-11 | D-006 (tạm thời): `CRM_CHAT_FLOW` mặc định `agent` dù luồng thử nghiệm; rollback bằng `pipeline` | decisions.md |
| 2026-11-12 | Hướng Y: dùng `AGENT_MODEL=gpt-4.1-mini`; sửa luật ngày/nghiệp vụ trong code thay vì prompt; "khách hàng" không tính spam; có kỳ thì bỏ `is_current`; "nhân viên <vai trò>" tính theo `user_roles`, chỉ tài khoản còn dùng | [LOG](../flows/crm-agent/LOG.md) |
| 2026-11-12 | Giới hạn gọi tool: trần chung chỉ đếm call thật chạy; `crm_query` 6 lần thử, 4 lần gửi CRM; không nới trần | LOG |
| 2026-11-12 | Giữ nguyên mô tả CRM của `product_user_access`, `product_agents` | STATE |

## 6. Tồn đọng

Phát hiện khi truy vết code, chưa có trong STATE:

| # | Vấn đề | Vị trí | Ảnh hưởng |
|---|---|---|---|
| T1 | `print()` debug in toàn bộ `AssistantTurn` (argument query), body gửi CRM và **toàn bộ response CRM (rows)** ra stdout | `agent/runner.py:289`; `providers/crm_api.py:199, 239, 255` | Vi phạm bất biến "log chỉ chứa metadata": PII khách hàng nằm trong log tiến trình ở mọi môi trường. **Đã gỡ 2026-11-16** |
| T2 | `chat_history.model` và chi phí ước tính lấy theo provider chung (`OPENAI_MODEL`) và đơn giá gpt-4o-mini, không theo `AGENT_MODEL` | `services/chat_service.py:232, 251, 384-399` | Khi đặt `AGENT_MODEL=gpt-4.1-mini`, history ghi sai model và chi phí thấp hơn thực tế khoảng 2,5 lần |
| T3 | `Prune` đếm token theo model của provider chung | `chat_service.py:137` | Lệch nhỏ khi model agent khác tokenizer |
| T4 | Mặc định trong dataclass `AgentLimits.max_steps = 5` khác `config.py` (6); `.env.example` đặt 5 | `agent/runner.py:75` | Chỉ gây nhầm khi dựng runner không qua settings (test, eval). **Code và `.env.example` đã sửa 2026-11-16** |

Đã có trong [STATE.md](../flows/crm-agent/STATE.md) (tóm tắt):
- Guide chưa có luật "username chỉ lấy nguyên văn từ kết quả tool".
- Chạm giới hạn vẫn có thể trả lời "thử lại sau".
- Bản ghi đầu/cuối theo từng người phải tách query.
- Chưa có case eval câu hỏi nhiều sale; chưa eval lại sau thay đổi giới hạn.
- Nghĩa "khách được hỗ trợ" của phiếu (r1) chưa chốt.
- Ranh giới ngày UTC (chờ CRM thêm `timezone`).
- Index tĩnh lệch 13 bảng.
- `contains` phân biệt dấu.
- Token CRM không được làm mới.
- Chưa phân quyền tool theo role/scope.
- Chưa có SSE tiến trình hay stream token.
- `.env.example` thiếu `AGENT_MODEL` (và còn biến đã bỏ `CRM_REPORT_MAX_ITEMS`); Toma đã sửa 2026-11-16.

## 7. Gợi ý cho bảo trì và mở rộng

- **Thêm tool:** input `extra="forbid"`, output kế thừa `ToolOutput`, khai báo trong `ToolSpec`, đăng ký ở `agent/setup.py`. Gọi CRM chỉ qua `providers/crm_api.py`. Runner không cần sửa.
- **Phân quyền:** gắn `required_scope` vào `ToolSpec` và nạp `scopes` cho principal ở `acting_for`. Điểm lọc đã có sẵn ở `registry.allowed()`.
- **Hiệu năng:** điểm nóng là số bước LLM (mỗi bước khoảng 4k token cố định) và số lần gọi CRM. Xem `crm_query_attempts`/`crm_query_outcomes` trên root span và lọc `chat_traces` theo hai trường này.
- **Chạy thử:** từ `backend/`, `.\venv\Scripts\python.exe -m pytest tests\chatbot`. Eval tay: `evals\run_crm_agent_eval.py`, cần `CRM_EVAL_ACCESS_TOKEN`.
