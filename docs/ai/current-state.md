# Current state and remediation backlog

## Scope

This document is the current status of the database, configuration, and chat
history work. It supersedes the original findings-only review and distinguishes
completed work from remaining validation, deferred scope, and open risks.

The current architecture is:

```text
Client
  -> API router / SSE transport
  -> ChatbotService
  -> SecurityStage
  -> OpenAI provider
  -> HistoryRepository
  -> Supabase public.chat_history
```

`SecurityStage` is implemented as a pre-provider guard. It normalizes the
message, runs the injection detector and configured content policy, and blocks
before provider/history side effects when a finding is present. The stage does
not log raw message text. Its typed decision is internal; the client receives a
generic `request_blocked` error.

Blocked requests are persisted in `public.chat_history` with
`status='blocked'`, the catalog response in `answer`, and no provider model or
usage. History views may include blocked records, but context construction must
query only `status='completed'`. Blocked persistence uses an independent
database session so provider/request transaction rollback cannot remove the
audit record.

FastAPI routes perform transport and dependency wiring. Provider calls remain
in the provider layer, and database access remains in the repository layer.

## Completion summary

| Area | Status | Summary |
|---|---|---|
| P0 importability and deployment configuration | Resolved in code/config | `Depends` is imported, `DATABASE_URL` is documented and passed through Compose. Clean-runtime and live-Supabase validation remain outstanding. |
| P1 ChatHistory persistence | Implemented, not production-verified | `ChatHistory`, repository, session UUID propagation, and completed/error persistence are wired. Error-transaction behavior and live insert validation remain open. |
| P2 configuration normalization | Resolved in implementation | One cached `pydantic-settings` model is used and model defaults are aligned. Pytest validation remains outstanding. |
| P3 history reads and ownership | Deferred | No history-read endpoint or ownership boundary is enabled. This is intentionally not production-ready. |
| P4 health/readiness semantics | Open | Connectivity check exists, but readiness status/error semantics and schema checks are incomplete. |

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

- A completed provider stream writes `status='completed'`.
- A provider exception attempts to write `status='error'` with any partial
  answer.
- `input_tokens`, `output_tokens`, `cost_usd`, `normalized_query`, and
  `retrieved_chunk_ids` are not produced by the current provider flow; they
  remain defaults or `null`.
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

3. **Backend test environment unavailable**
   - Focused tests exist under `backend/tests/`.
   - `pytest` was unavailable on the shell `PATH`, so the tests have not run.

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
   - Retrieval is not wired into the active stream, so
     `retrieved_chunk_ids` remains empty/null.

9. **Frontend lint baseline**
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
5. Execute a real chat request and verify the inserted row and generated
   `total_tokens` in `public.chat_history`.

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
14. Wire retrieval metadata only when real UUID chunk IDs are available.

### P4 — Operational hardening

15. Define `/health/db` as a readiness endpoint or diagnostic endpoint.
16. Return intentional non-2xx responses for unavailable dependencies.
17. Add schema compatibility checks for required `chat_history` columns.
18. Resolve or separately baseline the existing frontend lint failures.

## Validation record

- Python syntax validation for changed backend modules: **passed**.
- `git diff --check`: **passed**.
- `npm run build`: **passed**, with the existing CSS warning
  `Unexpected ";"`.
- `npm run lint`: **failed** on pre-existing frontend unused-variable and
  undefined-symbol errors.
- Backend pytest: **not run** because `pytest` was unavailable on `PATH`.
- Live Supabase connectivity/insert: **not verified**.

## Architectural impact

The implemented write path follows the documented boundaries:

- API route: request validation, dependency wiring, and SSE transport.
- Chatbot service: session resolution and application behavior.
- Provider: OpenAI-specific streaming.
- Repository: SQLAlchemy persistence.
- ORM model: database table mapping.

The remaining ownership and history-read work must preserve these boundaries.
