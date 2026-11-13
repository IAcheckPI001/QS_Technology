# Lưu trữ luồng website-qa tới 2026-11-11

Chép nguyên văn ngày 2026-11-11 khi tách tài liệu theo luồng (D-002). Không sửa file này;
trạng thái hiện tại ở [STATE.md](STATE.md), lịch sử mới ở [LOG.md](LOG.md). Phần lấy từ
`current-state.md` giữ nguyên tiếng Anh như bản gốc.

- Sơ đồ và bước 1–11 dưới đây mô tả cả `POST /chat/crm` khi `CRM_CHAT_FLOW=pipeline`; bước 3
  (session, lease) nay thuộc [chat-platform](../chat-platform/README.md).


## Từ `architecture.md`: mục "Luồng `POST /chat/website` (và `POST /chat/crm`)"


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


## Từ `current-state.md`: dòng P5 của "Completion summary"

| P5 active chatbot pipeline | Partially implemented | Security, context loading (with persisted `ConversationState`), pruning, the clarification loop (deterministic resume, `pending_answer`, held sub-queries, 2-attempt limit), analysis, execution-plan execution, fixed replies for chitchat/out_of_scope/handoff-only turns and provider final-answer streaming run. Retrieval is wired at test level: one retrieve task per sub-query, filtered hybrid search (vector + FTS, RRF, parent expansion) over `doc_chunks` via `match_doc_chunks` (`backend/sql/doc_chunks.sql`, applied manually), sources rendered into the answer prompt. Not verified against live Supabase; retrieval parameters are untuned starting values. Handoff is a scaffold: `DisabledHandoffProvider` creates no ticket, so `mode` stays `bot`. Requires the `conversation_state` column migration (not verified live). |

## Từ `current-state.md`: rủi ro 4a và 9

4a. **Handoff is a stub (H1) and source numbers restart each turn (H6)**
   - `DisabledHandoffProvider` returns `None` while the reply promises a human
     agent; `[S#]` citations are not persisted, so numbering restarts at S1.
   - Both deferred; see `docs/ai/reports/diagram_request_handler.html` §11.


9. **Retrieval is test-level and final answer lacks side effects**
   - Retrieve runs per sub-query against `doc_chunks`, but there is no rerank,
     no SSE event for sources/assets (images), no `unaccent` on FTS, and
     `RETRIEVAL_MIN_SIMILARITY` / top-k values are untuned. AnalysisStage only
     extracts `domain`, `scopes`, `product_models`, `control_interface`,
     `spec_attributes`; `chunk_type`, `doc_type`, `keywords` are not used yet.
   - Handoff uses `DisabledHandoffProvider`: no ticket, no forwarding to an
     agent platform, no way back to `mode=bot`. Agent-mode short-circuit exists
     but is only reachable when a real provider returns a ticket.
   - `ConversationState` is persisted in `public.chat_history.conversation_state`
     (jsonb, nullable). The column must be added manually in Supabase:
     `alter table public.chat_history add column conversation_state jsonb null;`
     Not verified against the live table.


## Từ `current-state.md`: việc 12c

12c. Product model codes follow CRM `product_name` (F54, F86, F86E, F10T, 6AH,
     6AHE, 6AV, 6AVE, 10iV, 10iVE). `ASTRO_10S` was removed; old `ASTRO_*` codes
     still resolve through alias normalization ("Astro 6AH" = "ASTRO_6AH" → 6AH);
     "10i"/"Astro 10i" is ambiguous (10iV/10iVE). **Provisional data:**
     capabilities of F86E/6AHE/6AVE copy the base model and 10iV/10iVE copy the
     old 10i row; `doc_chunks` chunks tagged `ASTRO_10I` are mapped to `10iV`.
     Existing Supabase data needs `backend/sql/migrate_product_models_crm.sql`
     (run manually; stops if chunks still carry `ASTRO_10S`). Model matching in
     text now requires a code boundary ("6AH" does not match inside "6AHE"), so
     codes glued to Vietnamese words ("F86có") are no longer detected.

## Từ `current-state.md`: các mục "Validation record" của pipeline

- Backend pytest via `backend\venv\Scripts\python.exe -m pytest` (2026-10-19):
  **152 passed, 5 failed**. All 104 `tests/learning_ai` tests pass. The 5 failures are
  in `tests/chatbot/test_chat_history.py` and `test_context_pipeline.py`: the tests
  are out of sync with the in-progress chatbot refactor (`Prune.execute` signature,
  `ContextLoader.resolve_retrieval_scope`, `FakeProvider.chat_complete_json`,
  undefined `ContextConfigurationError`).
- Backend pytest after wiring execution + answer composition (2026-10-20):
  **164 passed, 5 failed**; the same 5 pre-existing chatbot failures.
- Backend pytest after fixed replies + clarification loop + handoff scaffold
  (2026-10-20): **182 passed, 5 failed**; the same 5 pre-existing failures.
- Backend pytest after P0 (pipeline error handling, `analysis_error`, clarification
  cases A/B/C) (2026-10-24): **211 passed, 3 failed**. Remaining failures are in
  `tests/chatbot/test_context_pipeline.py`: `Prune.token_counter` signature and
  `ContextLoader.resolve_retrieval_scope` (missing `Branch` import/staticmethod),
  scheduled as P1.
- Fix after live test (2026-10-24): `RetrievalQuery.answer_mode` rejected
  `general` (retrieve task failed with `retrieval_error`); both schemas now share
  `AnswerMode`. The LLM `general` flag is gated by `allow_general` and
  `MODEL_SPECIFIC_PATTERN`. Backend pytest: **216 passed, 3 failed** (same P1
  failures).
- Backend pytest after P1 (Prune/CRM fixes, logging, error-row commit test,
  `last_models`/`active_model`, non-blocking pending, multilingual) (2026-10-24):
  **232 passed, 0 failed**.
- Empty analysis output (`sub_queries=[]` without pending, e.g. a statement with
  no question) is now answered as chitchat instead of `analysis_error`
  (2026-10-29, M3 code layer). Prompt rule for statements → out_of_scope is
  deferred. Backend pytest: **297 passed, 0 failed**.

## Từ `current-state.md`: mục "Context/RAG pipeline"


`ContextLoader` runs after the security stage and reads model context only
through `HistoryRepository.list_for_context()`, which filters to completed
turns. A persisted turn is converted to deterministic `user` and `assistant`
message identifiers derived from its history ID. Summary loading is not
implemented yet, so `Conversation.summary` remains `None`.

`Prune` applies `CONTEXT_TOKEN_BUDGET` after context loading and before
analysis/provider work. It removes the oldest history turns first and never
truncates the current query. `AnalysisStage` then builds the analysis context,
calls `QueryAnalyzer` through `OpenAIProvider`. `ExecutionStage` builds and runs
the execution plan with deterministic handlers, and `AnswerComposer` streams the
final answer from the task results, including retrieved `<sources>`. On the CRM
channel (agent flow) the same clarification → analysis → execution steps run
inside the `product_docs_ask` tool via `RetrievalPipeline`, with
`CatalogLookupStage` between analysis and execution, and the agent writes the
final answer. Invalid configuration is an application/configuration
error; an unfit mandatory payload is a context-budget/domain error. Neither is
a security block.
