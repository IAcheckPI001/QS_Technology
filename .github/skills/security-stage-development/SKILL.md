---
name: security-stage-development
description: Design, implement, review, and extend the chatbot SecurityStage pipeline. Use for prompt-injection detection, content-policy blocking, request normalization, security decisions, blocked responses, SSE error mapping, blocked chat-history persistence, locale-aware response catalogs, privacy-safe logging, and security-stage tests in this repository.
argument-hint: "[security-stage task, detector, policy, flow, or review scope]"
---

# SecurityStage development

Use this skill when changing the chatbot request-safety pipeline. Read the
repository instructions and architecture documents before editing:

- `.github/copilot-instructions.md`
- `docs/ai/architecture.md`
- `docs/ai/current-state.md`
- `docs/ai/security-stage-pipeline.md`
- `docs/ai/decisions.md` when it exists

The design source of truth is `docs/ai/security-stage-pipeline.md`. Preserve
the existing architecture unless the requested change requires a documented
decision.

## Core architecture

The request path is:

```text
Client
  -> router/schema validation
  -> session existence and authorization
  -> SecurityStage
  -> context/retrieval
  -> provider
  -> history persistence
  -> SSE/API response
```

Keep these boundaries:

- **Router** owns transport concerns, dependency wiring, request IDs, and SSE
  mapping. It must not contain detector rules or provider calls.
- **ChatbotService** owns the application flow and decides whether the
  provider may run. It must invoke `SecurityStage` before context/retrieval
  and before the provider.
- **SecurityStage** owns detector orchestration and produces a typed security
  decision. It must not know about FastAPI, SSE, HTTP status codes, or frontend
  components.
- **Detectors and policies** live below
  `backend/app/modules/chatbot/stages/security/`. Provider-specific LLM code
  must remain behind the provider/service boundary.
- **HistoryRepository** owns persistence. UI history and LLM context are
  different use cases: blocked records may be visible to history/audit, but
  only completed records may enter model context.

The v1 order is intentional: schema validation, session checks,
`SecurityStage`, context/retrieval, provider, and history. Do not treat a
client-supplied `session_id` or locale as a credential.

## Typed contract

Use the existing security models in
`backend/app/modules/chatbot/schemas/system/security.py`:

- `SecurityAction`: `ALLOW`, `BLOCK`, and the reserved `REVIEW`;
- `SecuritySeverity`;
- `SecurityFinding`;
- `SecurityDecision`.

When adding a field, keep schemas explicit, serializable, and versionable.
Aggregate findings deterministically:

1. a blocking finding wins over allow;
2. the highest severity becomes the decision severity;
3. rule IDs and finding order remain stable;
4. internal rule details and raw evidence are not exposed to clients.

Policy loading or detector configuration failures are system failures, not
successful allows. Required policy failures should fail closed, emit a
privacy-safe log with the request ID, and return a generic system error.

## Implementing a detector

Before adding a detector:

1. Search for an existing detector, protocol, policy catalog, and test.
2. Define a stable detector ID, category, severity, rule ID, and matching
   behavior.
3. Reuse the normalized views from
   `backend/app/util/normalize.py`; do not normalize independently in every
   detector.
4. Keep the original message unchanged for the provider and persistence.
5. Return typed findings; do not raise transport exceptions or emit SSE.
6. Add positive, negative, boundary, and regression tests.

### Normalize

Normalization is a deterministic detection aid, not a rewrite of user input.
Keep the original text and derive only the views needed for detection:

- NFC;
- case-folded text;
- accent-folded text where appropriate for Vietnamese;
- control/zero-width character metadata when required.

Never print or log the original text, normalized text, detection views, or
unredacted evidence. Be explicit about null bytes and control characters.
Normalization must not silently change the text sent to the provider.

### InjectionGuard

Maintain rule definitions in the versioned policy catalog:

`backend/app/modules/chatbot/stages/security/policies/injection_rules.py`

Do not put the entire rule catalog in `injection_guard.py`. The detector
implementation should consume the catalog and remain responsible for matching,
finding construction, and detector-specific logic.

Initial rule families include:

- ignore previous/prior/above instructions;
- role overrides such as “you are now”, “pretend you are”, and “act as if”;
- system or instruction tags such as `<system>`, `[SYSTEM]`, `[INST]`, and
  `<<SYS>>`;
- explicit instruction injection such as “new instruction”, “override”, and
  “system prompt”;
- null bytes;
- delimiter escapes and pseudo-tags such as “end of system” and
  `<instructions>`.

Avoid an indiscriminate substring blacklist. Use boundaries or context
requirements where possible, and test legitimate questions that discuss
prompt injection as a topic.

### ContentPolicy

Keep blacklist/topic policy separate from injection rules. Give each policy
rule an explicit identifier, category, severity, and rationale. Do not embed
business-topic policy in the router or provider. Make policy behavior
configurable and testable without network calls.

### OverflowHandler

`MessageText` currently enforces the request character limit. Do not add a
second character-limit implementation. Add an overflow handler only when the
system has a real token, context, or combined-payload limit. Decide explicitly
whether overflow is rejected, truncated, summarized, or reviewed; never
silently truncate user content.

## Block flow and user experience

The intended block flow is:

```text
SecurityStage -> SecurityBlockedError
  -> ChatbotService persists blocked audit/history
  -> ChatbotService re-raises the domain exception
  -> router logs safe metadata and emits SSE error
  -> frontend renders the backend response as an assistant message
```

Keep `SecurityBlockedError` at the domain/application boundary. Do not emit
`_sse_event()` from the stage or service: doing so couples business logic to
FastAPI/SSE and makes the flow hard to reuse.

The block event uses the stable transport code `request_blocked` and includes
the request ID. Do not send detector names, matched patterns, confidence
details, or raw request content to the client.

Backend owns user-facing block responses in:

`backend/app/modules/chatbot/stages/security/policies/responses.py`

Use a response code plus locale, not frontend-authored security text. Normalize
an allowlisted UI locale (`vi-VN` to `vi`, `en-US` to `en`) and use a safe
fallback for unsupported values. Locale is a preference, not an authorization
signal. Do not call an LLM solely to detect message language in v1.

The frontend should preserve the existing stream error parser and handle
`request_blocked` separately from generic transport errors. It may display the
backend message in the assistant placeholder without pretending that the
provider produced a `delta` stream. Do not retry a policy block automatically.

## Blocked history and context safety

When the requirement includes audit/history persistence:

- create a `ChatHistory` record with `status="blocked"`;
- preserve the original query only according to the approved retention and
  access policy;
- store the catalog response in `answer`;
- use `model=None` and record latency when available;
- keep blocked persistence independent from the provider transaction so a
  later rollback cannot erase the audit record;
- never add blocked content to model context.

Keep repository methods explicit for the two read paths:

- history/audit listing may include `completed`, `error`, and `blocked`;
- context construction must filter to `status="completed"` only.

If a database enum or check constraint exists, update it and add a migration.
If status is a plain string without a constraint, still add regression tests
and document the accepted status values. Consider retention, ownership,
access control, idempotency on client retry, and structured policy metadata
before production rollout.

## Privacy and observability

Log only safe metadata, such as:

- request ID and session ID;
- decision action and highest severity;
- policy version;
- finding count or redacted rule IDs;
- latency and outcome.

Never log raw user text, normalized views, system prompts, full evidence,
credentials, or `.env` values. If raw blocked text must be retained for
moderation, treat it as sensitive data and define retention, access control,
redaction, and deletion behavior.

Use structured logs where the existing logging setup supports them. Security
events should distinguish `blocked` from provider `error`; a policy block is
not a provider failure.

## Testing and validation workflow

Add or update tests near the affected behavior:

- normalization and control-character tests;
- detector positive/negative/boundary tests;
- decision precedence and policy-version tests;
- blocked requests never calling context/provider;
- `SecurityBlockedError` mapping to `request_blocked`;
- locale normalization and response fallback;
- blocked history status/answer/model assertions;
- context filtering that excludes blocked records;
- frontend rendering and no-retry behavior when applicable.

Run the smallest relevant backend tests first, then the repository baseline.
For this repository, also run the applicable frontend build and lint checks.
Use the existing commands from `package.json` and backend configuration rather
than inventing new tooling. Report pre-existing failures separately from
failures introduced by the change.

Before completion, verify:

1. provider calls are impossible on a block path;
2. transport code remains outside the security domain;
3. no raw security-sensitive content is logged or returned;
4. completed context cannot include blocked history;
5. schemas, migrations, tests, and documentation match the behavior;
6. architecture/current-state documentation is updated when boundaries or
   operational behavior change.

## Change checklist

- [ ] Read the architecture and current-state documents.
- [ ] Identify affected router, service, stage, policy, repository, schema,
      frontend, tests, and documentation files.
- [ ] Reuse existing protocols and helpers before adding new abstractions.
- [ ] Keep provider and transport concerns out of the security stage.
- [ ] Version policy and response catalogs.
- [ ] Preserve original input while using normalized detection views.
- [ ] Add privacy-safe logging and explicit error behavior.
- [ ] Persist blocked history only when requested and exclude it from context.
- [ ] Add focused regression tests.
- [ ] Run backend tests, frontend build/lint as applicable, and compile/import
      validation where appropriate.
- [ ] Record known limitations such as false positives, retention, or
      pre-existing validation failures.
