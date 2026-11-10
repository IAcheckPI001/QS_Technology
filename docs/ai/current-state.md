# Current state and remediation backlog

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

## Completion summary

| Area | Status | Summary |
|---|---|---|
| P0 importability and deployment configuration | Resolved in code/config | `Depends` is imported, `DATABASE_URL` is documented and passed through Compose. Clean-runtime and live-Supabase validation remain outstanding. |
| P1 ChatHistory persistence | Implemented, not production-verified | `ChatHistory`, repository, session ownership (`chat_sessions`), and completed/error/blocked/cancelled persistence are wired. The `error` row commit after streaming is verified by test on FastAPI 0.143 (see open risk 1); live insert validation remains open. |
| P2 configuration normalization | Resolved in implementation | One cached `pydantic-settings` model is used and model defaults are aligned. Pytest validation remains outstanding. |
| P3 history reads and ownership | Partially implemented | Support-chat session/message reads and session creation are available behind `LEARNING_API_ENABLED`; authentication and ownership are still deferred. |
| P4 health/readiness semantics | Open | Connectivity check exists, but readiness status/error semantics and schema checks are incomplete. |
| P5 active chatbot pipeline | Partially implemented | Security, context loading (with persisted `ConversationState`), pruning, the clarification loop (deterministic resume, `pending_answer`, held sub-queries, 2-attempt limit), analysis, execution-plan execution, fixed replies for chitchat/out_of_scope/handoff-only turns and provider final-answer streaming run. Retrieval is wired at test level: one retrieve task per sub-query, filtered hybrid search (vector + FTS, RRF, parent expansion) over `doc_chunks` via `match_doc_chunks` (`backend/sql/doc_chunks.sql`, applied manually), sources rendered into the answer prompt. Not verified against live Supabase; retrieval parameters are untuned starting values. Handoff is a scaffold: `DisabledHandoffProvider` creates no ticket, so `mode` stays `bot`. Requires the `conversation_state` column migration (not verified live). |
| P5b CRM agent flow | Experimental, unit-tested only | `/chat/crm` runs a bounded tool-calling loop (`AgentRunner`) when `CRM_CHAT_FLOW=agent` (default). Tools: `product_docs_ask` (reruns clarification → analysis → retrieval on a child state, no compose) and, behind `CRM_REPORT_ENABLED`, `crm_report` (aggregate reports: tickets from the CRM list API, customers / support assignments / device deliveries from the CRM Reporting Query API) and `crm_records` (whitelisted record lists), see 12d. Provider capabilities and tool schemas are checked at startup. Shared turn deadline, cancellation propagation, three-level concurrency limits and a per-session turn lease (409 `session_busy`) are implemented and tested with fakes only. Hybrid model selection: questions like "which models support EtherCAT? how do I install it?" filter models in code from `REGISTRY["capabilities"]` (`catalog_match` with `next_action` report_no_match / lookup_each / ask_selection / verify_with_sources), and follow-up lookups only accept models backed by evidence (employee message/history, session model context, discovered models, or cited sources via `based_on_sources`). The orchestrator is tool-neutral: shared rules in the system prompt, per-tool rules in `ToolSpec.guide`, per-tool turn state, `deduplicate` and `max_calls_per_turn` per tool. No per-role tool permissions (every CRM employee can use every tool), no SSE progress events, the final answer is one `delta` (no token streaming), no web tools. Not verified against live OpenAI tool calling or Supabase; `chat_sessions.turn_lease_until` must be applied manually. |
| P5c request tracing (phase 0) | Implemented, unit-tested only | In-process span tree per `/chat/*` request (`app/core/tracing.py`, no new dependency): router, security/context/prune, pipeline stages, agent steps, tool calls, retrieval (embedding, `match_doc_chunks`), CRM API pages, compose, history writes. Real OpenAI usage is recorded on spans (analysis, compose stream, embeddings, agent steps). Every turn logs one `chat_trace` summary line; with `CHAT_TRACE_PERSIST=true` the trace is stored in `public.chat_traces` (`backend/sql/chat_traces.sql`, apply manually) and served by `GET /chatbot/sessions/{id}/trace`. Metadata only. Not verified against live Supabase/OpenAI; no OpenTelemetry export, no context propagation to CRM/OpenAI, no UI, no retention. |
| P6 knowledge learning pipeline (`learning_ai`) | Ingestion + privacy wired behind a flag | Pure domain logic (record schema, post-LLM validation, rule conflicts, review lifecycle, chunking, indexer sync) plus CRM ingestion, prefilter and the Ollama-backed privacy pipeline exist and are unit-tested with fake providers. `POST /ai/learning` runs ingestion + privacy when `LEARNING_API_ENABLED=true` (no authentication yet). LLM segment/extract calls, job persistence, outbox, embedding and vector index are missing. Not verified against live Supabase/Ollama. |
| P7 technical document ingest (`doc_ingest`) | Parsing spike done (F54); contract C1 locked (rev 3); table normalization, profile, approval core and CLI `run` with HTML report implemented and tested; pipeline PDF → chunk not complete | Offline CLI tool in a separate `.venv-ingest` (Docling), isolated from the chat service (import boundary tested both ways, excluded from the chat image via `backend/.dockerignore`). C1 locked 2026-11-03 (D-02, D-03, D-04 data model, D-08, D-11); rev 3 changes T-01 to whitespace-gap column boundaries because the rev 2 rule failed on F54 itself. Implemented: `schemas/` (Pydantic, `extra="forbid"`), `profile.py` + `profiles/` (`default`, `qs_controller`, registry vocabulary snapshot), `normalize/` (Docling JSON reader; logical tables T-01…T-05, T-15), `technical_refs/` (ParamRef T-12, applicability T-13 on table cells), review queue, `review/approval.py` (unit states, serve rule, approval gate, carry-over by id then unique hash match, risk-based bulk approval, publish rule), CLI `run` (`cli.py`, `pipeline.py`, `report/html_report.py`, `parse/docling_runner.py`): PDF or saved Docling JSON → run dir `data/ingest_runs/{doc_id}/{run_id}/` + `report/index.html` showing each step. T-13 output is `applicability_candidates` (candidates, not facts). Tests: five C1 groups (LT, HC, AP, HA, PI) on the F54 fixture plus synthetic fixtures, none need Docling. Also implemented: Docling label classification (T-16), V-01 text coverage, S0 with per-page OCR, header/footer check (T-17), printed pages (T-06), section paths (T-07), `NormalizedElement`, figures (T-18 labels next to pictures, T-09 screenshot, T-10 watermark candidate, T-11 caption, T-14 crop + render to `normalized/images/`, T-19 duplicates), list parent/child (T-08 v1), T-12/T-13 on text. Not implemented: V-02…V-04, chunk builder, fact extraction, unit assignment, review CLI, publish, web upload. No DB writes. `doc_chunks` still holds hand-authored F86 chunks loaded by `chunking_loader/load_csv.py`. |

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

4a. **Handoff is a stub (H1) and source numbers restart each turn (H6)**
   - `DisabledHandoffProvider` returns `None` while the reply promises a human
     agent; `[S#]` citations are not persisted, so numbering restarts at S1.
   - Both deferred; see `docs/ai/reports/diagram_request_handler.html` §11.

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

10. **Frontend lint baseline**
   - `npm run lint` still fails on existing unrelated frontend errors.
   - `npm run build` passes with an existing CSS syntax warning.

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
12b. Product capabilities and model selection (agent flow), known limits:
     - Capabilities live in code (`extraction/registry.py`), closed world: a
       model without an interface is treated as not supporting it. Data comes
       from the product team; changes need a deploy. Move to a database
       repository behind `ProductCatalog` later. Only `control_interface` exists;
       spec values (number of axes, screen size) are not structured yet, so such
       conditions go to `unmapped_conditions` and `verify_with_sources`.
     - `verify_with_sources` relies on top-k chunks: the model list can be
       incomplete, and the 1–3 / ≥4 threshold is only applied through the prompt.
       `based_on_sources` checks that the model appears in the cited source, not
       what the sentence says.
     - "Astro nào hỗ trợ EtherCAT" (family alias as a filter) still asks to
       disambiguate "Astro". No hardware/firmware version entity. Sources carry
       the model filter of their group, not a per-chunk model (`match_doc_chunks`
       does not return `product_models`).
     - LLM-dependent behaviour (negation "không cần" vs "không hỗ trợ", pronouns,
       following `next_action`, prompt injection) is covered by the manual eval
       `backend/evals/run_crm_agent_eval.py`, which has **not been run** yet.
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
12d. `crm_report` + `crm_records` (experimental, `CRM_REPORT_ENABLED=false` by default).
     Semantic catalog: the LLM picks logical names from enums; join paths, system
     filters and business definitions live in `DatasetSpec` (decision 2026-11-10 with
     Toma: option A, no raw `list_datasets`/`get_table`/`run_query` tools for the LLM).
     Datasets: `tickets` (CRM `GET /api/v1/support/cases`, computed in-process; kept on
     the list API because the Reporting API cannot compute resolution time, ticket age
     or `status_group`), `customers` (CRM curated report dataset, needs `customer.read`),
     `support_assignments` and `device_deliveries` (`product_ownerships`), both raw
     tables that need `auth.manage_roles` on the CRM side. Report datasets compile to
     `POST /api/v1/reports/query` (`reporting/report_api.py`), run in parallel and are
     merged in the AI service (change/delta, empty periods). `crm_records` lists up to
     20 rows per call from a per-dataset column whitelist (no subject/description/notes,
     phone/email/address), with `total` and `next_offset`. Errors: 401
     `crm_auth_failed`, 403 `crm_forbidden` (new; was `crm_auth_failed`), Reporting API
     400 `crm_report_contract_error`, others `crm_unavailable`. Outputs carry
     `definitions` (fixed meaning of "khách của phiếu", "bán được", …).
     Verified with fakes only (`test_report_api.py`, `test_crm_records_tool.py`); the
     list API path was verified once against the CRM test API (22 tickets). The
     Reporting API itself is **not** verified over HTTP (its own doc says the same).
     Assumptions until the CRM team confirms (all written into `definitions` or code
     comments): DB timestamps are Vietnam local time (the API compares calendar dates);
     a case's customer is `support_cases.product_item_id → product_items.customer_id`;
     the curated `customers` dataset names its dimensions `assigned_sales`,
     `created_day`, `created_month` and accepts `select` on raw column names; product
     "model" is `products.name`; people are filtered by exact `auth_users.username`
     (no name → UUID lookup API yet; `assigned_sales` is only a UUID). Check with
     `backend/evals/check_crm_report_contract.py` (needs `CRM_EVAL_ACCESS_TOKEN`).
     The CRM bearer is the optional `crm_access_token` of `/chat/crm`
     (kept only in the request principal as `SecretStr`, excluded from dumps,
     logs, `chat_sessions` and snapshots); without it the tools fall back to
     `acting_user_id`, which is logged and stored, so it must not be a secret. The
     widget test route reads the token from `VITE_CRM_TEST_TOKEN`, which is
     bundled into the browser build: test environment only. Ticket status
     `resolved` counts as done (with `closed`). Known limits: tokens are not
     refreshed; `tickets` still re-fetches every ticket the token can see (no cache,
     no filter push-down); `priority`/`category`/`support_mode` are free strings until
     their enums are confirmed; `in_progress` is only updated by CRM when a case page is
     opened; no ticket content/detail, no SLA/overdue, no `having`, OR/NOT or `gt/lt` on
     report datasets, no `week` grain on report datasets; a sales user without
     `auth.manage_roles` only gets `customers` and `tickets` (others return
     `crm_forbidden`). Does the CRM Reporting API block sensitive columns
     (`auth_users.password_hash`, `sessions`…)? Unknown; the AI service never asks for
     them because only catalog paths are sent.
12a. CRM agent flow backlog: per-role tool permissions, SSE progress event,
     token streaming of the final answer, record detail (ticket content), raw report tool
     for admins (option C: whitelisted tables/columns, behind `required_scope`),
     person name → UUID lookup for report filters, write tools with user confirmation, planner step when the tool
     count grows, MCP adapter, Ollama/Gemini capability declarations, live
     verification of OpenAI tool calling and of cancellation reaching asyncpg
     (`pg_stat_activity`).
13. Add provider usage extraction for token counts and cost.
14. Decide `retrieved_chunk_ids` type (`UUID[]` vs `doc_chunks.id bigint`) before persisting retrieval metadata.

### P4 — Operational hardening

15. Define `/health/db` as a readiness endpoint or diagnostic endpoint.
16. Return intentional non-2xx responses for unavailable dependencies.
17. Add schema compatibility checks for required `chat_history` columns.
18. Resolve or separately baseline the existing frontend lint failures.

### P5 — Knowledge learning pipeline (`learning_ai`)

Design and per-step status are in `docs/ai/architecture.md`. Remaining work, in order:

Done: CRM ingestion from `public.history_support_chat`, prefilter, privacy
pipeline (regex A/D, Ollama B, redactor C, fail-closed) and `LearningIngestionService`.
`assemble_draft` now takes `redaction_applied` from the caller. The table is
Supabase-managed and must have `created_at timestamptz not null default now()`. The
ORM expects that column, and it has not been verified against the live table.

19. Add the missing registry keys (`topics`, `connectors`, `parameters`,
    `alarm_codes`) and build one `RegistrySnapshot` source shared with query extraction.
20. Build a labeled Vietnamese CRM evaluation set and measure Ollama recall per finding
    type before trusting a model. The `.env.example` default `qwen3:1.7b` is likely too
    small; `qwen2.5:7b-instruct` or newer is recommended as a starting point.
21. Segmenter/Extractor prompts and calls behind the provider layer, driven by a
    learning service, not the router. Segments whose main topic is pricing must use
    `skip_reason="pricing"`; official prices come from catalog documents.
22. Supabase tables for extraction jobs (with `source_content_hash` so unchanged
    conversations are not reprocessed), knowledge records/revisions, outbox and
    chunks/vectors. This needs a schema decision before implementation.
23. Learning service ordering: extract -> assemble -> validate -> conflicts ->
    `pending_review`. Approval must run the gate after validation and conflicts.
24. Review API/UI, semantic conflict comparison, `Embedder`/`SearchIndex`
    implementations, outbox worker, and chatbot retrieval using `ChunkFilters`.

### P6 — Technical document ingest (`doc_ingest`)

Design and per-step status are in `docs/ai/architecture.md`; the task list is
`docs/ai/reports/p1_implementation_backlog.md` (BL-xx).

Done: P-1 Parsing Spike on F54 (pdf pages 9, 11, 14, 18, 19, 40, 167–171;
Docling 2.145.0, `do_ocr=False`, TableFormer accurate, ~96 s), spike tool
`doc_ingest/spike/` (`run_spike.py`, `render_review.py`), `requirements-ingest.txt`,
`.gitignore` entries, and the P-1 documents (BL-00, BL-01). The module and the
P-1 documents are committed. Note: `docs/ai/doc_ingest_spike/source/F54_Operation
Manual (English Version)_V.02.pdf` is tracked in git although `source/` is meant
to be gitignored; whether to keep it is not decided.

Current step: **Ingestion V1 group A–C in progress** (C1 locked 2026-11-03).

25. Reviewer fills the "Người duyệt" column in `parsing_spike.md` and confirms
    decisions 1–11 (all rows are currently empty).
26. Run the spike on F86 (BL-13, D-07). Both F86 PDFs are now in
    `docs/ai/doc_ingest_spike/source/`, but no F86 output exists; required
    before S1 image rules (vector diagrams) are approved.
27. Done (2026-11-03): D-02, D-03, D-04 (data model), D-08, D-11 decided and
    contract C1 locked as rev 3 (BL-14); details in
    `p1_chunking_impact_assessment.md` §6. Still open: D-12 (V-xx/S0 thresholds)
    blocks chunk generation; D-05, D-06, D-09, D-10 and the LLM part of D-04 block
    later steps (F54 publish, F86 facts, unit publish, per-code values, fact
    extraction).
28. Ingestion V1 group A–C. Done (2026-11-03): schemas for tables, profile and
    review (BL-04 partial; `NormalizedElement` and validation schemas missing),
    configuration profile (BL-26), registry vocabulary snapshot (BL-29), table
    normalizers T-01…T-05 and T-15 (BL-05, BL-06, BL-27), T-12/T-13 on table cells
    (BL-11 partial), approval core (BL-18, BL-20 partial), synthetic fixtures
    (BL-31). Remaining: fixture text-layer words (BL-02b), V-01…V-04 (BL-25), chunk assertion
    library (BL-15), whole-pipeline determinism (BL-23), F86 spike (BL-13).
    Done earlier (2026-11-02): isolated module skeleton, golden F54 fixture
    (BL-02), F86 baseline lock (BL-03).
29. Ingestion V1 group D–E: baseline chunk builder, draft fact extraction,
    quality gate, knowledge units, review CLI, approved package (BL-16…BL-22).
30. Production integration (BL-90…BL-94): new tables, `doc_chunks` changes
    (`unit_id`, nullable embedding, `parent_id` from `parent_key`), loader,
    runtime facts/assets, eval vs. F86 baseline. Not planned yet.

## Validation record

- Python syntax validation for changed backend modules: **passed**.
- `git diff --check`: **passed**.
- `npm run build`: **passed**, with the existing CSS warning
  `Unexpected ";"`.
- `npm run lint`: **failed** on pre-existing frontend unused-variable and
  undefined-symbol errors.
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
- Empty analysis output (`sub_queries=[]` without pending, e.g. a statement with
  no question) is now answered as chitchat instead of `analysis_error`
  (2026-10-29, M3 code layer). Prompt rule for statements → out_of_scope is
  deferred. Backend pytest: **297 passed, 0 failed**.
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
- CRM agent flow (`AgentRunner`, `ToolRegistry`, `product_docs_ask`, provider
  capabilities, shared deadline, cancellation, per-session turn lease)
  (2026-10-30): backend pytest **387 passed, 0 failed** (311 existing tests
  unchanged in assertions; `test_chat_routes.py` harness gained a fake lease
  store). `npm run build` passed; `npm run lint` unchanged (139 pre-existing
  errors in `src/`). Live OpenAI tool calling and Supabase: **not verified**.
- Turn-lease self-lock fix (2026-10-30): backend pytest **390 passed, 0 failed**.
  `test_session_access.py::test_owner_can_resume_session` now asserts that a
  resumed session is only read (previously asserted a `touch`). `npm run build`
  passed. Live re-test on Supabase pending.
- Hybrid model selection (capabilities table, `CatalogLookupStage`,
  `catalog_match`, `awaiting_models`, evidence + `based_on_sources`, CRM model
  context, call dedup, citation check, analysis schema v3.4) and tool-neutral
  orchestrator (`ToolSpec.guide`, per-tool turn state, `deduplicate`,
  `max_calls_per_turn`) (2026-10-30): backend pytest **450 passed, 0 failed**.
  Changed assertions in existing tests, all intended: the agent child state now
  sends the session `last_models` to analysis; a model the agent invents is
  rejected with `model_not_evidenced` before analysis (previously
  `needs_clarification` from the guard); an unknown `[S#]` in the final answer is
  removed; the strict tool schema snapshot includes `based_on_sources`; the CRM
  turn now updates `last_models`/`active_model`. `npm run build` passed;
  `npm run lint` unchanged (139 pre-existing errors in `src/`). Live OpenAI and
  Supabase: **not verified**; manual eval not run.
- `doc_ingest` isolated module skeleton (`geometry.py`, `parse/`, golden F54
  fixture, import-boundary tests, F86 baseline lock) (2026-11-02): backend
  pytest in `backend\venv` **557 passed, 11 skipped** (the skips are the
  `requires_docling` tests); `.venv-ingest` `pytest tests\doc_ingest`
  **37 passed**. Spike re-run on pages 11 and 18 after the helper move: Docling
  JSON byte-identical, `p*_items.json` identical apart from the crop timing
  field `ms`.
- `doc_ingest` C1 implementation (schemas, profile, table normalization T-01…T-05
  and T-15, T-12/T-13 on cells, approval core, five C1 test groups) (2026-11-03):
  backend pytest in `backend\venv` **659 passed, 11 skipped** (skips are the
  `requires_docling` tests); `.venv-ingest` `pytest tests\doc_ingest`
  **138 passed**. GT-23 scan checked by inserting `"F54"` and `r"^#\d"` into a
  rule module (test failed, file restored). Tests that need later steps (LT-10,
  LT-11, AP-08…AP-10, HA-10…HA-12, PI-09) are listed as pending in
  `p1_golden_tests.md` §6, not implemented as stubs.
- `doc_ingest` CLI `run` + HTML report, `applicability_candidates`, carry-over by
  hash (2026-11-03): backend pytest in `backend\venv` **668 passed, 11 skipped**;
  `.venv-ingest` `pytest tests\doc_ingest` **147 passed**. Manual: CLI with Docling
  on the F54 PDF (pages 11, 14, 167–171, ~79 s of Docling) gave `tables.jsonl` with
  the same content hashes, cells, flags and review items as `--raw-dir` on the
  fixture; report opened from `data/ingest_runs/f54/verify-f54/report/index.html`
  (rendering checked by tests on HTML content, not in a browser by Claude).
- `doc_ingest` safety net (2026-11-03): Docling label classification (T-16: table of
  contents `document_index` kept, unsupported labels flagged `unsupported_element`), reader
  now walks children of every node (captions were silently missing before), V-01 text
  coverage against the PDF text layer (`words.json`, provisional thresholds 0.9/0.1, D-12
  open). Found from the user's run of F54 pages 5–10, where the table of contents was
  dropped without any flag. Backend pytest in `backend\venv` **679 passed, 12 skipped**;
  `.venv-ingest` `pytest tests\doc_ingest` **159 passed**. Re-run of pages 5–10: TOC kept
  (3 × T-16), V-01 passed 6/6; F54 fixture V-01 passed 11/11.
- `doc_ingest` S0 + per-page OCR (2026-11-03): the user's F86 Operation Manual run
  (pages 1–17) showed pictures but no text: the PDF has no text layer (text drawn as
  bitmaps/paths), Docling ran without OCR, and the report showed 0 review items. Now S0
  measures each page, pages without a text layer are OCR'd with RapidOCR (torch backend,
  already in `.venv-ingest`; the default onnxruntime backend is not installed) and get
  `ocr_required` (blocking). Re-run of F86 pages 1–17: 17/17 OCR, 235 s; captions
  (Figure 1-1…2-11) and headings recovered; open issues I-21 (headings tagged as page
  headers become furniture), I-22 (table drawn as an image, page 15), I-23 (OCR errors).
- `doc_ingest` T-17 / T-06 / T-07 (2026-11-03): fixes I-21. Docling header/footer labels
  are now checked: strings repeated on ≥ 3 pages in the top/bottom band (digits treated
  as equal), lines merged from them, or profile `furniture_patterns` are furniture; a
  header/footer seen once that is a numbered heading returns to the body
  (`furniture_reclassified`, non-blocking); other single ones stay furniture with
  `furniture_unconfirmed` (non-blocking). OCR text inside pictures becomes `figure_text`
  (not body text, not headings). Printed page numbers come from /PageLabels or the footer
  number sequence, never from an offset. `normalized/elements.jsonl` holds
  `NormalizedElement` rows (fields for T-08…T-11 still empty). F86 pages 5–17 OCR output
  is now a fixture (`fixtures/docling/f86_ocr`). F54 table hashes unchanged.
- `doc_ingest` figures, BL-10 (2026-11-03): the run now stores `raw/p{n}.objects.json`
  (bitmaps with pixel size, vector paths; objects inside a Form XObject use the form's
  bounds, which fixes a wrong position for F54 page 18). New rule T-18 attaches short labels
  next to a picture (F86 `320 mm` on pages 8 and 9) as `figure_text`. T-14 crop = Docling
  bbox + covering bitmaps + nearby vector paths + the picture's labels, rendered to
  `normalized/images/` when the run has the PDF. T-09 turns a 0-cell table covered by a
  bitmap into `screenshot`; T-10 marks a caption-less picture inside a bitmap repeated on
  ≥ 3 pages (same pixel size and same displayed size, any position) as
  `watermark_candidate` (condition changed from IoU ≥ 0.9 to ≥ 90% of the picture covered,
  because IoU missed F54 page 171; F86: 5 logos caught); T-11 moves figure/table captions to
  the nearest target. Text inside or next to pictures is only a keyword for the picture,
  never chunk body or a fact. HTML report has a Figures section. Picture units, review and
  serving images with answers are still not built (BL-19, BL-21, BL-92).
- `doc_ingest` full F54 run (171 pages, run `20261103-144432`, re-checked 2026-11-08 with
  the current code: same output). All output files pass their schemas; V-01 168 passed,
  0 failed, 3 not run (cover page OCR, two picture-only pages); 11 logical tables, 128
  headings, 33 screenshots, 247 rendered crops. Defects found then: T-10 treated UI
  screenshots of the same pixel and display size as a repeated bitmap (7 of 15 watermark
  candidates and 7 of 8 conflicts were real screenshots, I-24); T-18 took short section
  labels at the text left margin (I-25); `PART 1:CONTROLLER OVERVIEW` was not a heading
  (I-26). Normalized output is the chunk builder's input; no chunks are produced yet (BL-16).
- `doc_ingest` fixes I-24…I-26 (2026-11-08): `objects.json` bitmaps carry a content `hash`;
  T-10 watermark = same content at the same position on ≥ 3 pages, while the same content
  at other positions only gets the info flag `repeated_image`; T-18 skips lines starting at
  the document's text left margin; the keyword heading pattern accepts a title glued after
  `:`; T-11 keeps the Docling link when two candidates tie. Full F54 re-run (PDF objects on
  the saved raw): 8 watermark candidates, all real; 1 watermark conflict; 1 caption
  ambiguity (page 38, real); table hashes and printed pages unchanged.
- `doc_ingest` I-27 (2026-11-08): Docling sometimes emits both a picture and a 0-cell table
  for one screenshot. New rule T-19: two figure elements on a page with IoU ≥ 0.9 are one
  image; the captioned one (else the screenshot, else the first) is kept, the other gets
  `duplicate_image` and `duplicate_of`, no crop and no caption; nothing is deleted. Full
  F54: 5 duplicates (pages 64, 81, 85, 96, 98), rendered crops 247 → 242, everything else
  unchanged; F86 pages 5–17 unaffected.
- `doc_ingest` summary log: [chunking_builder/chunking_flow_log.md](chunking_builder/chunking_flow_log.md)
  collects the flow, step status, change history and fixed issues in one place (2026-11-08).
- `doc_ingest` reference run (2026-11-09): F54 171 pages re-parsed from the PDF
  (`data/ingest_runs/f54/20261109-063902`) reproduces the `fix-i27` figures exactly; its table
  hashes are now the baseline (listed in the summary log). No code change.
- `doc_ingest` BL-09 / T-08 v1 (2026-11-09): new `normalize/lists.py`. Docling returns lists
  flat, so the level comes from the left margin (main signal); a bullet glyph followed by a
  space only counts for a 3–18 pt indent. Any non-list body element ends a list block; a list
  at the top of a page continues the list ending the previous page (`list_cross_page`).
  Unclear cases get a review item instead of a guessed parent: `list_orphan` and the new
  `list_level_ambiguous` (both block facts, not chunks); siblings with different markers get
  `list_marker_mixed`. `list_info` is now the typed `ListInfo`; `RunReport.lists`; HTML report
  section "List". Full F54: 482 list items, 103 children, 0 orphans, 3 ambiguous (page 71),
  review 21 → 24, everything else unchanged; F86 pages 5–17 unchanged. Rule is v1, checked on
  F54 only.
- `doc_ingest` BL-11 text part (2026-11-09): `technical_refs/params.py::find_param_refs` and
  `normalize/text_refs.py`. Parameter codes in body text become `TextParamRef` (ParamRef +
  `start`/`end` + `role` definition/value_option/mention). Only prefixes listed in the new
  profile field `param_text_patterns` are scanned (`qs_controller`: `#` 4–5 digits, `M` exactly
  4, so M-code `M100` and pin `M8` are not parameters; they are counted as near-misses).
  T-13 also runs on text. T-08 v1.1: new review `list_param_mismatch` when a list child talks
  about a different code than its parent defines. Step `s1_refs` is now implemented;
  `RunReport.refs`; HTML section. Full F54: 227 refs (98/75/54), 302/302 code tokens covered,
  2 mismatches on page 96 (an editing error in the manual itself), review 24 → 26, everything
  else unchanged; F86 unchanged. Next: evaluation on other documents (profile fit report,
  labelled samples, F86 Installation and F10T).
- `doc_ingest` BL-34 multi-document evaluation (2026-11-09): `eval/profile_fit.py` adds
  `RunReport.profile_fit` (code tokens matched, near-misses, unknown code shapes, OCR share,
  big pictures holding sentences, Vietnamese text on OCR pages) and warning signals shown in
  the HTML report; nothing is changed automatically. New CLI `eval --run-dir --labels` scores
  a run against hand-labelled sample pages (`tests/doc_ingest/fixtures/eval/*.labels.json`,
  drafted by Claude from the PDF text layer and page images, `verified: false` until the team
  confirms) and writes `report/eval.json`/`eval.html`; the gate needs ≤ 50% OCR pages plus
  T-12 precision ≥ 0.99, recall ≥ 0.95, roles ≥ 0.95, no wrong list parent, all lexicon notes,
  ≥ 95% body sentences kept. Provisional results: F54 and F86 Installation pass; F86 Operation
  and F10T fail on OCR. New issues: I-28 (F10T: Docling takes a whole two-column page frame as
  one picture, so instructions become figure text), I-29 (OCR runs in English on a Vietnamese
  scan: diacritics lost), I-30 (`M0100.txt` macro name read as parameter). Not fixed yet.
- `doc_ingest` BL-16 chunk builder + BL-15 chunk checks (2026-11-09, **draft, awaiting team review of
  the 2b gate**): stage 2 `build` reads an existing normalized run + a document manifest
  (`manifests/*.yaml`) and writes `build/chunks.jsonl` (`DraftChunk`, independent of the table),
  `build/doc_chunks_v1.jsonl` (adapter to the current `doc_chunks` columns, candidate fields in
  `metadata`), `build/chunk_quality.json` (CQ-01…CQ-10, coverage, boundaries vs draft labels
  `fixtures/eval/{doc}.chunks.json`, comparison with the hand-written F86 CSV, review summary, gate),
  `build/chunk_review.json` (team verdicts) and `report/chunks.html`. CLI: `build`, `figure-ocr`
  (RapidOCR torch on figure crops of text-layer pages → keywords only); `run` calls `build` when a
  manifest exists. No DB writes; the chatbot retrieval flow is unchanged; no Vietnamese text yet (step 3).
  Results: F54 323 chunks, F86 Installation 26; CQ pass, coverage 1.0, boundaries P/R 1.0 on draft
  labels (type accuracy 0.9 / 0.71). New issues I-31 (F86 TOC page not detected), I-32 (F86 port table
  description cells shifted between rows), I-33 (figure chunks without caption carry only the heading),
  I-34 (port table granularity vs per-connector hand chunks), I-35 (coarse chunk-type rules).
  The FTS-branch bug was renumbered E-05 (E-02 already existed).
- `doc_ingest` C2 chunk contract (2026-11-09, approved with changes to §1, §2 and a new §13):
  [reports/p2_chunk_contract.md](reports/p2_chunk_contract.md) maps every `doc_chunks` column to its
  source, based on a read of the current retrieval flow (`Retriever`, `match_doc_chunks`,
  `product_docs_ask`). Key points: a matched child returns its **parent's** content and assets, so a
  parent is a context window holding its children verbatim (≤ 2,500 chars, one level); content stays in
  the source language while `embed_text` always carries a Vietnamese summary/FAQ/keywords (queries are
  rewritten in Vietnamese); procedures are never split per step; figure labels go to keywords only.
  The retrieval flow itself is not changed. New issue E-05: the FTS branch of `match_doc_chunks` drops
  all rows when the model filter is an empty array (vector branch treats it as no filter); to be fixed
  separately in the chatbot module.
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
- Trace diagnostics after Toma's case 1 (2026-11-07; `crm_report` with an expired CRM
  token: first call rejected by catalog validation, second call 401). The trace showed
  the flow but not why validation failed, what the LLM asked for, which credential was
  rejected, and `error_spans=5` counted one failure several times. Added: tool span
  `error_detail` (quoted values redacted), `crm_report` query shape +
  `credential_source`, summary `root_error_spans` / `failed_tool_calls`, root
  `tool_errors`, same fields in the `chat_trace` log line. Removed the debug `print`
  of applied report filters in `tools/crm_report.py`. Backend pytest **765 passed,
  14 skipped, 1 failed** (same CRLF-only `test_f86_baseline_csv_unchanged`). Live
  re-run of case 1: pending (Toma).
- CRM Reporting Query API + `crm_records` (2026-11-10, branch `test` from
  `feature/deploy_ai_service`): `CrmReportClient`, `ReportApiSource`/`ColumnSpec` in the
  catalog, `reporting/report_api.py` (compile/merge), `reporting/records.py`, datasets
  `customers`, `support_assignments`, `device_deliveries`, tool `crm_records`, 403 split
  into `crm_forbidden`, `ReportOutput.source`/`definitions` (`fetched_count`/`skipped_count`
  nullable), eval cases r1–r5 + `tools_any`/`datasets_any` in `run_crm_agent_eval.py`
  (`CRM_EVAL_ACCESS_TOKEN`), contract script `evals/check_crm_report_contract.py`.
  Backend pytest **885 passed, 14 skipped, 1 failed** (same CRLF-only
  `test_f86_baseline_csv_unchanged`). Two existing assertions changed on purpose: 403 is
  now `crm_forbidden`, agent setup registers `crm_records`. Frontend untouched;
  `npm run lint`/`build` not run (no `node_modules` in the worktree). Not verified: the
  Reporting API over HTTP, the agent eval cases with live OpenAI.
- Live Supabase connectivity/insert: **not verified**.

## Architectural impact

The implemented request/write path follows the documented boundaries:

- API route: request validation, dependency wiring, and SSE transport.
- Chatbot service: session resolution, stage coordination and application
  behavior.
- Provider: OpenAI-specific analysis call and final answer streaming.
- Repository: SQLAlchemy persistence.
- ORM model: database table mapping.

The remaining ownership and history-read work must preserve these boundaries.

## Context/RAG pipeline

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
