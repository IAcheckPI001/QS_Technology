# Kiến trúc và luồng hiện tại

## Phạm vi hệ thống

Project gồm frontend React/Vite tại `src/`, backend FastAPI tại `backend/`,
và Supabase Cloud làm database. Backend là nơi điều phối chatbot; frontend
chỉ tạo request, đọc SSE và lưu `session_id`.

```text
Frontend
  -> FastAPI route/dependency
  -> ChatbotService
  -> SecurityStage
  -> ContextLoader (history + ConversationState)
  -> [mode ≠ bot] câu cố định agent.*, dừng
  -> Prune
  ├─ website, hoặc CRM khi CRM_CHAT_FLOW=pipeline (RetrievalPipeline):
  │   -> ClarificationResumeStage (deterministic, không LLM)
  │   -> AnalysisStage -> OpenAIProvider (bỏ qua nếu đã resume)
  │   -> ExecutionStage -> ExecutionScheduler -> handlers (retrieve -> Retriever -> match_doc_chunks)
  │   -> câu cố định (chitchat/out_of_scope/handoff-only) | AnswerComposer -> OpenAIProvider.stream_chat
  │   -> HandoffProvider (disabled) + update_conversation_state
  └─ CRM (mặc định, xem "Luồng agent"):
      -> AgentRunner ⇄ OpenAIProvider.chat_complete_tools ⇄ ToolRegistry
         -> product_docs_ask = RetrievalPipeline trên RunState con
            (clarification -> analysis -> CatalogLookupStage -> execution, không compose)
         -> crm_report (khi CRM_REPORT_ENABLED) = ReportQuery -> validate -> theo nguồn dataset:
            list_api: API danh sách -> engine tổng hợp | report_api: compile -> POST /reports/query
            -> ghép kết quả (Bearer crm_access_token | acting_user_id) -> ReportOutput
         -> crm_records (cùng cờ) = RecordQuery -> whitelist cột -> trang <= 20 dòng + tổng
  -> HistoryRepository -> Supabase public.chat_history
  -> SSE về frontend
```

## Startup và dependency

`backend/app/main.py` cấu hình logging, tạo FastAPI app, đăng ký CORS, include
`backend/app/api/v1/router.py` và bọc ngoài cùng bằng `RequestContextMiddleware`
(request ID, access log có `outcome`). Lifespan tạo `OpenAIProvider` khi có
`OPENAI_API_KEY`, lưu provider vào `app.state` và đóng provider khi shutdown.
Khi `CRM_CHAT_FLOW=agent` (mặc định), lifespan dựng thêm `AgentRunner`
(`agent/setup.py`): đăng ký tool, kiểm tra capability của provider và schema
của từng tool. Thiếu capability hoặc schema không hợp lệ thì **dừng khởi động**
(`ToolConfigurationError`), không để lỗi xuất hiện giữa lượt chat.

Module chatbot (`backend/app/modules/chatbot/`):

```text
routers/      chat.py (POST /chat/*), workspace.py (GET /chatbot/*), sse.py (SSE + map lỗi)
dependencies.py  service/repository, RequestContext, auth theo kênh, Idempotency-Key
services/     chat_service.py (ChatbotService), session_access.py (+ SessionTurnLease), service_auth.py
adapters/     website.py, crm.py: schema kênh -> InboundRequest
repositories/ history_repository.py, chat_session_repository.py (+ ChatTurnLeaseRepository), doc_chunk_repository.py,
              trace_repository.py (public.chat_traces)
stages/       ... + retrieval_pipeline.py (clarification -> analysis -> [catalog] -> execution, dùng chung)
              catalog_lookup_stage.py (tìm model theo bảng capabilities, chỉ pipeline của agent)
extraction/   registry.py (intents, models, coverage, capabilities), validate_registry.py, product_catalog.py
agent/        runner.py (AgentRunner), deadline.py, prompts.py, setup.py
tools/        registry.py (ToolRegistry), schema.py (chuẩn hóa JSON Schema), base.py, product_docs.py,
              crm_report.py, crm_records.py
reporting/    catalog.py (DatasetSpec, ReportApiSource, ColumnSpec), datasets/ (tickets, customers,
              assignments, deliveries), validate.py, dates.py, engine.py, report_api.py (compile/merge
              Reporting API), records.py (chế độ danh sách)
providers/    openai.py, base.py (ToolCallingProvider + LLMCapabilities), crm_api.py (CrmListClient,
              CrmReportClient)
schemas/system/report.py, records.py  contract ReportQuery / RecordQuery (enum sinh từ catalog báo cáo)
```

Router không tự khởi tạo provider hoặc repository.

## Ba thành phần khi chạy

```text
Trình duyệt (widget src/chatbot)
  └─ cookie HttpOnly qs_visitor, qs_chat_session ─▶ widget-backend/ (Node, :8787)
       └─ Bearer qsk_… (key kênh website) + {session_id, message} ─▶ backend/ dịch vụ AI (:8000) POST /chat/website
CRM backend ─ Bearer qsk_… (key kênh crm) + {user_id, session_id, message} ─▶ dịch vụ AI POST /chat/crm
```

- **Dịch vụ AI** (`backend/`): chỉ xác thực service key và xử lý chat; không
  biết khách website.
- **widget-backend** (`widget-backend/`): giữ `CHATBOT_API_KEY`, cấp
  `visitor_id` ẩn danh, giữ `session_id` trong cookie HttpOnly (đọc từ header
  `X-Session-ID`), chuyển tiếp SSE và gỡ `session_id` khỏi event `done`.
- **Widget** (`src/`): chỉ gọi `/api/chat` và `/api/chat/history` cùng origin
  (Vite proxy `/api` khi dev). Support Workspace vẫn gọi thẳng GET
  `/chatbot/...` của dịch vụ AI (chưa xác thực).

## Luồng `POST /chat/website` (và `POST /chat/crm`)

1. Middleware chốt `request_id`. Dependency dựng `RequestContext` (channel do
   endpoint quyết định), xác thực service key qua `ServiceAuthService` (key phải
   được cấp cho kênh của endpoint) và đọc `Idempotency-Key`. Với CRM, router gắn `user_id` của body vào principal bằng
   `PrincipalContext.acting_for()`.
2. Router parse schema kênh (`WebsiteChatIn`/`CRMChatIn`); Pydantic kiểm tra
   schema version, `session_id` UUID, giới hạn text và client context. Nếu chưa
   cấu hình provider, trả HTTP 503.
3. `SessionAccessService` tạo session mới thuộc principal (`chat_sessions`)
   hoặc chỉ dùng lại session cùng chủ, cùng kênh, chưa revoked/expired; còn lại
   trả 404 `session_not_found`. Server sinh `message_id`; adapter dựng
   `InboundRequest` nội bộ (strict), service nhận kèm `PrincipalContext` và
   `RequestContext` trong `RunState`.
   Với session đã có, router chiếm **lease theo phiên** (`SessionTurnLease`,
   cột `chat_sessions.turn_lease_until`, một câu UPDATE nguyên tử, commit ngay
   bằng session DB riêng). Phiên đang có lượt chạy trả 409 `session_busy`. Lease
   được giải phóng khi stream SSE kết thúc vì bất kỳ lý do gì (xong, lỗi, client
   ngắt; shield trước cancel của anyio) và tự hết hạn sau `CHAT_TURN_LEASE_S`
   nếu tiến trình chết. Session mới không cần lease. Câu chiếm lease cũng cập
   nhật `last_activity_at`; transaction của request **không** UPDATE dòng
   `chat_sessions` của phiên đã có, vì transaction đó chỉ commit sau khi stream
   xong và khóa dòng sẽ chặn chính lease của request (connection riêng). Lệnh
   lease đặt `lock_timeout = 3s` để không treo tới `statement_timeout`.
4. `SecurityStage` normalize nội dung, chạy `InjectionGuard` và `ContentPolicy`.
   Nếu block, service ghi audit `status='blocked'` bằng session database riêng,
   không chạy context/provider, rồi router phát SSE `error`.
5. `ContextLoader` đọc history `status='completed'`, tạo `RunContext` gồm
   conversation, query và retrieval scope. Website hiện map tới cả
   `crm-technical` và `crm-sale`. `ConversationState` (pending clarification,
   `clarify_attempts`, `last_models`, `mode`, `ticket_id`) được đọc từ cột
   `conversation_state` của row completed gần nhất; dữ liệu sai schema thì dùng
   state mặc định. Nếu `mode ≠ bot` (đã chuyển nhân viên), service trả câu cố
   định `agent.awaiting`/`agent.active`, ghi history và **không** chạy
   analysis/LLM.
6. `Prune` áp dụng context token budget, giữ query/summary và bỏ các history
   turn cũ trước; lỗi budget/config là domain error, không phải security block.
7. `ConversationState` mang `last_models` (cộng dồn, cũ → mới, tối đa 4) và
   `active_model` (model duy nhất của lượt gần nhất; `None` sau lượt có ≥ 2 model;
   giữ nguyên sau lượt không nhắc model). Câu thiếu model kế thừa
   `active_model` trước, rồi mới xét `last_models`. `<state>` gửi LLM gồm cả hai
   để hiểu "nó" (active) và "các model trên" (last_models).
   Vòng làm rõ (`clarification/`):
   - `ClarificationResumeStage` chạy trước analysis. Nếu có pending và câu trả
     lời ngắn khớp chắc chắn (alias model, số thứ tự, "đúng/vâng" khi chỉ có
     một gợi ý, hoặc một mã giống model như "A10"), nó vá raw sub-query đang
     bị giữ (`patch_pending`) và dựng lại analysis bằng `resolve` +
     `plan_turn`, **không gọi LLM**.
   - Nếu không khớp, `AnalysisStage` gọi `QueryAnalyzer` với `<pending>` trong
     context. Output strict có thêm `pending_answer`; khi có giá trị, các ý bị
     giữ đã vá được ghép trước các sub-query mới.
   - Sau `clarify_attempts >= 2` lần hỏi mà vẫn chưa rõ, các ý bị giữ chuyển
     sang `no_docs` (`clarification_exhausted`) và pending bị xóa.
   - Câu trả lời là câu hỏi mới: pending giữ lại với `ttl` giảm dần (mặc định 2).
   - Câu trả lời không trích được gì (LLM trả `sub_queries=[]`, không có
     `pending_answer`, vd. "ok" khi có nhiều gợi ý): giữ lại các ý đang chờ và
     hỏi lại, tính một lần thử.
   - Câu cần đúng một model mà chưa có model (`resolve_sub_query`, có
     `last_models`): `model_dependency=general` → retrieve không lọc model,
     `answer_mode=general`, hỏi model ở cuối (không chặn); `last_models` có 1
     model → kế thừa (warning `inherited_model:X`); ≥ 2 model →
     `context_conflict` với candidates = `last_models`; không có →
     `missing_product_model` với candidates = model có tài liệu cho domain đích.
     Câu trả lời chung kết thúc bằng câu hỏi model tạo pending **không chặn**
     (`blocking=false`): trả lời mã/alias/số thứ tự sẽ tra cứu lại theo model đó;
     "ok/đúng" không kích hoạt (xử lý như chitchat).
     Model nêu ở lượt hiện tại luôn được ưu tiên. Cờ `general` của LLM chỉ được
     nhận khi intent có `allow_general` (mặc định có; `guide.installation` và
     `troubleshoot.error` thì không) và `standalone_query` không nhắc mã cụ thể
     (`MODEL_SPECIFIC_PATTERN`: CN1, X40, #4130, AL12, E05).
   - `guard_extracted_models` loại model LLM trả về mà mã/alias không có trong
     câu hỏi, lịch sử hay `last_models` (warning `model_not_in_text:X`), để không
     âm thầm đổi F84 thành F86.
   - Lỗi analysis/execution/compose được ghi history `error` và trả SSE
     `analysis_error`.
8. `ExecutionStage` tạo execution plan từ analysis và chạy plan qua
   `ExecutionScheduler` với các handler deterministic trong
   `orchestration/handlers.py`. Các handler này không gọi LLM:
   - `chitchat` và `out_of_scope` trả về `completed`.
   - `no_docs` trả về `completed`, kèm `unsupported_models`.
   - `handoff` trả về `handed_off`, kèm `handoff_reason`.
   - Planner **giữ** (`held_sub_query_ids`) các sub-query có clarification
     chặn hoặc có chung mention với clarification của lượt (vd. "F84 khác gì
     F54" khi F84 đang chờ làm rõ). Chúng thành task `clarify` `blocked`
     (`reason=task_blocked`) và không được tra cứu; các ý đã rõ vẫn
     chạy ngay.
   - `retrieve` (mức kiểm thử): planner tạo **một task cho mỗi sub-query**
     (`task-retrieve-{id}`), không gom theo `analysis.batches`, để các intent
     khác nhau không dùng chung scopes hợp nhất; scheduler chạy song song.
     Khi `Retriever` được inject (`main.py` → `app.state.chatbot_retriever`),
     `handle_retrieve` dựng `RetrievalRequest` cho từng target/fallback target
     và gọi `Retriever.search`. Không có retriever thì task `failed` với
     `handler_not_configured`; lỗi embedding/DB thì `failed` với
     `retrieval_error`; không có chunk liên quan thì `completed` kèm
     `metadata.no_hits`.

   Ranh giới trách nhiệm của tầng retrieve (filtered hybrid retrieval):

   | Thành phần | Trách nhiệm |
   |---|---|
   | `handle_retrieve` (`orchestration/handlers.py`) | Task → `RetrievalRequest`, trạng thái và lỗi task |
   | `Retriever.search` (`retrieval/retriever.py`) | Embedding câu hỏi, lặp targets, fallback khi không có chunk vượt `RETRIEVAL_MIN_SIMILARITY`, tách từng model khi `comparison`, gộp/dedupe, cắt `RETRIEVAL_FINAL_CHUNK_TOP_K`, mở rộng sang chunk cha (tối đa `RETRIEVAL_MAX_CONTEXT_PARENTS`), dựng `RetrievalTrace` |
   | `DocChunkRepository` | Session riêng cho mỗi lời gọi (task chạy song song), gọi SQL function |
   | `match_doc_chunks` (`backend/sql/doc_chunks.sql`) | Lọc `is_active`, `domain`, `scopes &&`, `product_models &&`, `control_interface` (rỗng = áp dụng chung); vector top-k + FTS (`embed_text`, OR) top-k; RRF; `spec_attributes` chỉ cộng điểm |
   | `ExecutionStage.assign_source_ids` | Gán `S#` theo thứ tự task sau khi mọi task xong; chunk trùng giữa sub-query dùng chung `S#`; đánh `selected` cho candidate và ghi trace vào `RunState` |
   | `AnswerComposer` | Block `<sources>` theo từng sub-query; prompt yêu cầu trích `[S#]` |

9. Lượt chỉ gồm `chitchat`/`out_of_scope`, hoặc chỉ gồm `handoff`, trả câu cố
   định từ `prompts/direct_responses.py` (theo `handoff_reason`) và không gọi
   `AnswerComposer`, **nếu** ngôn ngữ trả lời có bản soạn sẵn (vi, en). Ngôn ngữ
   khác đi qua `AnswerComposer`.

   Đa ngôn ngữ: analysis trả `language` (ISO 639-1) và `standalone_query` luôn
   bằng tiếng Việt (embedding/FTS chạy trên `embed_text` tiếng Việt). Ngôn ngữ
   trả lời = `analysis.language` → `ConversationState.language` (lượt resume
   không gọi LLM) → locale client → `vi`; được gán vào `query.language`, gửi cho
   `AnswerComposer` qua `<language>` và lưu vào `ConversationState.language`.
   Câu trả lời trước analysis (bị chặn, `agent.*`) dùng ngôn ngữ của phiên →
   locale → `guess_reply_language` (heuristic dấu/từ tiếng Việt, mặc định `en`).
   `chat_history.normalized_query` lưu các `standalone_query`.
   Các lượt khác: `AnswerComposer` gom kết quả bằng `collect_results`, dựng messages gồm
   system prompt, history, `<query>`, `<task_results>` và `<clarification>`
   (nếu có), rồi stream câu trả lời qua `provider.stream_chat`. Mỗi lượt chỉ
   gọi LLM một lần cho câu trả lời cuối. Nếu có task retrieve, messages có thêm
   `<sources>` (nội dung chunk cắt theo `source_char_limit`). Sau khi stream xong,
   service ghi history `status='completed'`. Sources/assets chưa được gửi về
   frontend qua SSE và `retrieved_chunk_ids` chưa được ghi.
   Sau khi trả lời, nếu có task `handed_off` thì gọi `HandoffProvider`. Hiện chỉ
   có `DisabledHandoffProvider` (không ticket, giữ `mode=bot`); chưa nối API
   bên ngoài, chưa chuyển tiếp tin nhắn cho nhân viên và chưa có cơ chế trả về
   `mode=bot`. `update_conversation_state` tính state mới và lưu vào cột
   `conversation_state` của row `completed`.
10. Router phát event `done` với `request_id` và authoritative `session_id`
    (cùng giá trị header `X-Session-ID`). Bên tích hợp giữ session cho lượt sau:
    widget-backend lưu trong cookie HttpOnly `qs_chat_session` và gỡ
    `session_id` khỏi `done`; CRM giữ trong UI state và gửi `null` khi bắt đầu
    hội thoại mới. Support Workspace chỉ còn đọc khóa cũ `chatbot_session_id`
    trong localStorage làm session mặc định để xem.
11. Exception được log server-side và ánh xạ thành SSE `error` trong
    `routers/sse.py`: `request_blocked` (SecurityStage), `context_error`
    (context/pruning), `analysis_error` (analysis/execution/compose),
    `agent_error` (luồng agent CRM), còn lại `provider_error`.

## Luồng agent (kênh CRM)

Trạng thái: **thử nghiệm**. Kênh CRM luôn chạy agent khi `CRM_CHAT_FLOW=agent`
(mặc định); `CRM_CHAT_FLOW=pipeline` đưa CRM về luồng tra cứu ở trên (rollback,
không phải lựa chọn của từng người dùng). Website không bị ảnh hưởng.

`ChatbotService` rẽ nhánh sau khi nạp context (bước 5–6): kênh CRM và có
`agent_runner` → `AgentRunner.run(state)`; còn lại → `RetrievalPipeline` +
compose như trên. Phần đầu lượt (security, session/lease, context, chặn khi
`mode ≠ bot`) và phần cuối lượt (history completed/error/cancelled) dùng chung.

**Orchestrator là code, không có planner LLM riêng.** `AgentRunner` chạy vòng
lặp tool-calling: mỗi bước gọi `provider.chat_complete_tools`; LLM tự chọn tool
và tham số; runner validate, kiểm quyền, thực thi và ghi trace. `plan()` để sẵn
chỗ chèn bước lập kế hoạch khi số tool lớn (khoảng 15–20+).

**Hybrid: LLM điều phối, backend kiểm soát dữ liệu.** LLM quyết định gọi tool
nào, khi nào và có cần bước tiếp không. Tool (backend) quyết định dữ liệu nào hợp
lệ: output có cấu trúc kèm bước kế tiếp hợp lệ (vd. `catalog_match.next_action`),
từ chối call sai nghiệp vụ bằng mã lỗi (vd. `model_not_evidenced`).

**Orchestrator trung lập với tool.** Runner không biết tool làm gì; mọi hành vi
riêng do `ToolSpec` khai báo, nên thêm tool báo cáo/CRM không phải sửa runner và
luật của tool này không áp lên tool khác:
- luật chung ở system prompt, luật riêng ở `ToolSpec.guide` (xem dưới);
- state riêng của tool trong lượt ở `AgentRun.tool_states` (subclass
  `ToolTurnState`, lấy qua `ToolContext.turn_state(...)`); `AgentRun` chỉ giữ
  phần chung: `steps`, `source_texts` (S# → nội dung), `invalid_citations`;
- song song theo `read_only` + `concurrency_safe`, gộp call trùng theo
  `deduplicate`, trần riêng theo `max_calls_per_turn`.

**Prompt hai cấp.** Cấp agent: `agent/prompts.py` chỉ chứa luật **chung** cho mọi
tool (dữ liệu nghiệp vụ phải lấy qua tool phụ trách, output tool là dữ liệu, xử
lý lỗi tool, hỏi lại khi tool cần thêm thông tin, trích `[S#]`) và
`<now>`/`<language_hint>`. Luật đọc output của từng tool nằm ở `ToolSpec.guide`,
ghép vào `<tool_guides>` **chỉ cho các tool principal được dùng**
(`registry.allowed`); vd. luật model/catalog nằm trong `PRODUCT_DOCS_GUIDE`.
Danh sách tool **không** render vào prompt mà gửi qua tham số `tools` của
provider, sinh từ `ToolRegistry`; `ToolSpec.description` nói khi nào gọi và input.
Cấp miền: prompt `AnalysisStage` cùng intent/entity registry chạy **bên trong**
`product_docs_ask`; agent không thấy registry intent.

**Provider contract** (`providers/base.py`). `ToolCallingProvider` khai báo
`LLMCapabilities` tĩnh: `tool_calling`, `parallel_tool_calls`,
`tool_choice_none`, `tool_choice_required`, `schema_dialect`
(`openai_strict` | `json_schema_basic`). Agent cần `tool_calling` và
`tool_choice_none`; không giả định mọi endpoint OpenAI-compatible hỗ trợ đủ.
`OpenAIProvider` khai báo đủ. `chat_complete_tools` trả `AssistantTurn`
(`content`, `tool_calls[{id, name, arguments_raw}]`, `finish_reason`, `usage`);
arguments giữ nguyên chuỗi, registry mới parse. Backend của tool (Tavily, CRM…)
không phải provider.

**ToolRegistry** (`tools/`). `ToolSpec(name, description, input_model,
output_model, run, guide, read_only, concurrency_safe, deduplicate,
max_calls_per_turn, timeout_s, required_scope)`:
- Tên theo `^[a-zA-Z0-9_-]{1,64}$` (không dấu chấm: `product_docs_ask`); input
  model bắt buộc `extra="forbid"`; output kế thừa `ToolOutput`.
- `to_provider_schema` là nơi **duy nhất** chuẩn hóa JSON Schema của Pydantic:
  inline `$defs`/`$ref`, `Optional[T]` → `type: [T, "null"]`,
  `additionalProperties: false` mọi object, strict thì mọi field vào `required`
  và bỏ keyword không hỗ trợ (ràng buộc vẫn do Pydantic kiểm khi validate).
  Dict tự do, schema đệ quy, union object với dialect basic → lỗi lúc startup.
- `allowed(principal)`: hiện mọi tool không đòi scope đều được dùng (chưa có
  role/scope cho nhân viên CRM) — điểm gắn phân quyền sau này.
- `invoke` luôn trả đúng một `ToolOutcome` cho mỗi `tool_call_id`; lỗi là mã gửi
  lại LLM: `tool_invalid_args` (JSON sai, sai schema, field lạ; kèm vị trí lỗi,
  không lặp giá trị), `tool_not_found`, `tool_not_allowed`, `tool_timeout`,
  `tool_failed` (chi tiết chỉ vào log), `tool_invalid_output`,
  `tool_output_too_large`. Tool từ chối vì nghiệp vụ bằng `ToolRejected(code,
  detail)` (`ToolArgumentError` → `tool_invalid_args`); `detail` do tool viết,
  không chứa dữ liệu nhạy cảm. `CancelledError` không bao giờ bị bắt.
- Thêm tool mới: input `extra="forbid"`, output kế thừa `ToolOutput` (tự cắt
  bằng `to_llm` nếu lớn), `description` + `guide`, khai báo `read_only` /
  `concurrency_safe` / `deduplicate` (tool ghi: không gộp call, chưa hỗ trợ xác
  nhận người dùng) / `max_calls_per_turn` / `required_scope`, đăng ký trong
  `agent/setup.py`. State trong lượt dùng subclass `ToolTurnState` riêng.

**Giao thức tool-call trong runner.**
- `tool_choice="auto"` trong vòng lặp; `"none"` cho bước cuối (hết bước, hết
  lượt gọi tool, hết giờ, hoặc lần trả lời rỗng đầu tiên) — vẫn gửi `tools` để
  lịch sử message `tool` hợp lệ.
- Có tool call (kèm hoặc không kèm content): content là suy nghĩ trung gian,
  không gửi người dùng nhưng giữ trong assistant message. Chỉ có content: câu
  trả lời cuối, yield thành **một** `delta` (chưa stream token). Rỗng hai lần:
  `agent_empty_answer`. `finish_reason=length`: câu trả lời vẫn trả kèm log
  cảnh báo; tool call bị cắt thành `tool_invalid_args`.
- Mỗi `tool_call_id` có đúng một message `role=tool`, theo thứ tự call; call
  vượt `AGENT_MAX_TOOL_CALLS` nhận `tool_budget_exhausted`, call bỏ vì hết giờ
  nhận `tool_timeout`, call vượt `max_calls_per_turn` của tool nhận
  `tool_call_limit` (call của tool khác vẫn chạy).
- Call trùng (cùng tên, argument giống nhau sau khi chuẩn hóa thứ tự key và
  khoảng trắng) của tool `deduplicate` (mặc định = `read_only`) không chạy lại:
  dùng output của call thành công ở bước trước hoặc của call cùng response, bước
  ghi `status="deduplicated"`. Call lỗi được thử lại; tool ghi luôn chạy.
- Câu trả lời cuối: `[S#]` không thuộc nguồn đã trả trong lượt bị bỏ khỏi câu
  trả lời và ghi vào `invalid_citations`.
- Output tool được cắt theo **token** (`util/token_counter.py`,
  `AGENT_TOOL_OUTPUT_TOKENS`). `product_docs_ask` cắt theo cấu trúc: luôn giữ
  `status`/`clarification`/`task_results`, thêm nguồn theo rank tới khi hết
  budget, nguồn cuối cắt ở ranh giới câu, ghi `truncated`/`omitted_sources`.

**Deadline chung và cancellation.** `Deadline(AGENT_TURN_TIMEOUT_S)`; mỗi lời
gọi nhận `min(giới hạn riêng, thời gian còn lại − AGENT_FINAL_RESERVE_S)` nên
tổng không vượt timeout của lượt; còn dưới phần dự phòng thì bỏ tool còn lại và
chuyển sang bước cuối; bước cuối hết giờ → `agent_timeout`. Client ngắt: cancel
đi xuyên `stream_reply` → runner → `TaskGroup` của các tool → RunState con →
`QueryAnalyzer`/`Retriever`/`DocChunkRepository`; service ghi `cancelled`,
không ghi `completed`. Tầng agent không tạo task chạy ngầm tách rời.

**Concurrency ba mức.**
1. Tool call trong một response: độc lập theo định nghĩa (LLM chưa thấy kết quả
   của nhau; phụ thuộc thể hiện qua bước sau). Chạy song song bằng `TaskGroup`
   (tối đa `AGENT_PARALLEL_TOOLS`) chỉ khi provider cho phép và mọi tool trong
   batch `read_only` + `concurrency_safe`; ngược lại tuần tự. S# cấp qua
   `SourceAllocator` dùng chung của lượt: không trùng, chunk trùng giữ S#; khi
   song song, thứ tự số theo thứ tự hoàn thành.
2. Nhiều nhân viên: mỗi request có state riêng; provider/retriever không có
   trạng thái. `AGENT_MAX_CONCURRENT_RUNS` giới hạn lượt agent đồng thời mỗi
   tiến trình. Kết nối DB tối đa ≈ số lượt × tool song song × task retrieve: cân
   với `DATABASE_POOL_SIZE`.
3. Cùng một phiên: lease theo phiên (bước 3), 409 `session_busy`.

**`product_docs_ask`.** Chạy `RetrievalPipeline` trên RunState con, có thêm
`CatalogLookupStage` giữa Analysis và Execution (chỉ pipeline của tool, website
không có): `query.origin` = câu hỏi agent viết; history = history phiên + tin
nhắn hiện tại; `pending` bị bỏ; `last_models`/`active_model` của phiên được giữ
để kế thừa model và phát hiện `context_conflict` bằng code. Status: `answered`
(có nguồn), `matched` / `no_match` (tìm model bằng dữ liệu sản phẩm),
`needs_clarification` (candidates gồm `code` + `name`), `no_docs`, `handoff`,
`out_of_scope`, `failed`. Nhóm nguồn ghi `product_models` (model đã lọc khi
retrieve) để agent không gán nguồn của model này cho model khác.

*Tìm model theo tiêu chí (Q1) rồi hỏi tiếp về model đó (Q2).* Sub-query
discovery = `lookup.product_catalog` chưa có model, có `control_interface`,
`excluded_control_interface` hoặc `unmapped_conditions` (analysis schema v3.4,
thêm `interface_match: all|any`). `CatalogLookupStage` lọc bằng
`ProductCatalog` (hiện `RegistryProductCatalog` đọc `REGISTRY["capabilities"]`
— phần cứng **hỗ trợ** gì, khác `coverage` là **có tài liệu** gì; closed world:
mọi model có một dòng) và trả `catalog_match` (`applied`, `unmapped_conditions`,
`models[{code, name, has_technical_docs, documented_interfaces}]`,
`next_action`):

| Kết quả | `next_action` | Retrieval | Model được dùng làm bằng chứng ở Q2 |
|---|---|---|---|
| Điều kiện trong bảng loại hết model | `report_no_match` (status `no_match`) | không | — |
| 1–3 model (`MAX_AUTO_LOOKUP_MODELS`), không có `unmapped_conditions` | `lookup_each` | không | có (`discovered_models`) |
| ≥ 4 model, không có `unmapped_conditions` | `ask_selection` | không | không: lượt sau nhân viên nêu model hoặc "tất cả" (danh sách nằm trong history) |
| Có `unmapped_conditions` | `verify_with_sources` | catalog; lọc theo ứng viên nếu có điều kiện trong bảng, không lọc nếu không có | chỉ model trong nguồn agent trích qua `based_on_sources` |

`no_match` khác `needs_clarification`: dữ liệu xác nhận không có thì báo kết quả,
không hỏi lại. Một interface vừa yêu cầu vừa loại trừ → `unclear_query`.
Trong cùng lần gọi có discovery, sub-query cần model mà model không có trong câu
hỏi của agent (thiếu model, `context_conflict`, so sánh thiếu model, hoặc model
kế thừa từ phiên) được giữ lại với task status `awaiting_models` (không phải câu
hỏi lại nhân viên); agent gọi lại theo `next_action`. Sub-query độc lập có model
riêng (vd. "F86 có bao nhiêu trục? F54 thì sao?") chạy như thường.

*Bằng chứng model.* Model trong câu hỏi của agent phải có trong: tin nhắn hoặc
history của nhân viên, `last_models`/`active_model` của phiên, `discovered_models`
của lượt (`ProductDocsTurnState`), hoặc nguồn trích qua `based_on_sources`
(`models_in_text`, không tính alias mơ hồ). Thiếu → `model_not_evidenced` trước
khi gọi LLM analysis; S# không có trong lượt → `tool_invalid_args`. Guard trong
AnalysisStage vẫn chạy với cùng bằng chứng (`RunState.evidence_models`) để chặn
model LLM analysis tự thêm. `based_on_sources` chỉ kiểm model **có xuất hiện**
trong nguồn, không kiểm nghĩa câu.

- Làm rõ model qua history, không qua `pending`: tool trả
  `needs_clarification` → agent hỏi lại; lượt sau agent gọi lại với mã model
  nhân viên chọn; câu hỏi lại ở lượt trước nằm trong history nên guard giữ được
  model đó.
- `handoff` chỉ là **kết quả nghiệp vụ** (giá, bảo hành… ngoài tài liệu, kèm
  `handoff_reason`); agent không đổi `Mode`, không gọi `HandoffProvider`.
- Lượt agent chỉ cập nhật ngữ cảnh model của `conversation_state`
  (`last_models`/`active_model` từ các lần tra cứu có nguồn, qua
  `product_docs_plans`); không pending, không handoff. Lượt chỉ dùng tool khác
  giữ nguyên ngữ cảnh model.
- Tool có gọi LLM (analysis) vì thuộc tầng agent; quy tắc "handler orchestration
  không gọi LLM" giữ nguyên.

**Persistence.** `retrieval_snapshot` gộp plan của mọi lần gọi tool (task id
`{tool_call_id}:task-retrieve-qN`) và thêm khóa nội bộ `agent_steps` (bước LLM/
tool, trạng thái, latency; không chứa nội dung), `answered_without_tools` (lượt
không gọi tool nào — theo dõi câu trả lời từ trí nhớ) và `invalid_citations`.
`normalized_query` lưu các câu hỏi agent gửi cho `product_docs_ask`. Lỗi agent →
history `error`, SSE `agent_error`.

**`crm_report`** (thử nghiệm, sau cờ `CRM_REPORT_ENABLED`, mặc định tắt). Số liệu
tổng hợp từ CRM theo **semantic catalog**: LLM chỉ chọn tên logic (dataset, metric,
dimension, filter) trong enum; đường dẫn cột, join, filter hệ thống và định nghĩa nghiệp
vụ nằm trong `DatasetSpec`. LLM không gọi API khám phá schema (`/reports/datasets`,
`/reports/tables`), không thấy token, URL hay tên bảng/cột. Bốn dataset:

| Dataset | Nguồn | Quyền CRM | Ghi chú |
|---|---|---|---|
| `tickets` | list_api `GET /api/v1/support/cases` | theo token | Giữ nguồn cũ: cần metric dẫn xuất (thời gian xử lý, tuổi phiếu, `status_group`) mà Reporting API không tính được |
| `customers` | report_api, dataset dựng sẵn `customers` | `customer.read` | Mặc định loại `customer_type` spam/lost (trừ khi lọc/nhóm theo trường này); `assigned_sales` chỉ là UUID |
| `support_assignments` | report_api, bảng `support_assignments` | `auth.manage_roles` | Mỗi dòng là một lần giao; khách = thiết bị của phiếu (`case_id.product_item_id.customer_id`); người hiển thị và lọc theo `assigned_to.username` |
| `device_deliveries` | report_api, bảng `product_ownerships` | `auth.manage_roles` | "Bán được" = thiết bị giao cho khách; loại chuyển nhượng (`transferred_from_ownership_id is_null`) |

- LLM chỉ điền `ReportQuery` (`schemas/system/report.py`): `dataset`, `metrics`
  (1–3), `dimensions` (0–2), `filters` (≤8, AND), `date_range` (`preset` hoặc
  `start`/`end` dạng ngày, `end` không bao gồm), `time_grain`, `sort`, `limit`
  (mặc định 10, trần 50). Enum sinh từ catalog (hợp của mọi dataset); LLM không truyền timezone.
- `reporting/validate.py` kiểm tra theo catalog của dataset (operator hợp kiểu,
  giá trị enum, nhãn tiếng Việt, alias model qua `resolve_models`) **trước** khi gọi
  CRM; lỗi → `tool_invalid_args` kèm giá trị hợp lệ để agent tự sửa. Dataset report_api
  chỉ chia kỳ theo các kỳ khai báo (`ReportApiSource.period_dimension`, không có `week`);
  trường string của report_api giữ nguyên hoa/thường (`casefold=False`, SQL so khớp chính xác).
- list_api: `providers/crm_api.py` gọi `GET {CRM_API_BASE_URL}{source_path}?limit=&offset=`,
  lặp tới `total` hoặc `CRM_REPORT_MAX_ITEMS` (`source_truncated`). Item API → record
  (`extra="ignore"`): `subject`, `description` và trường không khai báo bị bỏ ngay khi
  parse. `reporting/engine.py` (hàm thuần): filter hệ thống (`delete_pending = false`) →
  filters + date_range → nhóm theo dimensions (+ kỳ theo `CRM_REPORT_TIMEZONE`) → metric →
  điền kỳ trống bằng 0 và `change.delta`/`delta_pct` → sort (None cuối) → limit.
- report_api: `reporting/report_api.py` (hàm thuần) compile `NormalizedQuery` thành JSON
  của `POST /api/v1/reports/query`: một query cho mỗi nhóm metric cùng filter riêng
  (vd `current_assignment_count` có `is_current = true`), query gốc luôn có `count`
  (`matched_count`); chia kỳ có dimension thêm query `ranking` không chia kỳ để xếp hạng và
  cắt limit theo tổ hợp; `[start, end)` → `from`/`to` bao gồm; mọi value là chuỗi; query có
  dimension gửi `limit` 1000 + `totals`. `CrmReportClient` chạy các query song song
  (`TaskGroup`), rồi `merge_report` ghép theo khóa dimension (nhóm theo UUID, hiển thị
  username/tên), điền kỳ trống và tính delta bằng hàm của engine.
- **CRM phân quyền và giới hạn phạm vi dữ liệu theo token** (`crm_access_token`, trường
  tùy chọn của `/chat/crm`, `SecretStr`, `exclude=True`: không log, không lưu; không có
  token thì Bearer là `acting_user_id`); dịch vụ AI không lọc quyền thêm. 401 →
  `crm_auth_failed`; 403 → `crm_forbidden`; 400 của Reporting API → `crm_report_contract_error`
  (spec do catalog sinh nên đây là lỗi cấu hình, log ERROR, agent không thử lại);
  timeout/5xx/body lạ → `crm_unavailable`.
- `ReportOutput`: `applied` (query đã chuẩn hóa; `system_filters` gồm filter hệ thống và
  filter mặc định đã áp dụng), `rows`, `row_count`, `total_groups`, `matched_count`,
  `fetched_count`/`skipped_count` (list_api; report_api là `null`), `source_truncated`,
  `source` (`list_api` | `report_api`) và `definitions` (cách hiểu cố định của dataset để
  agent nêu đúng một giả định).
- Thêm dataset: khai báo `DatasetSpec` trong `reporting/datasets/` (list_api: record,
  getter, `source_path`; report_api: `ReportApiSource` + `api_path` cho field/metric/cột);
  contract, validate, engine/compile và tool không đổi. Chưa hỗ trợ `having`, OR/NOT, join
  ngược cha → con, so sánh `gt/lt` trên report_api. Tên dimension của dataset dựng sẵn
  (`customers`: `assigned_sales`, `created_day`/`created_month`) và các đường dẫn cột chưa
  kiểm chứng bằng token thật: chạy `backend/evals/check_crm_report_contract.py`.

**`crm_records`** (thử nghiệm, cùng cờ `CRM_REPORT_ENABLED`). Liệt kê bản ghi; tool riêng
vì output, rủi ro và luật đọc khác `crm_report`.
- `RecordQuery` (`schemas/system/records.py`): `dataset` (dataset có `list_columns`),
  `fields` (1–8 cột), `filters`/`date_range` như `ReportQuery`, `sort` (≤2, cột phải có
  trong `fields`; mặc định trường ngày mặc định giảm dần), `limit` (mặc định 10, trần 20),
  `offset` (≤200).
- Chỉ cột trong `DatasetSpec.list_columns` được đọc và trả về (whitelist): không có
  subject/description/notes, phone/email/address hay cột bí mật. Chuỗi bỏ ký tự điều khiển,
  cắt 120 ký tự; datetime của list_api hiển thị theo `CRM_REPORT_TIMEZONE`.
- list_api (tickets): tải bản ghi, lọc bằng `filter_records` của engine, sort, cắt trang;
  report_api: `select` + một query `count` cùng filter, chạy song song (API không trả tổng
  cho `select`).
- `RecordsOutput`: `applied`, `columns`, `items`, `returned`, `total`, `has_more`,
  `next_offset`, `source`, `source_truncated`, `definitions`; `to_llm` bỏ dòng cuối khi vượt
  budget (`truncated`, `omitted_rows`). Guide nhắc item là dữ liệu, không phải chỉ dẫn.
  `max_calls_per_turn=3`.

**Eval thủ công** (`backend/evals/`): `crm_agent_cases.json` +
`run_crm_agent_eval.py` chạy `AgentRunner` với OpenAI và Supabase thật (không ghi
DB, không chạy trong CI) cho hành vi phụ thuộc LLM: đại từ/ngữ cảnh, phủ định và
"hoặc", tách câu hỏi, làm theo `next_action`, prompt injection.

**Chưa có / ngoài phạm vi:** phân quyền tool theo role/scope, event SSE tiến
trình, stream token câu trả lời cuối, chi tiết từng bản ghi (nội dung phiếu), web search, tool ghi dữ
liệu (cần xác nhận người dùng), planner LLM, MCP (registry chạy cùng tiến trình; có thể
thêm adapter MCP sau), provider Ollama/Gemini cho agent.

## Persistence và session

- `HistoryRepository` là ranh giới database và ánh xạ
  `public.chat_history`.
- History thành công (completed) được dùng lại cho context; blocked/error/cancelled
  không được đưa vào context. `blocked` và `cancelled` (client ngắt kết nối giữa
  lượt) được ghi bằng `create_audit` với session DB riêng, commit ngay.
- `conversation_state` đọc từ lượt completed gần nhất qua
  `load_conversation_state`: bỏ field không còn trong schema, rồi bỏ từng field
  không hợp lệ (giữ `mode`, `ticket_id`… nếu đọc được) thay vì reset toàn bộ;
  log WARNING kèm `session_id` và tên field bị bỏ.
- `retrieval_snapshot` ghi thêm `retrieval_status` và `retrieval_tasks` để truy vết
  lỗi tra cứu (khách không nhận mã lỗi cho trường hợp này).
- `ChatSessionRepository` ánh xạ `public.chat_sessions` (chủ sở hữu session).
  `POST /chat/*` chỉ dùng lại session cùng principal và kênh. Các GET
  `/chatbot/sessions/{session_id}/...` và `/chatbot/conversations` (Support
  Workspace) **chưa** kiểm ownership.
- `message_id` do server sinh là `chat_history.id`; `Idempotency-Key` được lưu
  vào `chat_history.idempotency_key` nhưng chưa chống xử lý trùng. Hai request
  cùng session không chạy song song: request thứ hai nhận 409 `session_busy`
  (lease theo phiên).

## Tracing (giai đoạn 0: trong tiến trình, không thư viện ngoài)

Mỗi request `POST /chat/*` có một `Trace` (`app/core/tracing.py`): cây span với
`start_ms` tính từ lúc middleware nhận request, `duration_ms`, `status` và thuộc
tính metadata. Span cha nằm trong contextvars; `TaskGroup` sao chép context nên tool
chạy song song và task retrieve vẫn nằm đúng dưới span cha.

```text
chat.request (root: channel, flow, history_status, first_delta_ms, deltas)
├ session.resolve · session.lease_acquire
├ stage.security · stage.context_load · stage.prune
├ [agent] agent.run (steps, tool_calls, answered_without_tools)
│  ├ agent.wait_slot
│  ├ llm.chat_tools (step, tool_choice, finish_reason, tool_calls, input/output_tokens)
│  ├ tool.product_docs_ask (tool_call_id, result_status, sources)
│  │  ├ stage.clarification · stage.analysis (intents, routes) → llm.chat_json
│  │  ├ stage.catalog_lookup (next_action) · stage.execution (tasks)
│  │  └ retrieval.search (hits, top_score, fallback)
│  │     ├ embedding (input_tokens) · db.match_doc_chunks (rows) · db.fetch_chunks
│  ├ tool.crm_report (query_shape, credential_source) → report.validate · report.fetch
│  │    → http.crm_list×N (status_code) · report.engine
│  │    | report_api: report.fetch (queries) → http.crm_report×N (dataset, status_code) · report.merge
│  ├ tool.crm_records (dataset, fields, returned, total) → records.fetch → http.crm_list | http.crm_report
│  └ tool.<name> tức thời khi call bị gộp trùng / vượt trần / hết lượt (status = mã)
│     (span tool lỗi có error_detail đã che giá trị trong nháy; root có tool_errors)
├ [pipeline] stage.clarification … stage.execution · stage.compose → llm.stream_chat
├ history.write (history_status)
└ session.lease_release
```

- Router (`routers/chat.py`) tạo trace; `routers/sse.py` kích hoạt trace suốt stream,
  đóng khi stream kết thúc (xong, lỗi, client ngắt), log một dòng `chat_trace`
  (outcome, duration, first_delta_ms, số span/LLM/tool, token thật, lỗi gốc,
  `tool_errors`) và lưu vào
  `public.chat_traces` qua `TraceRepository` (session DB riêng, shield khi bị huỷ,
  lỗi chỉ log) khi `CHAT_TRACE_PERSIST=true`. Lỗi trước khi stream (401/404/409/422)
  không lưu trace.
- Token thật: `OpenAIProvider` ghi usage của `chat_complete_json`, `chat_complete_text`,
  `stream_chat` (`stream_options.include_usage`) và `embed` vào span; runner ghi usage
  của `chat_complete_tools`. `chat_history.input_tokens/output_tokens/cost_usd` vẫn là
  ước tính, chưa đổi sang usage thật.
- Chỉ metadata: không ghi nội dung tin nhắn, câu hỏi agent viết, argument/output tool,
  prompt, câu trả lời hay `crm_access_token`. `Span.set` cắt chuỗi 120 ký tự, list 20
  phần tử; tối đa `CHAT_TRACE_MAX_SPANS` span/trace (vượt thì đếm `dropped_spans`).
- Không có trace đang chạy (test, learning_ai) thì `span()` là no-op.
- Chưa có: OpenTelemetry/OTLP, truyền `traceparent`/`X-Request-ID` sang CRM API và
  OpenAI, lấy mẫu, retention, giao diện waterfall, tracing cho `/ai/learning`.

## Các lớp và trách nhiệm

| Lớp | Trách nhiệm | Không nên làm |
|---|---|---|
| API router | HTTP/SSE transport, dependency wiring, error mapping | Gọi LLM, chứa detector/business rule |
| Schema | Contract version, validation, giới hạn input | Quyết định orchestration |
| `ChatbotService` | Điều phối session và stages, lifecycle history | Chứa provider implementation |
| Stage | Một bước domain có typed state/decision | Tạo HTTP response |
| `AgentRunner` | Vòng lặp tool-calling, giới hạn, deadline, trace | Chứa logic của từng tool, render tool vào prompt |
| `ToolRegistry` / tool | Contract tool, chuẩn hóa schema, kiểm quyền, invoke an toàn | Ghi state cha ngoài `ToolContext`, tạo task chạy ngầm |
| Provider | Adapter cho OpenAI/LLM, khai báo capability | Policy/security/routing |
| Repository | Query/write Supabase | Trả SSE hoặc biết UI |
| Frontend service | POST và parse SSE | Tự quyết định trạng thái backend |

## API surface hiện tại

Đang public: `GET /health`, `GET /health/db`, `POST /chat/website` và
`POST /chat/crm` (service key server-to-server, đúng kênh)
và các GET `/chatbot/...` của Support Workspace (kể cả `/trace`). Module `learning_ai` cung cấp
`POST /ai/learning` và các endpoint support-chat khi `LEARNING_API_ENABLED=true`
(xem mục dưới). Quyền nhân viên CRM theo `user_id`, ownership cho các GET history, chống xử lý trùng
theo `Idempotency-Key` và production readiness/schema checks là phạm vi chưa
hoàn thiện.

## Luồng ingest tài liệu kỹ thuật (`doc_ingest`): thiết kế và trạng thái

Mục tiêu: biến PDF manual (F54, F86, ...) thành element đã chuẩn hóa, rồi thành
chunk/fact/asset có provenance, qua người duyệt, rồi nạp vào `doc_chunks` để
`match_doc_chunks` truy xuất. Module nằm ở `backend/app/modules/doc_ingest/`, là
**tool offline chạy bằng CLI** trong venv riêng `.venv-ingest`
(`backend/requirements-ingest.txt`: Docling, docling-core, pypdfium2, pydantic, PyYAML).
Module chatbot và image dịch vụ chat không được import/cài gói này.

**Trạng thái tổng quát (2026-11-03):** xong P-1 Parsing Spike trên F54, khung
module độc lập, fixture golden F54 (BL-02), khóa baseline F86 (BL-03). **Contract
C1 đã khóa** (D-02, D-03, D-04 mô hình dữ liệu, D-08, D-11; rev 3 đổi T-01 sang
biên cột theo khe trắng). Đã có code và test cho: schema, profile cấu hình, chuẩn
hóa **bảng** (T-01…T-05, T-15), parse mã parameter và ghi chú áp dụng trên cell
(T-12, T-13), review queue, lõi approval theo unit. **Chưa có pipeline PDF →
chunk đầy đủ**: chưa có V-02…V-04, builder, trích fact, CLI review,
publish. Đã có CLI `run` (PDF → Docling → chuẩn hóa bảng → thư mục chạy + báo cáo
HTML từng bước) để kiểm thử bằng file thật. Dữ liệu `doc_chunks` vẫn là chunk F86
biên soạn tay, nạp bằng `chunking_loader/load_csv.py`.

**Cập nhật 2026-11-09 — chunk builder (BL-16, contract C2):** giai đoạn 2 `build` đọc thư mục
chạy đã chuẩn hóa + manifest, sinh chunk nháp (`build/chunks.jsonl`, `DraftChunk` độc lập với
bảng) + adapter ra dòng `doc_chunks` hiện tại (`build/doc_chunks_v1.jsonl`) + kiểm chất lượng
(`build/chunk_quality.json`, `report/chunks.html`). **Không ghi DB; luồng tra cứu chatbot không
đổi.** Chưa có: phần tiếng Việt (Bước 3), đánh giá tra cứu offline (Bước 4), loader/xuất bản.

**Cấu trúc và ranh giới module:**

```text
backend/app/modules/doc_ingest/
  geometry.py          BBox, parse_pages, overlap_ratio — thuần Python, dùng lại cho S1
  schemas/             Pydantic extra="forbid": normalized.py (LogicalTable, ApplicabilityCandidate
                       = ứng viên T-13, Applicability = của fact/BL-17, ReviewItem, LogEntry),
                       profile.py, review.py (KnowledgeUnit, ApprovalRecord), run.py (RunReport)
  profile.py           nạp profile YAML (extends, vocabulary_file), profile_hash
  profiles/            default.yaml, qs_controller.yaml, registry_snapshot.json (chép registry chatbot)
  normalize/           docling_reader.py (Docling JSON dict -> RawItem, bbox gốc trên-trái; đi vào con
                       của mọi phần tử nên đọc được caption), coverage.py (T-16: phân loại nhãn,
                       mục lục giữ nguyên, nhãn chưa hỗ trợ -> unsupported_element),
                       tables.py (T-01..T-05, T-15 + gọi T-12/T-13), recorder.py (review/log),
                       pages.py (T-17 xác nhận header/footer theo lặp nhiều trang, chữ trong hình
                       -> figure_text; T-06 trang in), sections.py (T-07 section path theo số),
                       figures.py (T-18 nhãn sát hình, T-09 screenshot, T-10 watermark, T-19
                       hình trùng, T-11 caption, T-14 vùng crop), lists.py (T-08 v1 list
                       cha–con theo lề trái), text_refs.py (T-12/T-13 trên text, T-08 v1.1),
                       elements.py (ghép NormalizedElement ->
                       normalized/elements.jsonl)
  validate/coverage.py V-01 độ phủ text: từ text layer (words.json) so với nội dung giữ lại
  s0.py                S0: quyết định OCR theo trang (text layer missing/poor), ocr_required
  parse/profile_probe.py  S0 đo trang bằng pypdfium2 (ký tự, ký tự lỗi, bitmap, path, xoay, page label)
  parse/pdf_probe.py   page_objects: bitmap (+ px, hash nội dung) và nét vector từng trang -> raw/p{n}.objects.json;
                       đối tượng trong Form XObject lấy bounds của form
  technical_refs/      params.py (ParamRef, T-12; find_param_refs quét text), applicability.py (T-13)
  eval/                profile_fit.py (độ khớp profile, tín hiệu cảnh báo), labels.py + score.py + render.py
                       (lệnh `eval`: chấm theo nhãn mẫu tests/doc_ingest/fixtures/eval → report/eval.*)
  manifest.py, manifests/  DocManifest (doc_id theo quy ước CSV, doc_type, model, scope + luật scope, bucket)
                       cho chunk builder; f54.yaml, f86_installation.yaml, f86_operation.yaml (contract C2 §3)
  build/               chunk builder BL-16 (giai đoạn 2, đọc thư mục chạy có sẵn, không parse lại PDF):
                       loader.py, chunker.py (khối label heading → đơn vị → cửa sổ cha ≤ 2.500), render.py,
                       fields.py (scope, interface, từ khóa, embed_text, assets, review), assertions.py
                       (CQ-01…CQ-10, BL-15), quality.py (độ phủ, ranh giới theo nhãn, so CSV tay, cổng 2b),
                       builder.py (ghi build/*.jsonl, chunk_quality.json, chunk_review.json)
  export/doc_chunks_v1.py  DraftChunk → dòng bảng doc_chunks hiện tại (trường ứng viên C2 §13 vào metadata)
  report/chunks_report.py  report/chunks.html: trang duyệt chunk (cổng, CQ, độ phủ, ranh giới, so CSV, thẻ chunk)
  parse/figure_ocr.py  lệnh `figure-ocr`: RapidOCR (torch, có sẵn) trên ảnh crop hình ở trang có text layer
                       → build/figure_ocr.jsonl (chỉ làm từ khóa)
  review/approval.py   trạng thái unit, luật phục vụ, approval gate, giữ approval (theo id,
                       id đổi thì khớp duy nhất theo hash), duyệt hàng loạt theo rủi ro,
                       luật xuất bản (phụ thuộc, conflict)
  pipeline.py          một lần chạy: chuẩn hóa, ghi data/ingest_runs/{doc_id}/{run_id}/ (contract §1),
                       trạng thái bước tính từ module có thật, cảnh báo bảng bị cắt bởi tập trang
  report/html_report.py  report/index.html tự chứa: tổng quan + trạng thái bước, theo trang
                       (ảnh + khung element + biên cột), theo bảng (lưới Docling thô cạnh bảng logic,
                       tô màu T-01/T-02/T-05/T-15, ứng viên T-13), review queue, log
  cli.py               `run --pdf ... | --raw-dir ...` (gọi `build` ở cuối khi có manifest), `eval`, `build`,
                       `figure-ocr` (Docling chỉ import khi cần parse/render PDF)
  parse/               nơi duy nhất (cùng spike/) được import docling, pypdfium2, PIL
    docling_runner.py  build_converter (spike dùng chung), convert_pages, render_pages
    pdf_probe.py       page_label (/PageLabels), image_objects (bitmap nhúng), count_path_objects
    make_fixture.py    CLI: output spike + PDF -> fixture golden (bỏ ảnh, kèm bitmaps.json)
  spike/               công cụ đo P-1 (dùng geometry + parse/pdf_probe)
backend/tests/doc_ingest/
  conftest.py          marker requires_docling: tự skip khi venv không có Docling
  fixtures/docling/f54/  p{n}.docling.json + p{n}.bitmaps.json + README (sha256 PDF, version)
  synthetic.py, f54.py   fixture tổng hợp (SynPage) + helper chạy chuẩn hóa trên F54
  test_import_boundary.py, test_geometry.py, test_f54_fixture.py, test_f86_baseline.py
  test_logical_table.py, test_header_classification.py, test_applicability.py,
  test_approval.py, test_profile_isolation.py   5 nhóm test theo quyết định C1
backend/tests/chatbot/test_registry_snapshot.py   snapshot từ vựng khớp REGISTRY (venv chính)
```

- `doc_ingest` chỉ import `app.modules.doc_ingest.*` trong `app` (không
  `app.core`, `app.db`, chatbot, learning_ai, chunking_loader); phần còn lại của
  `app` không import `doc_ingest`. `test_import_boundary.py` kiểm cả hai chiều
  bằng AST.
- `backend/.dockerignore` loại `app/modules/doc_ingest/` và
  `requirements-ingest.txt` khỏi image dịch vụ chat.
- Test chạy ở hai venv (thư mục `backend`):
  - `.\venv\Scripts\python.exe -m pytest tests`: test thuần của doc_ingest chạy, test `requires_docling` bị skip;
  - `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest`: chạy đủ, kể cả validate `DoclingDocument`.
- Test thuần chỉ đọc fixture JSON, không cần PDF. Fixture sinh lại bằng
  `make_fixture` (lệnh trong README của fixture).
- `schemas/`, `profile.py`, `normalize/`, `technical_refs/`, `review/` chỉ dùng
  pydantic + PyYAML (có sẵn ở cả hai venv) và không import Docling, nên 5 nhóm test
  C1 (LT, HC, AP, HA, PI; [p1_golden_tests.md §6](reports/p1_golden_tests.md#6-bộ-test-theo-nhóm-quyết-định-c1-rev-3))
  chạy được ở cả hai venv.

```text
[P-1] Parsing spike (Docling)         XONG cho F54 (11 trang); báo cáo chờ người duyệt ký
                                      F86: PDF đã có trong source/, CHƯA chạy (BL-13, D-07)
[S0]  Hồ sơ tài liệu (đo trang, chọn OCR/cấu hình)   CÓ CODE + TEST (BL-24): OCR theo trang bằng
                                      RapidOCR backend torch; F86 Operation không có text layer
[C1]  Contract artifact ingest        ĐÃ KHÓA 2026-11-03 (rev 3)
[S1]  Chuẩn hóa deterministic T-01..T-15
      bảng: T-01..T-05, T-15 + T-12/T-13 trên cell   CÓ CODE + TEST (BL-05, BL-06, BL-11 phần bảng, BL-27)
      T-17 header/footer, T-06 trang in, T-07 section path   CÓ CODE + TEST (BL-07, BL-08)
      hình: T-18, T-09 screenshot, T-10 watermark, T-11 caption, T-14 crop + render
                                      CÓ CODE + TEST (BL-10)
      list cha–con T-08 v1 (lề trái + glyph phụ, nối qua trang)   CÓ CODE + TEST (BL-09)
      T-12/T-13 trên text (mã + vị trí + vai trò), T-08 v1.1   CÓ CODE + TEST (BL-11)
[Profile] Profile cấu hình (default, qs_controller)  CÓ CODE + TEST (BL-26, BL-29)
[T-16] Phân loại nhãn Docling        CÓ CODE + TEST (BL-33): mục lục giữ, nhãn lạ -> review
[V]   Kiểm bất biến V-01..V-04        V-01 CÓ CODE + TEST (ngưỡng tạm, D-12 mở); V-02..V-04 chưa có
                                      (BL-25): đối chiếu bảng với text layer, bất biến bảng, cấu trúc trang
[S2]  Screenshot/hình -> asset        ảnh crop ở normalized/images/ (BL-10); asset + unit duyệt hình,
                                      lưu storage chưa có code (BL-19, BL-90)
[S3]  Trích fact (parameter, I/O)     HOLD: chờ S1 + D-04, D-10
[Build] Chunk builder baseline        HOLD: chờ S1 đạt golden test + thư viện CQ (BL-15, BL-16)
[Review] Knowledge unit + HITL + CLI  lõi approval có code + test (BL-18, BL-20 phần lõi);
                                      gán unit từ builder, review_events, CLI chưa có (BL-19, BL-21)
[Publish] Gói đã duyệt -> Supabase    phạm vi 3, chưa lên kế hoạch (BL-90..BL-94)
```

**Kiểm thử bằng file PDF (CLI `run`, thư mục `backend`):**

```powershell
# PDF thật: Docling ~6–19 s/trang, nên chọn trang
..\.venv-ingest\Scripts\python.exe -m app.modules.doc_ingest.cli run --pdf "<file.pdf>" --pages 11,14,167-171 --doc-id f54 --profile qs_controller
# Chạy lại chuẩn hóa trên Docling JSON đã lưu (fixture hoặc raw/ của lần chạy trước), không cần Docling
.\venv\Scripts\python.exe -m app.modules.doc_ingest.cli run --raw-dir tests\doc_ingest\fixtures\docling\f54 --doc-id f54
```

- Output: `data/ingest_runs/{doc_id}/{run_id}/` (gitignored) gồm `raw/`, `normalized/`,
  `pages/` (ảnh trang khi có PDF), `run_report.json`, `report/index.html` (mở bằng
  trình duyệt).
- Báo cáo có bảng V-01 theo trang (độ phủ, trùng, token thiếu), mục lục (T-16) và phần
  tử nhãn chưa hỗ trợ. V-01 cần `p{n}.words.json`: tự sinh khi có `--pdf`; `--raw-dir`
  không có words thì báo "V-01 không chạy".
- Báo cáo hiển thị bước chưa có code là "chưa triển khai". Applicability là **ứng viên
  T-13**, không phải fact. ID bảng là định danh của lần chạy; so giữa các lần chạy dùng
  content hash. Bảng chạm biên của tập trang đã chọn được gắn nhãn "có thể bị cắt".
- Chưa có upload qua web (cần auth admin, H-9); không chạy được từ dịch vụ chat.

**Spike (`doc_ingest/spike/`):**

| File | Vai trò |
|---|---|
| `run_spike.py` | Chạy Docling **một lần** mỗi trang (helper hình học/pdfium lấy từ `geometry.py`, `parse/pdf_probe.py`) (`do_ocr=False`, TableFormer `accurate`, `images_scale=2`), đọc cả lớp `BODY` + `FURNITURE` (footer `Page \| N`), đo phủ bitmap/số path vector trong picture, crop lại picture bằng pypdfium2 ở scale 2/3/4 (đường `page_render_crop`), đọc `/PageLabels`. Xuất `p{n}.json`, `p{n}_items.json`, `p{n}_overlay.png`, `p{n}_tables.html`, `p{n}_pictures/`, `summary.json` |
| `render_review.py` | Dựng `index.html` và `p{n}_tables.html` để người duyệt so crop bảng/hình với HTML Docling dựng |

Chạy (thư mục `backend`):
`..\.venv-ingest\Scripts\python.exe -m app.modules.doc_ingest.spike.run_spike --pdf "<pdf>" --doc f54 --pages 9,11,14,18,19,40,167-171 --out ..\docs\ai\doc_ingest_spike\output`.
PDF nguồn (`docs/ai/doc_ingest_spike/source/`), output spike và
`data/ingest_runs/` đều gitignored.

Kết luận chính của spike F54 (chi tiết ở
[reports/parsing_spike.md](reports/parsing_spike.md)):

- Chỉ số cột của TableFormer không tin được (trang 11 đảo cột, trang 169 mất cả
  cột trống, trang 168 cờ header gắn vào dòng dữ liệu) → S1 dựng bảng từ bbox của
  cell (biên cột theo khe trắng giữa các cụm cell, contract rev 3), nối bảng qua
  trang và kế thừa header.
- PDF không có `/PageLabels`; `printed_page` lấy từ chuỗi số tăng dần ở footer
  (T-06 rev 2), manifest chỉ để ghi đè; không suy từ offset.
- Screenshot bị nhận là `table` 0×0; watermark bị nhận là `picture`; caption có
  thể gắn nhầm vào bảng; `level` của heading luôn bằng 1 nên section path phải
  dựng từ mẫu đánh số.
- Mã parameter có dạng đơn/dải/danh sách; D-01 chốt khớp chỉ qua
  `param_codes int[]` tường minh.

**Nguyên tắc pipeline chung (contract rev 2):** pipeline xử lý mọi PDF được nạp
mà không biết trước lỗi cấu trúc.
- Luật T-xx chỉ dùng tín hiệu hình học/cấu trúc với sai số tương đối và không
  tham chiếu tài liệu cụ thể.
- Tri thức miền/ngôn ngữ (mẫu mã, cụm từ điều kiện, từ khóa caption, registry
  model) nằm trong profile cấu hình; profile `default` hoàn toàn chung.
- Lỗi chưa biết được bắt bằng S0 (đo trước) và V-xx (so với text layer PDF và
  các bất biến cấu trúc). Kết quả thành mục review / cờ trên knowledge unit,
  không thành dữ liệu sai im lặng.
- Lỗi hợp lệ về hình thức không phát hiện tự động hoàn toàn được, nên duyệt bắt
  buộc theo mức rủi ro vẫn là yêu cầu cứng.

Tài liệu thiết kế (contract C1 đã khóa; S0, V-xx, builder vẫn là đặc tả chưa có code):
[p1_chunking_impact_assessment.md](reports/p1_chunking_impact_assessment.md)
(vấn đề, quyết định D-xx, GO/HOLD),
[p1_normalization_contract.md](reports/p1_normalization_contract.md)
(`NormalizedElement`, `LogicalTable`, bố cục `data/ingest_runs/{doc_id}/{run_id}/`),
[p1_golden_tests.md](reports/p1_golden_tests.md) (GT/CQ/RB),
[p1_implementation_backlog.md](reports/p1_implementation_backlog.md) (BL-xx).

## Luồng học tri thức (`learning_ai`): thiết kế và trạng thái

Mục tiêu: biến hội thoại hỗ trợ / tài liệu thành `KnowledgeRecord` có cấu trúc,
được người duyệt, rồi chia chunk và index cho chatbot truy xuất. Module nằm ở
`backend/app/modules/learning_ai/`.

**Trạng thái tổng quát:** phần lõi domain thuần (schema, validate, conflict rule,
lifecycle, chunking, indexer logic) đã có và có unit test tại
`backend/tests/learning_ai/`. `POST /ai/learning` (sau cờ `LEARNING_API_ENABLED`,
chưa có auth) chạy được bước [1]: ingestion → prefilter → privacy.
**Chưa có luồng end-to-end tới tri thức**: chưa có lời gọi LLM segment/extract,
persistence Supabase (job, record), outbox, embedding hay vector index.

```text
[0] POST /ai/learning                 chạy [1]; chỉ include khi LEARNING_API_ENABLED=true, chưa có auth
[1] Ingestion -> SourceDocument       có logic + service, đã nối route [0] (chưa có bảng job)
      prefilter -> privacy A..D       Ollama bắt buộc, fail-closed (xem mục Privacy bên dưới)
[2] Pass 1 Segmenter (LLM)            chỉ có schema Segment/SegmentationOutput
[3] Pass 2 Extractor (LLM, strict)    có schema + to_strict_schema (inject enum registry);
                                      chưa có prompt/provider call
[4] assemble_draft -> DRAFT record    có logic (hệ thống gán ID/provenance/privacy/source_id)
[5] validate_record                   có logic: locator bịa, basis<->role, mã registry,
                                      classification<->content, registry drift
[6] detect_rule_conflicts             rule cho parameter/spec/wiring có;
                                      so sánh ngữ nghĩa + tra candidate từ DB chưa có
[7] Review lifecycle + approval_gate  có logic thuần; chưa có persistence/API/UI review
[8] Outbox -> sync_record             build_chunks + embedding_text + upsert idempotent có;
                                      Embedder/SearchIndex chỉ là Protocol, chưa có outbox
[9] Chatbot retrieval theo ChunkFilters  chưa nối
```

| File | Vai trò |
|---|---|
| `schemas/knowledge_record.py`, `content.py`, `common.py` | Record chuẩn, content theo 5 loại (wiring, procedure, parameter_config, troubleshooting, spec_fact), Claim có basis + evidence |
| `schemas/llm_output.py` | DTO đầu ra LLM 2 pass và chuyển Pydantic sang JSON Schema strict |
| `schemas/registry.py` | `RegistrySnapshot` dùng chung với query extraction |
| `extraction/assembler.py`, `validators.py` | Ghép DTO thành draft, kiểm tra deterministic hậu-LLM |
| `review/conflict_detector.py`, `lifecycle.py` | Xung đột theo luật, state machine, approval gate, revision bất biến |
| `chunking/*`, `indexing/indexer.py` | Chunk theo loại tri thức, embedding text, đồng bộ index idempotent |
| `repositories/support_chat_repository.py` | Đọc session và message từ `public.support_chat_test_sessions` / `public.history_support_chat` theo `message_no` |
| `ingestion/source_document.py`, `prefilter.py`, `service.py` | Dựng document có locator, lọc hội thoại vô giá trị, điều phối nạp → lọc → privacy |
| `privacy/*` | Regex PII/giá, chia cửa sổ, kiểm tra bằng Ollama, thay placeholder |

### Nguồn và ingestion

Nguồn là hội thoại CRM giữa nhân viên thật và khách trong
`public.history_support_chat` (`id`, `session_id`, `message_no`, `sender_role`,
`message_text`, `created_at`) tham chiếu `public.support_chat_test_sessions`.
Bảng do Supabase quản lý; ứng dụng đọc qua repository. Mỗi row là một message;
locator `m1..mN` liên tục theo `message_no`, message rỗng bị bỏ. `source_id` là UUIDv5 của
`session_id` + hash nội dung, nên ổn định khi nội dung không đổi.

Prefilter chạy trước mọi lời gọi model và chỉ skip khi chắc chắn: thiếu tin nhắn
khách, thiếu tin nhắn nhân viên, mọi message chỉ gồm từ chào hỏi/cảm ơn/xác nhận/đại
từ, hoặc nội dung có nghĩa dưới 40 ký tự. Một message có bất kỳ từ khác, chữ số hoặc mã
registry thì không bị coi là chào hỏi ("xin chào, tôi cần giới thiệu về F86" được giữ).

`LearningIngestionService.prepare(session_id)` trả `IngestionResult` với status
`ready | skipped | privacy_unavailable`. Kết quả chưa được lưu lại vì chưa có bảng job.

### Privacy (bắt buộc trước khi dữ liệu rời server)

```text
A  regex       email, SĐT, IPv4, CCCD/CMND/MST/STK (chỉ khi có từ khoá), giá
B  Ollama      theo cửa sổ: PII phi cấu trúc + pricing / policy / customer_specific
C  redactor    kiểm span có thật, thay placeholder; thực thể PII thay ở MỌI message
D  regex lại   trên kết quả cuối, che nốt nếu còn sót
```

- Ollama nhận text đã che ở tầng A. Model chỉ báo cáo
  `{reviewed_locators, findings[{locator, category, type, text}]}`; hệ thống quyết
  định hành động: `pii` và `pricing` bị thay placeholder (`[PERSON_1]`, `[PRICE_1]`),
  `policy` và `customer_specific` giữ text, gắn cờ trong `flags_by_locator`.
- Fail-closed: provider lỗi, output sai schema, hoặc `reviewed_locators` thiếu message
  mục tiêu → cả document `privacy_unavailable`, không có kết quả một phần.
- Finding có `text` không phải chuỗi con nguyên văn, hoặc locator ngoài cửa sổ, bị loại
  và đếm vào `unverified_findings`.
- Hội thoại dài: gom message nguyên vẹn tới `OLLAMA_WINDOW_TOKENS` (tiktoken × 1,5), kèm
  2 message trước làm ngữ cảnh, và gửi danh sách thực thể đã tìm thấy sang cửa sổ sau.
  Endpoint OpenAI-compatible của Ollama không đặt được `num_ctx` theo request: phải
  đặt `PARAMETER num_ctx` trong Modelfile và khai báo `OLLAMA_NUM_CTX` khớp. Provider
  coi prompt chạm 95% `num_ctx` là đã bị cắt. Kiểm tra `reviewed_locators` là chốt
  chặn cuối khi giá trị cấu hình lệch với Modelfile.
- Regex giá phân biệt đơn vị tiền rõ nghĩa (đ, đồng, vnđ, usd, $), đơn vị số lượng
  (ngàn, nghìn, triệu, tỷ, củ — bỏ qua khi theo sau là danh từ kỹ thuật như "xung",
  "vòng"), đơn vị mơ hồ (k, tr) và tiếng lóng (lít, xị — cần từ khoá giá).
- Thay thế toàn document không phân biệt hoa/thường, ưu tiên không lọt hơn chính xác.
  Giá trị gốc của placeholder không được lưu.

Giới hạn đã biết của thiết kế hiện tại:

- `chatbot/extraction/registry.py` chưa có các key `topics`, `connectors`,
  `parameters`, `alarm_codes` mà `FIELD_TO_REGISTRY_KEY` cần, nên với registry thật
  `validate_registry` sẽ báo `unknown_code` cho các trường này.
  `learning_ai/extraction/registry.py` đang là file rỗng.
- `approval_gate` không tự chạy `validate_record` / conflict detection; service
  điều phối (chưa có) phải bảo đảm thứ tự đó.

Khi thay đổi flow, cần cập nhật đồng thời schema/API contract, service/stage,
repository/provider boundary, test và tài liệu này. Không mô tả scaffold hoặc
stub như tính năng đã sẵn sàng.
