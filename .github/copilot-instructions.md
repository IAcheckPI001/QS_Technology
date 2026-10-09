
## Architecture Rules

* Keep API transport logic separate from business logic.
* Keep provider-specific LLM code isolated behind provider/service interfaces.
* Do not place LLM provider calls directly inside FastAPI route handlers.
* Prefer dependency injection for infrastructure dependencies.
* Keep schemas explicit and versionable.
* Do not introduce a new framework or architectural pattern unless the task requires it.
* Preserve the existing architecture unless there is a clear technical reason to change it.

## Configuration

* Secrets must never be hard-coded.
* Use environment variables for credentials and deployment-specific configuration.
* Never read or expose `.env` contents.
* `.env.example` is the reference for required configuration keys.

## Validation

Before considering a change complete:

1. Run the relevant formatter/linter.
2. Run the relevant tests.
3. Run the application startup/import validation when appropriate.
4. Run and check npm run build, npm run lint
5. Report any validation failure explicitly.

Use the repository's existing commands before inventing new ones.

## Change Policy

Before changing architecture, first inspect:

* `docs/ai/architecture.md`
* `docs/ai/current-state.md`
* `docs/ai/decisions.md`

Do not rewrite unrelated modules merely to improve style.

For a small task, prefer a minimal change.

For a cross-module change, identify:

* affected modules
* API/schema impact
* dependency impact
* test impact
* backward compatibility risks

## Context Strategy

Use repository semantic search and targeted file inspection rather than loading the whole repository.

Prefer:

* relevant files
* relevant symbols
* architecture documentation
* existing tests
* existing error logs

Avoid loading generated files, dependencies, build artifacts, logs and large datasets unless they are directly relevant.

If documented architecture conflicts with the actual implementation, inspect the implementation and report the discrepancy instead of silently rewriting the documentation.

## Documentation

Keep durable architectural knowledge in:

* `docs/ai/architecture.md`
* `docs/ai/current-state.md`
* `docs/ai/decisions.md`
* `docs/ai/known-issues.md`

When a task changes an architectural decision or important workflow, update the appropriate document.

## Completion Format

At the end of a task, report:

* What changed
* Files changed
* Tests/validation executed
* Known issues
* Architectural impact
* Follow-up work, if any