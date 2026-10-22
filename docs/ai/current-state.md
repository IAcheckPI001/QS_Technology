# Current state and remediation backlog

## Scope

This document is the current status of the database, configuration, and chat
history work. It supersedes the original findings-only review and distinguishes
completed work from remaining validation, deferred scope, and open risks.

The current request architecture is:

```text
Frontend
  -> FastAPI route / dependency
  -> ChatbotService
  -> SecurityStage
  -> ContextLoader
  -> Prune
  -> AnalysisStage -> QueryAnalyzer -> OpenAIProvider
  -> ExecutionStage -> ExecutionScheduler -> deterministic task handlers
  -> AnswerComposer -> OpenAIProvider.stream_chat
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
| P1 ChatHistory persistence | Implemented, not production-verified | `ChatHistory`, repository, session UUID propagation, and completed/error persistence are wired. Error-transaction behavior and live insert validation remain open. |
| P2 configuration normalization | Resolved in implementation | One cached `pydantic-settings` model is used and model defaults are aligned. Pytest validation remains outstanding. |
| P3 history reads and ownership | Partially implemented | Support-chat session/message reads and session creation are available behind `LEARNING_API_ENABLED`; authentication and ownership are still deferred. |
| P4 health/readiness semantics | Open | Connectivity check exists, but readiness status/error semantics and schema checks are incomplete. |
| P5 active chatbot pipeline | Partially implemented | Security, context loading (with persisted `ConversationState`), pruning, the clarification loop (deterministic resume, `pending_answer`, held sub-queries, 2-attempt limit), analysis, execution-plan execution, fixed replies for chitchat/out_of_scope/handoff-only turns and provider final-answer streaming run. Retrieval is wired at test level: one retrieve task per sub-query, filtered hybrid search (vector + FTS, RRF, parent expansion) over `doc_chunks` via `match_doc_chunks` (`backend/sql/doc_chunks.sql`, applied manually), sources rendered into the answer prompt. Not verified against live Supabase; retrieval parameters are untuned starting values. Handoff is a scaffold: `DisabledHandoffProvider` creates no ticket, so `mode` stays `bot`. Requires the `conversation_state` column migration (not verified live). |
| P6 knowledge learning pipeline (`learning_ai`) | Ingestion + privacy wired behind a flag | Pure domain logic (record schema, post-LLM validation, rule conflicts, review lifecycle, chunking, indexer sync) plus CRM ingestion, prefilter and the Ollama-backed privacy pipeline exist and are unit-tested with fake providers. `POST /learning-knowledge` runs ingestion + privacy when `LEARNING_API_ENABLED=true` (no authentication yet). LLM segment/extract calls, job persistence, outbox, embedding and vector index are missing. Not verified against live Supabase/Ollama. |

## Finding status

| # | Previous finding | Current status | Evidence and remaining concern |
|---|---|---|---|
| 1 | Missing `DATABASE_URL` could block clean startup | **Resolved in tracked configuration; validation open** | `backend/.env.example` contains the placeholder and `docker-compose.yml` passes `${DATABASE_URL}`. A clean-container startup and live Supabase query still need verification. |
| 2 | Missing SQLAlchemy/database dependencies | **Resolved / false positive in current tree** | `backend/requirements.txt` contains `sqlalchemy`, `asyncpg`, and `pydantic-settings`. Installing and running the backend environment has not been verified here. |
| 3 | Missing `Depends` import | **Resolved** | `backend/app/api/v1/health.py` imports `Depends`; Python syntax validation passed. |
| 4 | `ChatSession`/repository `organization_id` mismatch | **Resolved by replacement** | The old session scaffold was removed. `backend/app/db/models/history.py` and `backend/app/modules/chatbot/repositories/history_repository.py` now represent `public.chat_history`. |
| 5 | No application migration/schema creation | **Partially resolved / externally managed** | The ORM mapping exists and Supabase owns the table. The application does not create or migrate the table, and `/health/db` only runs `SELECT 1`; schema compatibility is not checked automatically. |
| 6 | Successful writes were not committed | **Resolved for normal successful requests; error path open** | `backend/app/db/session.py` commits after a normal request. However, the service creates an `error` history row and re-raises the provider exception; the dependency then rolls back the transaction, so the error row may be lost. |
| 7 | Chat route bypassed persistence | **Resolved for write path** | The route injects `ChatbotService`; the service resolves UUIDs and writes completed/error history through `HistoryRepository`. History reads remain out of scope. |
| 8 | Website string UUID and database UUID mismatch | **Resolved at persistence boundary** | The service validates/parses the incoming string and converts it to `UUID`; invalid or unknown values receive a new UUID. The replacement ID is returned in SSE `done`. |
| 9 | Duplicated settings sources | **Resolved** | `backend/app/core/config.py` has one cached `Settings` model consumed by application and database code. |
| 10 | Health endpoint semantics were ambiguous | **Open** | `/health/db` exists, but unavailable-database status codes, structured error responses, readiness semantics, and schema-level checks are not finalized. |

## Implemented behavior

### Session ID lifecycle

1. Missing `session_id`: the backend reuses
   `backend/app/util/uuid_generate.py` to generate a UUID.
2. Existing UUID with history: the same ID is reused.
3. Invalid or unknown UUID: a new UUID is generated.
4. The authoritative UUID is returned in the existing SSE `done` event.
5. The frontend stores it in `localStorage` under
   `chatbot_session_id`.

Clearing that local key starts a new active conversation but does not delete
historical database records. Deletion is not currently implemented.

### Chat history writes

- The current service writes `status='completed'` after streaming the
  provider-generated answer. Retrieve tasks ground the answer in `doc_chunks`
  sources (`[S#]` citations in the text only).
- A provider or pipeline exception attempts to write `status='error'` with any
  partial answer.
- `input_tokens`, `output_tokens`, `cost_usd`, `normalized_query`, and
  `retrieved_chunk_ids` are not produced by the current active flow; they remain
  defaults or `null`.
- Synthetic UUIDs and metrics are permitted only in local/test fixtures, never
  as fabricated production measurements.

## Open risks and deferred scope

### High priority

1. **Error history durability**
   - The `error` record is created in the same request transaction that is
     rolled back after the provider exception.
   - The error record may therefore not persist.
   - This weakens operational visibility and violates the documented
     completed/error history behavior.

2. **No live Supabase verification**
   - No verified `/health/db` request has been recorded.
   - No verified insert/select against `public.chat_history` has been recorded.
   - The ORM definition has not been compared automatically with the live table.

3. **Backend test suite partially failing**
   - Tests run with `backend\venv\Scripts\python.exe -m pytest` from `backend/`.
   - 5 chatbot tests fail because they lag the in-progress chatbot refactor.
     See the validation record.

### Medium priority

4. **History reads are not implemented**
   - The frontend still contains the legacy `/chats` client path.
   - There is no current `chat_history` read endpoint.

5. **No ownership boundary**
   - `session_id` is client-controlled and is not an authorization credential.
   - The table has no account ID or visitor-token ownership field.
   - Production history reads must remain disabled until ownership checks exist.

6. **No idempotency key**
   - The frontend sends `message_id`, but it is not persisted in
     `chat_history`.
   - Retries can create duplicate history rows.

7. **No ordering/concurrency policy**
   - Concurrent requests for one session can be committed out of order.
   - The current UI limits normal concurrent sends, but the backend has no
     ordering or idempotency guarantee.

### Lower priority

8. **Provider usage metadata is incomplete**
   - Token counts and cost are not collected.
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

1. Make `status='error'` durable by isolating error-history persistence from
   the rolled-back provider/request transaction, or by handling the error
   commit explicitly.
2. Install/restore the backend test environment and run the focused tests.
3. Run the backend with the configured runtime environment.
4. Verify `/health/db` against Supabase.
5. Execute a real chat request and verify the inserted row in
   `public.chat_history`. Token/cost fields should remain unset until usage
   extraction is implemented; do not treat them as currently generated.

### P2 — Required before enabling history reads

6. Add a `chat_history` read endpoint and repository query with explicit
   session ordering.
7. Decide whether reads support authenticated users, anonymous visitors, or
   both.
8. For anonymous access, add server-issued visitor-token ownership binding.
9. For authenticated access, validate account ownership.
10. Add authorization tests for matching and mismatched session/token pairs.

### P3 — Reliability and data quality

11. Persist or otherwise enforce an idempotency key based on `message_id`.
12. Define ordering/concurrency behavior for one session.
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
final answer from the task results, including retrieved `<sources>`. Tools are not executed. Invalid configuration is an application/configuration
error; an unfit mandatory payload is a context-budget/domain error. Neither is
a security block.
