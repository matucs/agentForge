# Limitations (current state, Phase 3)

This file exists so nothing in this repository is misrepresented. It is
updated at the end of every phase.

## What is real right now

- `/api/health` performs a real `SELECT 1` against Postgres and a real
  `PING` against Redis on every call. It is not cached or hard-coded.
- The Anthropic and OpenAI providers make real SDK calls and compute cost
  from the token counts each API response actually reports. Neither has
  been exercised with a live API key in this environment (no key was
  configured), so the "configured" flags in `/api/health` currently show
  `false` for both — this is correct behavior, not a bug: absent credentials
  must report as unavailable, never as a silent mock.
- The database schema is real, migrated, and verified against a running
  Postgres 16 container in this environment.
- `POST/GET /api/projects`, `/api/tasks`, `/api/runs`, and `GET /api/agents`
  are real, tested against a live Postgres instance (transactional-rollback
  fixtures, not mocks): creating a task under a nonexistent project, or a run
  under a nonexistent task, returns a real 404 rather than a raw
  IntegrityError. The seven-agent registry is populated by an Alembic data
  migration, not hard-coded in a response handler.
- A real LangGraph orchestration graph (`backend/app/orchestration/graph.py`)
  runs all nine steps end to end, checkpointed into Postgres via
  `AsyncPostgresSaver` — confirmed by querying the `checkpoints` table
  directly after a run, not just by trusting the API's reported status.
  Retry routing (`routing.py`), the iteration cap, the workflow timeout, and
  cancellation are all real, tested code paths (`tests/test_routing.py`,
  `tests/test_orchestration.py`) — the timeout/cancellation tests use a
  substituted slow graph to make the race deterministically testable, not to
  fake agent behavior.

## What does not exist yet

- No agent (Planner, Architect, Researcher, Developer, Reviewer, QA,
  Security) has any reasoning logic implemented yet. Each orchestration node
  (`backend/app/orchestration/nodes.py`) writes one honestly-labeled
  placeholder `agent_messages` row (`payload.implemented = false`) and
  passes state through unchanged — no LLM call, no invented plan, finding,
  or test result. Message `type` values are deliberately neutral
  (`PLANNER_STEP_COMPLETED`, not `PLAN_CREATED`; `QA_STEP_COMPLETED`, not
  `TEST_PASSED`) so nothing claims an outcome that was never computed.
- No deterministic verification gate or policy engine exists yet
  (`backend/app/verification/`, `backend/app/policy/` are scaffolding only).
  The `policy` node does not create an `Approval` row or pause the run.
- No Git integration, no PR creation, no failure-injection demos, no
  evaluation harness, no observability pipeline (OpenTelemetry/LangSmith),
  and no dashboard pages beyond the single health panel on `/`.
- CI currently runs lint/type-check/tests for the scaffold that exists; it
  does not yet exercise agent workflows because none exist.

## Bugs found and fixed during development

- **`created_at` was frozen at migration-apply time for every table, for
  every row, since Phase 1.** `TimestampMixin` used
  `server_default="now()"` — a bare Python string, which SQLAlchemy binds as
  a literal *parameter*, not raw SQL. Postgres ended up with
  `DEFAULT '<the exact instant CREATE TABLE ran>'::timestamptz`, so every
  row inserted afterward without an explicit `created_at` got that one
  frozen timestamp, forever — confirmed by inspecting
  `information_schema.columns.column_default` and by observing identical
  `created_at` values across unrelated rows created hours apart. Found while
  manually verifying Phase 3's event ordering, not by a test (the existing
  tests happened not to check for cross-row time separation). Fixed to
  `server_default=text("now()")` plus a migration
  (`0debfa0f3ecc_fix_created_at_server_default_to_real_.py`) correcting the
  column default going forward, with a regression test
  (`test_created_at_is_a_real_per_row_timestamp_not_a_frozen_default`) that
  specifically requires the `real_client` fixture — the transactional-
  rollback `client` fixture wraps a whole test in one DB transaction, and
  Postgres's `now()` is constant for the life of a transaction by design, so
  that fixture cannot detect this class of bug.
- **`agent_messages` ordering could scramble under fast, near-simultaneous
  inserts.** Ordering by `(created_at, id)` broke when two messages landed
  in the same microsecond (plausible with sub-millisecond stub nodes) and
  the secondary sort key was a random UUID uncorrelated with insertion
  order. Fixed by adding a DB-generated monotonic `seq` (`BigInteger`,
  `Identity()`) column and ordering by it instead.

## Known trade-offs made in Phase 1

- Postgres/Redis are exposed on host ports 5433/6380 instead of the
  standard 5432/6379, because this development machine already runs other
  Postgres/Redis instances on the standard ports. Internal container-to-
  container communication still uses the standard ports.
- The frontend Docker image runs `next dev` rather than a production build,
  matching the "local development" scope of Docker Compose per the spec —
  a production image is deferred to the deployment-hardening phase.

## Known trade-offs made in Phase 3

- The in-flight-run registry used for cancellation
  (`app/orchestration/service.py`, `_running_tasks`) is an in-process
  `dict`, not durable. If the backend restarts mid-run, that run's
  `runs.status` row is left at `"running"` — an honest signal that
  something was interrupted — rather than silently reporting completion,
  but there is no automatic reconciliation yet (e.g. a startup sweep that
  marks stale `"running"` rows as failed). That reconciliation is deferred;
  tracked here rather than pretended away.
- The LangGraph checkpointer (`AsyncPostgresSaver`, via `psycopg`) is a
  separate connection/driver from the domain schema's SQLAlchemy/`asyncpg`
  engine, per ADR-001/ADR-002 — two Postgres client libraries against the
  same database. This is a deliberate, documented trade-off (the
  checkpointer library expects `psycopg`), not an oversight.
