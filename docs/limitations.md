# Limitations (current state, Phase 5)

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

- **Planner, Architect, and Researcher agents are real** (`backend/app/agents/`):
  each makes a real call through the `LLMProvider` abstraction and its
  output is parsed with `Pydantic.model_validate` against a fixed schema
  (`app/agents/schemas.py`) — a response that doesn't parse gets one
  corrective retry, then the node raises (`app/agents/llm_json.py`); there
  is no fallback plan/architecture/research content. Verified two ways in
  this environment (no API key configured yet): the "no credentials" path
  is exercised for real (`test_run_fails_cleanly_when_no_llm_provider_configured`,
  and manually via a live HTTP request — the run ends `failed` with a
  `PLANNER_FAILED` message carrying the real provider error text, zero
  artifacts created); the real-generation path
  (`test_run_produces_real_plan_architecture_research_with_live_llm`) is
  `skipif`-guarded on a configured key and will start running automatically
  once one is added to `backend/.env` — it is not run yet in this
  environment.
- **The Researcher's findings are grounded, not invented**: before calling
  the LLM, `repo_tools.list_files`/`search_keyword` do a real, deterministic
  filesystem scan of the task's project `repo_path`; any returned finding
  citing a `file_path` outside that scan is discarded
  (`researcher.filter_grounded_findings`, unit-tested directly) and recorded
  separately as `discarded_ungrounded_findings` in the persisted artifact —
  visible, not silently dropped.
- Each of the three agents' structured output is persisted as a real
  `Artifact` row (`GET /api/runs/:id/artifacts`, new in this phase), linked
  from its `agent_messages` row via `artifact_id`.
- **Developer, Reviewer, QA, and Security are real** (Phase 5):
  - Developer (`backend/app/agents/developer.py`) makes a real LLM call,
    then applies the result to a real Git working tree via
    `backend/app/git_integration/git_ops.py` — a thin wrapper that shells
    out to the actual `git` CLI (branch create/checkout, file writes,
    commit, diff). `apply_developer_output` is unit-tested independent of
    the LLM call with a hand-built `DeveloperOutput`
    (`tests/test_developer_apply.py`), and `git_ops` itself is tested
    against real temp git repositories (`tests/test_git_ops.py`) — every
    assertion is against real `git` command output, nothing simulated.
  - Reviewer makes a real LLM call over the actual `git diff` and persists
    findings as real `Review` rows. `state["review_findings"]` now feeds
    `routing.route_after_reviewer` (built in Phase 3, inert until now) with
    real data for the first time.
  - QA (`backend/app/agents/qa.py`) and Security
    (`backend/app/agents/security_scan.py`) are **deterministic — no LLM
    call at all**. QA detects and actually executes the target repo's test
    command via subprocess (real `pytest`/`npm test`, real exit code,
    real captured output — `tests/test_qa.py` proves both a genuinely
    passing and a genuinely failing test suite are reported correctly).
    Security runs a real regex-based scan for secret-shaped strings and
    risky constructs (`eval`, `exec`, `shell=True`, `pickle.loads`) over the
    files Developer actually changed (`tests/test_security_scan.py`).
  - On a Reviewer/QA-triggered retry, Developer is given the specific
    findings/failure output that caused it (`nodes._build_retry_feedback`,
    unit-tested in `tests/test_developer_retry_feedback.py`) so it attempts
    an actual fix, not a blind repeat.
  - New endpoints: `GET /api/runs/:id/reviews`, `/test-results`,
    `/security-findings`.
  - The Phase 4 real-LLM integration test now runs the full pipeline against
    a real temp git fixture repo once a key is configured — still
    `skipif`-guarded, not exercised in this environment yet (no key
    configured here).

## What does not exist yet

- No deterministic verification gate or policy engine exists yet
  (`backend/app/verification/`, `backend/app/policy/` are scaffolding only).
  The `policy` node does not create an `Approval` row or pause the run.
  Reviewer/Security findings are real and persisted, but nothing currently
  *blocks* a run on them — a high-severity finding is visible via the API,
  not enforced.
- No GitHub PR creation (Phase 5's git operations are local-only: real
  branches and commits, never a push or a remote API call), no
  failure-injection demos, no evaluation harness, no observability pipeline
  (OpenTelemetry/LangSmith), and no dashboard pages beyond the health panel
  on `/`.
- No dependency/CVE vulnerability database check — Security is a static
  pattern scan only (see Phase 5 trade-offs below).
- CI runs lint/type-check/tests for the real code that exists (including
  the deterministic Developer/QA/Security/git_ops tests), but the full
  agent pipeline's real-LLM path is not exercised in CI — no API key is
  configured there, by design (never commit one), so that path only runs
  wherever a developer has added their own key locally.

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

## Known trade-offs made in Phase 4

- The Researcher does a single deterministic retrieval pass (list files +
  keyword search) before one LLM call — not a multi-turn agentic
  tool-calling loop where the model could decide to search again based on
  what it saw. This keeps the LLM abstraction thin (`LLMProvider.complete`,
  one call in/one response out) and the grounding check simple, at the cost
  of the Researcher being unable to "dig deeper" within a single run. A real
  tool-calling loop is a reasonable future enhancement, not implemented here.
- The Architect's `challenges` field is populated by the LLM (spec §5.2:
  "should challenge the Planner when necessary") but nothing currently
  *acts* on a non-empty `challenges` list — it's recorded in the artifact
  and visible via the API, not yet wired into routing or a retry. That
  wiring is a natural fit for the Phase 6 policy engine, not built yet.
- Real-provider integration tests exist
  (`test_run_executes_full_pipeline_with_live_llm`) but have not actually
  executed against a live model in this environment — no API key has been
  configured here yet. They are `skipif`-guarded, not deleted or faked, and
  will run automatically once a key is added.

## Known trade-offs made in Phase 5

- **Full-file-content replacement, not diffs/patches.** Developer's LLM
  output is a complete file body per changed path, not a unified diff. This
  makes applying and unit-testing the result trivially deterministic
  (`git_ops.write_files` + `commit_all`, no patch/merge logic to get wrong),
  at the cost of being unable to make a surgical one-line change to a large
  existing file without the model reproducing the whole thing. A real
  diff/patch-based approach is a reasonable future improvement, not built
  here.
- **Security is a static pattern scan, not a dependency/CVE database
  check.** It catches secret-shaped strings and a handful of risky
  constructs (`eval`, `shell=True`, ...) via regex over changed files — real
  and deterministic, but it does not check `requirements.txt`/`package.json`
  against a vulnerability database (`pip-audit`, `npm audit`, or similar).
  Deliberately out of scope to avoid a network dependency on an external
  advisory service for this phase.
- **The base branch is assumed to be named `main`.** `git_ops.ensure_branch`
  checks out `main` before creating the task branch on first entry; if a
  target repo's default branch has another name, Developer still works (it
  falls back to branching from whatever is currently checked out) but the
  "branch from the real default" behavior silently doesn't apply. Not
  configurable yet.
- **Backend container now requires `git`.** The Dockerfile installs it and
  sets a container-local git identity (`agentforge@example.com`) — found
  and fixed while verifying this phase in Docker (the base `python:3.11-
  slim` image has no `git` binary at all, which would have made
  Developer/Reviewer fail silently-to-the-user as an unhandled subprocess
  error the first time someone actually ran this in a container with a real
  API key configured). CI's `ubuntu-latest` runner has `git` already but no
  configured identity, so the workflow now sets one before the test step —
  found by inspection while fixing the container, not by a CI failure.
