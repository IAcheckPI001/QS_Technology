# Lưu trữ chat-platform tới 2026-11-11

Chép nguyên văn ngày 2026-11-11 khi tách tài liệu theo luồng (D-002). Không sửa file này;
trạng thái hiện tại ở [STATE.md](STATE.md), lịch sử mới ở [LOG.md](LOG.md). Phần lấy từ
`current-state.md` giữ nguyên tiếng Anh như bản gốc.

- Số P trong "Completion summary" (P5 = pipeline chatbot, P6 = learning, P7 = doc_ingest) khác
  với "Next remediation order" (P5 = learning, P6 = doc_ingest); giữ như bản gốc.


## Từ `architecture.md`: "Startup và dependency", "Ba thành phần khi chạy"


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


## Từ `architecture.md`: "Persistence và session", "Tracing"


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


## Từ `architecture.md`: "API surface hiện tại"


Đang public: `GET /health`, `GET /health/db`, `POST /chat/website` và
`POST /chat/crm` (service key server-to-server, đúng kênh)
và các GET `/chatbot/...` của Support Workspace (kể cả `/trace`). Module `learning_ai` cung cấp
`POST /ai/learning` và các endpoint support-chat khi `LEARNING_API_ENABLED=true`
(xem mục dưới). Quyền nhân viên CRM theo `user_id`, ownership cho các GET history, chống xử lý trùng
theo `Idempotency-Key` và production readiness/schema checks là phạm vi chưa
hoàn thiện.


## Từ `current-state.md`: phần đầu "Scope"

## Scope

This document is the current status of the AI service: database,
configuration and chat history, the chatbot pipeline and CRM agent flow,
service-key auth, the knowledge learning pipeline (`learning_ai`) and the
technical document ingest tool (`doc_ingest`). It supersedes the original
findings-only review and distinguishes completed work from remaining
validation, deferred scope, and open risks.

The current request architecture is:

```text
Frontend
  -> FastAPI route / dependency
  -> ChatbotService
  -> SecurityStage
  -> ContextLoader
  -> Prune
  ├─ website / CRM with CRM_CHAT_FLOW=pipeline:
  │   -> AnalysisStage -> QueryAnalyzer -> OpenAIProvider
  │   -> ExecutionStage -> ExecutionScheduler -> deterministic task handlers
  │   -> AnswerComposer -> OpenAIProvider.stream_chat
  └─ CRM (default, experimental): AgentRunner ⇄ ToolRegistry (product_docs_ask)
  -> HistoryRepository -> Supabase public.chat_history
  -> SSE response
```

`SecurityStage` is implemented as a pre-context and pre-provider guard. It
normalizes the message, runs the injection detector and configured content
policy, and blocks context loading and provider calls when a finding is
present. A blocked request is still persisted as an audit record through an
independent database session. The stage does not log raw message text. Its typed
decision is internal; the client receives a generic `request_blocked` error.

Blocked requests are persisted in `public.chat_history` with
`status='blocked'`, the catalog response in `answer`, and no provider model or
usage. History views may include blocked records, but context construction must
query only `status='completed'`. Blocked persistence uses an independent
database session so provider/request transaction rollback cannot remove the
audit record.

FastAPI routes perform transport, dependency wiring and error mapping. The
service coordinates the stages, provider-specific calls remain behind the
provider layer, and database access remains in the repository layer.


## Từ `current-state.md`: các dòng P0–P4, P5c của "Completion summary"

| Area | Status | Summary |
|---|---|---|
| P0 importability and deployment configuration | Resolved in code/config | `Depends` is imported, `DATABASE_URL` is documented and passed through Compose. Clean-runtime and live-Supabase validation remain outstanding. |
| P1 ChatHistory persistence | Implemented, not production-verified | `ChatHistory`, repository, session ownership (`chat_sessions`), and completed/error/blocked/cancelled persistence are wired. The `error` row commit after streaming is verified by test on FastAPI 0.143 (see open risk 1); live insert validation remains open. |
| P2 configuration normalization | Resolved in implementation | One cached `pydantic-settings` model is used and model defaults are aligned. Pytest validation remains outstanding. |
| P3 history reads and ownership | Partially implemented | Support-chat session/message reads and session creation are available behind `LEARNING_API_ENABLED`; authentication and ownership are still deferred. |
| P4 health/readiness semantics | Open | Connectivity check exists, but readiness status/error semantics and schema checks are incomplete. |
| P5c request tracing (phase 0) | Implemented, unit-tested only | In-process span tree per `/chat/*` request (`app/core/tracing.py`, no new dependency): router, security/context/prune, pipeline stages, agent steps, tool calls, retrieval (embedding, `match_doc_chunks`), CRM API pages, compose, history writes. Real OpenAI usage is recorded on spans (analysis, compose stream, embeddings, agent steps). Every turn logs one `chat_trace` summary line; with `CHAT_TRACE_PERSIST=true` the trace is stored in `public.chat_traces` (`backend/sql/chat_traces.sql`, apply manually) and served by `GET /chatbot/sessions/{id}/trace`. Metadata only. Not verified against live Supabase/OpenAI; no OpenTelemetry export, no context propagation to CRM/OpenAI, no UI, no retention. |

## Từ `current-state.md`: "Finding status", "Implemented behavior"

## Finding status

| # | Previous finding | Current status | Evidence and remaining concern |
|---|---|---|---|
| 1 | Missing `DATABASE_URL` could block clean startup | **Resolved in tracked configuration; validation open** | `backend/.env.example` contains the placeholder and `docker-compose.yml` passes `${DATABASE_URL}`. A clean-container startup and live Supabase query still need verification. |
| 2 | Missing SQLAlchemy/database dependencies | **Resolved / false positive in current tree** | `backend/requirements.txt` contains `sqlalchemy`, `asyncpg`, and `pydantic-settings`. Installing and running the backend environment has not been verified here. |
| 3 | Missing `Depends` import | **Resolved** | `backend/app/api/v1/health.py` imports `Depends`; Python syntax validation passed. |
| 4 | `ChatSession`/repository `organization_id` mismatch | **Resolved by replacement** | The old session scaffold was removed. `backend/app/db/models/history.py` and `backend/app/modules/chatbot/repositories/history_repository.py` now represent `public.chat_history`. |
| 5 | No application migration/schema creation | **Partially resolved / externally managed** | The ORM mapping exists and Supabase owns the table. The application does not create or migrate the table, and `/health/db` only runs `SELECT 1`; schema compatibility is not checked automatically. |
| 6 | Successful writes were not committed | **Resolved; verified by test, depends on FastAPI version** | `backend/app/db/session.py` commits after the request. The router catches pipeline exceptions inside the SSE generator, so the `error` row is committed, not rolled back (`test_error_history_from_failed_stream_is_committed_not_rolled_back`, FastAPI 0.143). See open risk 1 for the minimum-version concern. |
| 7 | Chat route bypassed persistence | **Resolved** | The route injects `ChatbotService`, which writes history through `HistoryRepository`. Reads exist for the Support Workspace (`GET /chatbot/...`) without an ownership check (see medium-priority item 4). |
| 8 | Website string UUID and database UUID mismatch | **Resolved by replacement** | `session_id` is validated as a UUID by the request schema (422 otherwise) and resolved by `SessionAccessService` against `chat_sessions`; unknown or foreign IDs get `404 session_not_found` (see Session ID lifecycle). |
| 9 | Duplicated settings sources | **Resolved** | `backend/app/core/config.py` has one cached `Settings` model consumed by application and database code. |
| 10 | Health endpoint semantics were ambiguous | **Open** | `/health/db` exists, but unavailable-database status codes, structured error responses, readiness semantics, and schema-level checks are not finalized. |

## Implemented behavior

### Session ID lifecycle

1. Missing `session_id`: `SessionAccessService` creates a UUID and a
   `public.chat_sessions` row owned by the current principal and channel.
2. Existing UUID owned by the same principal (same channel, not revoked or
   expired): the same ID is reused.
3. Any other UUID (unknown, other owner, legacy session that exists only in
   `chat_history`): `404 session_not_found`; a non-UUID value is a 422.
4. The authoritative UUID is returned in the SSE `done` event and in the
   `X-Session-ID` response header.
5. The AI service authenticates only service keys bound to a channel
   (`backend/sql/service_keys.sql`, CLI `app.modules.chatbot.service_keys_cli`).
   The visitor-token flow was removed (2026-10-29).
6. Website: `widget-backend/` calls `POST /chat/website` with the website key.
   It keeps `session_id` in an HttpOnly cookie (`qs_chat_session`), issues an
   anonymous `qs_visitor` cookie that is never sent to the AI service, and on
   `session_not_found` clears the cookie and retries once. Website sessions are
   owned by the website integration.
7. CRM: CRM backends call `POST /chat/crm` and send `user_id`; CRM sessions are
   owned by (integration, `user_id`). The CRM widget keeps `session_id` in UI
   state and sends `null` for a new conversation.
8. `backend/sql/chat_sessions.sql` must be applied on Supabase first.

Starting a new conversation (cookie cleared by widget-backend, or `null`
`session_id` from CRM) does not delete historical database records. Deletion is
not currently implemented.

### Chat history writes

- The current service writes `status='completed'` after streaming the
  provider-generated answer. Retrieve tasks ground the answer in `doc_chunks`
  sources (`[S#]` citations in the text only).
- A provider or pipeline exception attempts to write `status='error'` with any
  partial answer.
- `normalized_query` stores the Vietnamese `standalone_query` of each
  sub-query (joined by newlines) once analysis has run. `input_tokens`,
  `output_tokens` and `cost_usd` are estimates from question/answer text only.
  `retrieved_chunk_ids` is not produced; `retrieval_snapshot` is used instead.
- Synthetic UUIDs and metrics are permitted only in local/test fixtures, never
  as fabricated production measurements.


## Từ `current-state.md`: rủi ro 1–3, 4b, 4–8, 10

## Open risks and deferred scope

### High priority

1. **Error history durability: verified in test, depends on FastAPI version**
   - `test_error_history_from_failed_stream_is_committed_not_rolled_back`
     (FastAPI 0.143.0) shows the `error` row is committed: the router catches
     the exception inside the SSE generator, so `get_db_session` exits normally
     and commits after streaming.
   - `requirements.txt` allows `fastapi>=0.115`. FastAPI 0.106–0.117 closed
     yield-dependencies before a `StreamingResponse` was sent; on those versions
     history writes during streaming would not be committed. Raising the
     minimum version is a dependency decision that has not been made yet.
   - Not verified against live Supabase.

2. **No live Supabase verification**
   - No verified `/health/db` request has been recorded.
   - No verified insert/select against `public.chat_history` has been recorded.
   - The ORM definition has not been compared automatically with the live table.

3. **Backend test suite**
   - Tests run with `backend\venv\Scripts\python.exe -m pytest` from `backend/`.
   - Last recorded full run: 679 passed, 12 skipped (2026-11-03); later
     entries in the validation record do not carry full-suite counts. See the
     validation record.

4b. **CRM service key: delegated trust, no per-user authorization yet**
   - `user_id` is asserted by the CRM backend; a leaked key can impersonate any
     employee of that integration. Mitigation today: revoke + reissue.
   - The CRM agent flow currently lets every employee use every registered
     tool. `ToolRegistry.allowed(principal)` and `ToolSpec.required_scope` are
     the hook for role/scope checks; nothing populates `principal.scopes` yet.
   - Deferred: employee permissions resolved from `user_id` (tools, assigned
     customers, learning access), an API to list/read a user's conversations,
     per-integration scopes, tenant isolation of `doc_chunks`/retrieval, rate
     limiting per key, `last_used_at` tracking.
   - `backend/sql/service_keys.sql` and the `acting_user_id` column in
     `chat_sessions.sql` are not applied/verified on live Supabase.

### Medium priority

4. **History reads have no ownership check**
   - `GET /chatbot/sessions/{id}/history`, `/retrieval` and
     `GET /chatbot/conversations` exist for the Support Workspace
     (`/support-workspace`) but are unauthenticated; `/chatbot/conversations`
     lists every session. Keep them internal until item 5 is solved.
   - `chat_history.channel`, `updated_date` and `retrieval_snapshot` require
     `backend/sql/chat_history_workspace.sql` on Supabase.
   - The Workspace "Hỗ trợ ticket" view uses support-chat sessions
     (`history_support_chat`); opening a `chat_history` session there shows a
     "not in support-chat" notice because the two tables do not share sessions.

5. **Ownership only on chat writes**
   - `POST /chat/*` binds sessions to the principal via `public.chat_sessions`
     (service key integration, plus `user_id` for CRM). The GET
     history/retrieval/conversation endpoints do not check authentication or
     ownership yet; Support Workspace calls them directly from the browser and
     widget-backend calls the history endpoint server-to-server.
   - Production history reads must remain disabled until ownership checks exist.

6. **Idempotency key stored, not enforced**
   - The frontend sends `Idempotency-Key` (one UUID per message, reused on
     retry); it is stored in `chat_history.idempotency_key`.
   - Duplicate detection/replay is not implemented: retries can still create
     duplicate history rows and LLM calls.

7. **Per-session turn lease; no idempotent replay**
   - A second request on a session whose turn is still running gets
     409 `session_busy` (`chat_sessions.turn_lease_until`, released when the
     SSE stream ends, expires after `CHAT_TURN_LEASE_S`). New sessions take no
     lease. Requires `backend/sql/chat_sessions.sql` on Supabase (not verified
     live).
   - The lease release is shielded against anyio cancellation (how Starlette
     cancels a stream); a raw `asyncio` task cancel can interrupt it, and the
     lease then expires on its TTL.
   - Found in live testing (2026-10-30): the first version also touched
     `last_activity_at` inside the request transaction, which holds the row
     lock until the stream ends; the lease UPDATE (separate connection) then
     waited on it until `statement_timeout`, so every resumed session hung ~30s
     (widget-backend 502). Fixed: the lease UPDATE sets `last_activity_at`,
     the request transaction no longer updates existing session rows, and lease
     statements use `lock_timeout = 3s`. Unit tests use fakes and cannot
     reproduce row locks; this path still needs live verification.
   - A retry sent while the original turn still runs is rejected by the lease;
     a retry after it finished runs again (no replay by `Idempotency-Key`).

### Lower priority

8. **Provider usage metadata is incomplete**
   - `chat_history.input_tokens`, `output_tokens` and `cost_usd` are estimates
     from the question and answer text (`count_tokens`); prompt context, analysis
     calls, agent steps and embeddings are not counted there.
   - Provider-reported usage is now collected per LLM/embedding call in the trace
     (`chat_trace` log line, `chat_traces.trace.summary`), but is not yet written
     back to `chat_history` or converted to cost.
   - `retrieved_chunk_ids` remains empty/null: the column is `UUID[]` while
     `doc_chunks.id` is `bigint`, so it needs a schema decision.

10. **Frontend lint baseline**
   - `npm run lint` still fails on existing unrelated frontend errors.
   - `npm run build` passes with an existing CSS syntax warning.


## Từ `current-state.md`: "Next remediation order" P1–P4 (trừ 12a–12d)

## Next remediation order

### P1 — Required before calling persistence complete

1. Decide the minimum FastAPI version (see open risk 1) so the verified
   commit-after-stream behavior of `status='error'`/`completed` rows holds.
2. Install/restore the backend test environment and run the focused tests.
3. Run the backend with the configured runtime environment.
4. Verify `/health/db` against Supabase.
5. Execute a real chat request and verify the inserted row in
   `public.chat_history`. Token/cost fields are estimates from question and
   answer text only (no prompt context, no embedding); replace with provider
   usage when available.

### P2 — Required before enabling history reads

6. ~~Add a `chat_history` read endpoint and repository query with explicit
   session ordering.~~ Done: `GET /chatbot/sessions/{session_id}/history`,
   `/retrieval` and `GET /chatbot/conversations` (no ownership check yet).
7. Decide whether reads support authenticated users, anonymous visitors, or
   both.
8. Anonymous website visitors are bound to sessions by widget-backend
   cookies; the AI service GET endpoints still need service-key auth.
9. For authenticated access, validate account ownership.
10. Add authorization tests for matching and mismatched session/token pairs.

### P3 — Reliability and data quality

11. Persist or otherwise enforce an idempotency key based on `message_id`.
12. ~~Define ordering/concurrency behavior for one session.~~ Done: per-session
    turn lease (409 `session_busy`).
13. Add provider usage extraction for token counts and cost.
14. Decide `retrieved_chunk_ids` type (`UUID[]` vs `doc_chunks.id bigint`) before persisting retrieval metadata.

### P4 — Operational hardening

15. Define `/health/db` as a readiness endpoint or diagnostic endpoint.
16. Return intentional non-2xx responses for unavailable dependencies.
17. Add schema compatibility checks for required `chat_history` columns.
18. Resolve or separately baseline the existing frontend lint failures.


## Từ `current-state.md`: các mục "Validation record" dùng chung

- Python syntax validation for changed backend modules: **passed**.
- `git diff --check`: **passed**.
- `npm run build`: **passed**, with the existing CSS warning
  `Unexpected ";"`.
- `npm run lint`: **failed** on pre-existing frontend unused-variable and
  undefined-symbol errors.
- Backend pytest after API gateway step (request ID outcome, channel endpoints,
  visitor token, `chat_sessions` ownership) (2026-10-28): **274 passed, 0 failed**.
  `npm run build` passed; `npm run lint` still fails on pre-existing errors in
  files outside this change.
- Backend pytest after high-risk fixes from
  `docs/ai/reports/diagram_request_handler.html` (H2 request log without message
  text, H3 `retrieval_status` in snapshot, H4 `cancelled` history on client
  disconnect, H5 per-field `conversation_state` recovery) (2026-10-29):
  **292 passed, 0 failed**. H1 (handoff stub) and H6 (`[S#]` restarts each turn)
  remain open.
- CRM service key auth (`/chat/crm`, `ServiceAuthService`, `acting_user_id`
  session ownership) (2026-10-29): **319 passed, 0 failed**. `npm run build`
  passed; `npm run lint` still fails on pre-existing errors in `src/`.
- AI service is service-key only (visitor token removed, keys bound to a
  channel, `X-Session-ID` header) and `widget-backend/` added (2026-10-29):
  backend pytest **311 passed, 0 failed**; `node --test` in `widget-backend`
  **15 passed**; `npm run build` passed; `npm run lint` unchanged (139
  pre-existing errors in `src/`). End-to-end against live Supabase: **not
  verified**. Backlog: rate limit in widget-backend, "new conversation" button
  (BFF has `POST /api/chat/reset`), docker-compose service for widget-backend,
  Support Workspace default session (no longer in `localStorage`).
- Turn-lease self-lock fix (2026-10-30): backend pytest **390 passed, 0 failed**.
  `test_session_access.py::test_owner_can_resume_session` now asserts that a
  resumed session is only read (previously asserted a `touch`). `npm run build`
  passed. Live re-test on Supabase pending.
- Request tracing phase 0 (2026-11-07): `app/core/tracing.py`, spans across router,
  service, `RetrievalPipeline`, `AgentRunner`, tools, `Retriever`, `CrmListClient` and
  `OpenAIProvider` (real usage), `TraceRepository` + `backend/sql/chat_traces.sql`,
  `GET /chatbot/sessions/{id}/trace`, settings `CHAT_TRACE_PERSIST` /
  `CHAT_TRACE_MAX_SPANS`. Run in the worktree with the main checkout's
  `backend\venv` and a placeholder `DATABASE_URL` (tests use fakes): backend pytest
  **762 passed, 14 skipped, 1 failed**. The failure is
  `test_f86_baseline_csv_unchanged`: the worktree checkout converts
  `doc_chunks_f86.csv` to CRLF, so its hash differs; unrelated to this change.
  New `tests/chatbot/test_tracing.py` (13 tests). Existing assertions unchanged.
  Frontend untouched; `npm run lint`/`build` not run (no `node_modules` in the
  worktree). `chat_traces` table and live persistence: **not verified**.
- Live Supabase connectivity/insert: **not verified**.

## Từ `current-state.md`: "Architectural impact"


The implemented request/write path follows the documented boundaries:

- API route: request validation, dependency wiring, and SSE transport.
- Chatbot service: session resolution, stage coordination and application
  behavior.
- Provider: OpenAI-specific analysis call and final answer streaming.
- Repository: SQLAlchemy persistence.
- ORM model: database table mapping.

The remaining ownership and history-read work must preserve these boundaries.

## Từ `api_guidelines.md`: mục "Trạng thái và giới hạn hiện tại"

Dòng "chưa có tool CRM" dưới đây đã lỗi thời từ 2026-10-30 (`crm_report`) và 2026-11-10 (`crm_schema`, `crm_query`).


- CORS, OpenAI provider lifecycle và database session được cấu hình ở
  `backend/app/main.py`. CORS cho phép header request `Content-Type`, `Accept`,
  `Authorization`, `Idempotency-Key`, `X-Request-ID`, `X-CSRF-Token` và expose
  `X-Request-ID`. Header request mới mà frontend gửi phải được thêm vào
  `allow_headers`, nếu không preflight trả `400 Disallowed CORS headers` và trình
  duyệt chặn request (kiểm bằng `backend/tests/api/test_cors.py`). Đây là danh
  sách được phép, không phải header bắt buộc.
- History được ghi vào Supabase `public.chat_history`: `completed`, `error`
  (đã kiểm chứng commit sau khi stream bằng test, FastAPI 0.143), `blocked` hoặc
  `cancelled` (hai trạng thái sau commit ngay bằng session riêng).
  `normalized_query` lưu câu hỏi đã chuẩn hóa tiếng Việt.
- `client_context.locale` chỉ là nguồn dự phòng cho ngôn ngữ trả lời: ưu tiên
  ngôn ngữ do analysis phát hiện, rồi ngôn ngữ của phiên. Câu cố định chỉ có
  `vi`/`en`; ngôn ngữ khác được sinh qua LLM. Output strict của analyzer có thêm
  `language` (v3.3, nội bộ).
- Support-chat history endpoints chỉ được enable cùng `LEARNING_API_ENABLED` và
  chưa có ownership; client legacy `/chats` không phải contract backend hiện tại.
- Retrieval đã nối ở mức kiểm thử (xem architecture.md bước 8). Tool agent mới
  có `product_docs_ask` cho kênh CRM (thử nghiệm, xem architecture.md "Luồng
  agent"); chưa có tool CRM, chưa phân quyền tool theo role/scope (mọi nhân viên
  CRM dùng được mọi tool), chưa có event SSE tiến trình.
- Lượt chỉ có chitchat/out_of_scope/handoff trả câu cố định (một chunk SSE)
  không qua LLM; các lượt khác stream từ provider qua `AnswerComposer`, dựa trên
  kết quả task của execution plan. Output strict của analyzer có thêm
  `pending_answer` (v3.1, nội bộ) và `model_dependency` (`general` |
  `model_specific`, v3.2, nội bộ); `RetrievalPlan.answer_mode` có thêm `general`. Task `retrieve` chạy hybrid
  search trên `doc_chunks`; lỗi task nội bộ mới là `retrieval_error` (không lộ ra
  SSE). Schema nội bộ `RetrievalRequest` có thêm `product_scope_mode`,
  `control_interface`, `spec_attributes`; `RetrievalSubQueryResult` có `hits`
  (`ChunkHit`, gồm `assets`); `RetrievalFilters.collections` không còn bắt buộc.
  SSE chưa có event sources/assets. Không viết tài liệu hoặc test như thể RAG đã
  hoàn thiện (chưa rerank, tham số chưa tối ưu, chưa kiểm thử với Supabase thật).

## Từ `architecture.md`: "Phạm vi hệ thống" và sơ đồ tổng (trước khi có `crm_schema`/`crm_query`)

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
