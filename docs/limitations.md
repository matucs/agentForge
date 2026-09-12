# Limitations (current state, Phase 10)

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
- **The deterministic Verification Gate is real** (`backend/app/verification/`):
  `checks.py` actually runs `mypy`/`ruff` (or `tsc`/`eslint` for a Node/TS
  repo) via subprocess — real tool execution, not a guess — and `gate.py`'s
  `evaluate_gate` combines that with the Reviewer/QA/Security results
  already in state under spec §10's fixed rules (typecheck failure, a
  required test failure, a blocking security finding, or a high-severity
  Reviewer finding each BLOCK; lint/low-severity issues are recorded but
  never block). Every rule is unit-tested in isolation
  (`tests/test_verification_gate.py`), and the subprocess runners are
  tested against real temp repos with an actual mypy type error and an
  actual ruff violation (`tests/test_verification_checks.py`) — confirmed
  to correctly report both a genuine pass and a genuine failure. Results
  persist as real `VerificationResult` rows
  (`GET /api/runs/:id/verification-results`).
- **The risk-based Policy engine is real** (`backend/app/policy/engine.py`,
  ADR-004): `classify_risk` inspects the actual changed-file paths and diff
  content (table-driven unit tests for every tier,
  `tests/test_policy_engine.py`, including the critical/`DROP TABLE`
  case), and `decide_policy` is enforced in `policy_node`, not merely
  described — a real `Approval` row is created for a high-risk change
  (`Run.status = "awaiting_approval"`), and `POST
  /api/approvals/:id/approve|reject` (spec §22) are the only way to move
  it forward, tested end to end against a directly-seeded pending approval
  (`tests/test_approvals.py`) and confirmed live via a manual HTTP request
  (`GET /api/approvals` → `POST .../approve` → real `approved` status +
  the linked `Run` flipped to `completed`; a second approve attempt
  correctly 409s).
- **Scope decision, not an oversight**: Policy is the last graph node before
  `END`, so "pausing for approval" does not interrupt/resume the LangGraph
  execution — the graph finishes normally and `Run.status` is simply left
  non-terminal-in-the-good-sense (`awaiting_approval`) until a human
  decides. `service.py`'s post-graph status write was fixed to respect
  whatever `policy_node` already set, rather than unconditionally
  overwriting it with `"completed"` (see Bugs section).
- **Real GitHub PR creation is wired in** (`backend/app/git_integration/`):
  `github_client.py` is a real REST client (`POST /repos/{owner}/{repo}/pulls`)
  with the same "unavailable, never fake success" contract as the
  `LLMProvider` abstraction (`GitHubClientUnavailable`), and `git_ops.py`
  gained a real `push_branch` (tested against an actual local bare
  repository standing in for "GitHub" — real `git push` mechanics, refspec
  and all, with zero network dependency, `tests/test_git_ops.py`).
  `pr_service.open_pull_request` is called after a run is already
  `completed` (auto-approved, or via `POST /api/approvals/:id/approve`) —
  PR creation is additive, never a merge gate, so a failure there is
  recorded and never reverts the policy decision. **Verified two ways in
  this environment (no `GITHUB_TOKEN` configured yet)**: the "no
  credentials" path is exercised for real
  (`test_open_pull_request_skips_cleanly_without_github_credentials`, and
  manually via a live HTTP request — approve a seeded pending approval →
  run flips to `completed` → a real `PR_CREATION_SKIPPED` event with the
  actual reason text, zero PR artifacts created); a real-PR test exists,
  `skipif`-guarded on `GITHUB_TOKEN`/`GITHUB_REPO`, not run yet here. The
  GitHub client's own request/response handling (auth header, URL, success
  parsing, error surfacing) is unit-tested with `httpx.MockTransport`
  (`tests/test_github_client.py`) — the same "fake the network boundary,
  test our own code" technique already used for the LLM retry logic and
  the orchestration timeout/cancel tests, not a simulation of GitHub's
  actual behavior.
- **Token/cost tracking is now real** (Phase 8): `complete_structured`
  (`app/agents/llm_json.py`) returns real usage alongside the parsed
  output, accumulated across retries so a failed parse attempt's real
  tokens are never dropped. `RunRepository.increment_usage` adds to (never
  overwrites) `Run.total_input_tokens`/`total_output_tokens`/
  `estimated_cost_usd` after every Planner/Architect/Researcher/Developer/
  Reviewer call. Exceeding `MAX_RUN_BUDGET_USD` raises `BudgetExceededError`,
  caught by `service.py` into a real `stopped_by_budget` status — tested
  with real DB rows (`tests/test_budget.py`).
- **Per-node observability is real** (`app/observability/`):
  `instrument_node` wraps all nine orchestration nodes, writing a real
  `ToolCall` row (duration, success/failure) and one structured log line
  per execution, and creating a real OpenTelemetry span — verified with
  `tests/test_instrumentation.py` (both the success and the
  raised-exception path leave a correct row behind) and manually via a live
  no-credentials run (`PLANNER_FAILED` correctly recorded as a failed
  `ToolCall`). Structured logs and tracing are also wired at the run level
  (`service.py`: `run_started`/`run_finished` events, a parent span per
  run).
- **`GET /api/metrics` is real** (`app/observability/metrics.py`,
  Prometheus text format): every Gauge is `.set()` from a live DB query at
  request time — verified two ways: `tests/test_metrics.py` seeds real rows
  and asserts the exposed text matches, and manually via a live HTTP
  request (ran one real no-credentials pipeline, hit `/api/metrics`,
  confirmed `runs_total`/`runs_by_status{status="failed"}` matched a direct
  `SELECT count(*) ... GROUP BY status` on the same database).
- **The evaluation harness is real** (`evals/tasks/*.yaml`,
  `app/evaluation/`): five task definitions load and validate
  (`tests/test_evaluation.py`, including a rejected malformed file); the
  runner executes each task through the real orchestration service
  (`run_to_completion`, `service.py`) against a disposable temp git fixture
  repo — the same code path a live run takes. The no-credentials path is
  always-on and tested as a real subprocess invocation of
  `python -m app.evaluation.runner`, asserting the exact spec §35 message
  and a non-zero exit; manually confirmed via `make eval` in this
  environment (no key configured here). Reviewer/QA/Security detection
  rate is intentionally left unmeasured (`EvaluationRun.reviewer_correct`
  etc. stay `None`) rather than invented — computing it honestly needs a
  task with a *known* injected bug to check detection against. Phase 10's
  failure-injection demos (below) prove the deterministic gate catches
  known-injected bugs when invoked directly; wiring that same known-bug
  signal into the eval harness's per-run scoring is not done and would be
  its own follow-up, not assumed here.
- **The full frontend dashboard is real** (`frontend/src/app/`): every page
  is a client component fetching from the live backend — `/`, `/runs`,
  `/runs/[id]`, `/tasks`, `/tasks/[id]`, `/agents`, `/evaluations`,
  `/operations`, `/approvals`. Two small new endpoints back the parts that
  had no JSON-shaped equivalent yet: `GET /api/evaluations` and
  `/api/evaluations/:id/runs` (real aggregates computed from `EvaluationRun`
  rows, tested in `tests/test_evaluations_api.py`), and
  `GET /api/operations/summary` (the same real DB queries
  `app/observability/metrics.py` already used for Prometheus, reshaped to
  JSON — `tests/test_operations_api.py`). Verified: `next build` and
  `tsc --noEmit` both clean; the full stack brought up in Docker (backend +
  frontend + Postgres + Redis) and every page hit for a real 200; a real
  task/run created via the API and its detail page confirmed reachable;
  CORS confirmed working for the frontend origin against the real backend.
  The "new task" form on `/tasks` calls the same
  `POST /api/projects`/`/api/tasks`/`/api/runs` +
  `POST /api/runs/:id/start` sequence the backend's own tests use — no
  separate "demo" code path.
- **The failure-injection demos are real** (`backend/app/demos/`,
  spec §13). Scenarios 2–4 (`make demo-failure`) need no LLM and always run:
  a disposable git fixture repo, a real commit standing in for "Developer
  just wrote this" (a genuinely broken `add()`'s subtraction bug, a
  genuinely hardcoded `AKIA...`-shaped AWS key, a genuine Alembic migration
  file), Reviewer's approval simulated and explicitly labeled as such in the
  module docstring and code comments (never hidden), then the real
  `qa_node` → `security_node` → `verification_node` → `policy_node` executed
  in sequence exactly as LangGraph would merge them. Verified live in this
  environment: Scenario 2's real `pytest` subprocess genuinely fails against
  the broken `add()` and the real Verification Gate genuinely blocks despite
  the simulated approval (`final_decision=BLOCKED_BY_VERIFICATION`);
  Scenario 3's real regex scan genuinely finds the secret and blocks the
  same way; Scenario 4's real `classify_risk` genuinely rates the
  `alembic/versions/...` path `high`, producing
  `final_decision=PENDING_HUMAN_APPROVAL`. Scenario 1 (Reviewer genuinely
  catching the bug via a real LLM call) and `make demo` (one real task
  through the full pipeline) are both gated on real LLM credentials —
  confirmed to print "Integration unavailable. Configure ANTHROPIC_API_KEY
  or OPENAI_API_KEY to enable this feature." and exit non-zero rather than
  fake a run, since no key is configured in this environment.

## What does not exist yet

- No cleanup of the Project/Task/Run rows the demo scripts create in the
  real dev database (only their temp git repos are cleaned up, via
  `tempfile.TemporaryDirectory`) — see Phase 10 trade-offs below.
- No dependency/CVE vulnerability database check — Security is a static
  pattern scan only (see Phase 5 trade-offs).
- No Slack/n8n notification when a run reaches `awaiting_approval` — an
  operator has to poll `GET /api/approvals` themselves; that integration is
  Phase 11.
- No PR update/close/merge operations, and no webhook handling for PR
  status changes coming back from GitHub — only creation.
- No separate LangSmith/Braintrust integration (see Phase 8 trade-offs
  below) — OpenTelemetry tracing plus the local console fallback is the
  observability backend actually implemented.
- No Grafana/Prometheus server wired into Docker Compose — `/api/metrics`
  is a real Prometheus-compatible endpoint, but nothing currently scrapes
  it in this repo's `docker-compose.yml`.
- CI runs lint/type-check/tests for the real code that exists (including
  the deterministic verification/policy/Developer/QA/Security/git_ops/
  github_client/instrumentation/metrics/evaluation tests), but the full
  agent pipeline's real-LLM path, the real-GitHub-PR path, and a real
  `make eval` run are not exercised in CI — no API key/GitHub token is
  configured there, by design (never commit one), so those paths only run
  wherever a developer has added their own credentials locally.

## Bugs found and fixed during development

- **A structured-logging call silently killed every node execution's
  finally-block cleanup (Phase 8).** `_logger.info("agent_execution",
  event=f"{agent_name}_node", ...)` passed `event` as both structlog's
  implicit first-positional-argument event name AND an explicit keyword,
  raising `TypeError: ... got multiple values for argument 'event'` inside
  `instrument_node`'s `finally` block — the ToolCall row was never written,
  and because this happened deep inside LangGraph's node-execution
  machinery, the resulting exception replaced the original one being
  propagated and the whole run silently hung at `status="running"` forever
  instead of ending `failed` (its background asyncio task raised, but
  nothing was polling it or logging the failure). Found because
  `tests/test_orchestration.py`'s timeout-sensitive tests started failing
  (`did not reach a terminal state within 5.0s`) immediately after wiring
  `instrument_node` into `nodes.py` — a real regression a real test caught,
  not found by inspection. Fixed by passing the event name only positionally
  (structlog already renders it as the `event` field) in both
  `instrumentation.py` and `service.py`'s equivalent calls.
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
- **`service.py` would have silently overwritten a real `blocked`/
  `awaiting_approval` outcome with `"completed"` (Phase 6).** The
  post-`graph.ainvoke` success path unconditionally wrote
  `status="completed"` — harmless while `policy_node` was a placeholder
  that never set anything else, but the moment `policy_node` became real
  and started setting `blocked`/`awaiting_approval` itself, this line would
  have clobbered it back to `completed` on every single run, making the
  entire policy engine's enforcement invisible at the one place
  (`GET /api/runs/:id`) everything else reads it from. Caught by inspection
  while wiring `policy_node`, before it was exercised by a test — fixed by
  reading the run's current status first and only defaulting to
  `"completed"` if it's still `"running"`.

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

## Known trade-offs made in Phase 6

- **`classify_risk`'s default tier for an unrecognized change is `medium`,
  not `low`.** Spec §11's table doesn't define a fallback; erring toward
  requiring at least Reviewer/QA/Security sign-off (which already happened
  earlier in the pipeline) rather than silently auto-merging an
  unclassified change seemed the safer default. Documented here rather than
  left implicit.
- **No literal LangGraph pause/resume.** As described above, "pausing for
  human approval" is implemented as `Run.status = "awaiting_approval"` plus
  a real `Approval` row, not as an interrupted/resumed graph execution —
  because Policy is already the last node before `END`, there is nothing
  downstream that would need to run later. If a future phase needs a risk
  trigger *earlier* in the pipeline (e.g. pausing before Developer writes
  files at all), that would need real interrupt/resume support this phase
  does not add.
- **Lint failures never block**, per a literal reading of spec §10's rule
  table (only Typecheck/Security/Tests/Reviewer are listed as BLOCK
  conditions). A stricter policy could treat lint as blocking too; this
  system currently treats it as informational only, recorded in
  `VerificationResult` but never in `blocking_reasons`.

## Known trade-offs made in Phase 7

- **The push URL embeds the token rather than assuming a pre-configured
  remote.** `pr_service` builds
  `https://x-access-token:<token>@github.com/<owner>/<repo>.git` from
  settings and pushes to it explicitly, rather than requiring `repo_path`
  to already have a correctly configured GitHub `origin`. This lets any
  local working tree — including throwaway temp fixture repos — be pushed
  to a real configured GitHub repo without per-repo remote setup, at the
  cost of the token briefly appearing in a subprocess argument list (not
  logged by this codebase, but visible to anything else inspecting process
  arguments on the host — a real consideration for a genuinely
  security-sensitive deployment, not addressed here).
- **PR creation always targets `main` as the base branch** (`_BASE_BRANCH`
  in `pr_service.py`), matching the same assumption `git_ops.ensure_branch`
  already makes about the default branch name (Phase 5). Not configurable
  per-project yet.
- **No retry on a transient GitHub API failure** (rate limit, momentary
  5xx) — a failure is recorded as `PR_CREATION_FAILED` once and that's it;
  there's no automatic re-attempt. An operator would need to notice and
  manually retry (there's no API endpoint for that yet either).
- **Real end-to-end PR creation has not been exercised in this
  environment** — no `GITHUB_TOKEN`/`GITHUB_REPO` were configured for this
  pass (a deliberate choice: doing so live would need a disposable real
  GitHub repository, a meaningfully bigger setup step than the Anthropic
  API key was). The `skipif`-guarded test and the wiring are real and ready
  to run the moment credentials are added.

## Known trade-offs made in Phase 8

- **No separate LangSmith/Braintrust SDK integration**, by deliberate
  choice: spec §15 explicitly treats these as optional ("if configured...
  if unavailable, must still work"), and our `LLMProvider` abstraction
  calls raw provider SDKs directly (not LangChain's `ChatAnthropic`/
  `ChatOpenAI` wrappers), so LangSmith's usual automatic instrumentation
  wouldn't trace those calls anyway without extra manual `@traceable`
  wiring. Real OpenTelemetry spans already satisfy the tracing requirement
  with zero added SaaS dependency; adding a second backend on top would be
  scope creep without new observability value.
- **`/api/metrics` recomputes every value from the database on every
  scrape** rather than maintaining running in-memory counters. This is
  the more honest choice (a number can never drift from what's actually in
  the database) at the cost of a query fan-out per scrape — fine at this
  project's scale, would need revisiting for a very high-frequency
  Prometheus scrape interval against a much larger dataset.
- **The evaluation harness measures real pipeline outcomes (success,
  duration, cost) but not agent *accuracy*** (Reviewer/QA/Security
  detection rate). Spec §14's example output includes those percentages;
  computing them for real requires a task with a *known* injected bug so a
  detection can be checked against ground truth — that's Phase 10's
  failure-injection harness. Rather than inventing plausible-looking
  percentages now, `EvaluationRun.reviewer_correct`/`qa_detected`/
  `security_detected` are left `None` (the schema already supports this —
  nullable columns from Phase 1) until Phase 10 can populate them
  honestly.
- **The evaluation runner processes tasks sequentially, one at a time**,
  awaiting each real pipeline run to completion before starting the next
  (`run_to_completion`, not the API's fire-and-forget `start_run`). Simple
  and correct; slower than running the 5 tasks concurrently, which would
  be a reasonable future optimization once evaluation sets grow larger.

## Known trade-offs made in Phase 9

- **No automated frontend tests.** Verification is `tsc --noEmit` +
  `next build` (both clean) plus manual checks against the real running
  backend (every page hit for a real 200 in Docker, a real task/run's
  detail page confirmed reachable, CORS confirmed). No component/e2e test
  suite (e.g. Playwright) was added — a reasonable next step, not claimed
  as done here.
- **The "new project" form's repo path is a path on the backend host, not
  something the browser can validate or browse to.** This mirrors how
  `Project.repo_path` already works everywhere else in the system (the
  agents operate on a real server-side git working tree); the form's
  placeholder text says so, but there's no server-side existence check at
  creation time — an invalid path only surfaces once a run actually tries
  to use it (Developer/QA/Security would fail for real, not silently).
- **The run detail page polls every 2 seconds while a run is active**, and
  the overview/operations pages poll every 5 seconds unconditionally. Simple
  and correct at this project's scale; a production deployment would more
  likely use the already-real Redis pub/sub or a WebSocket rather than
  polling — not built here, since polling is sufficient to demonstrate the
  real data flow honestly.

## Known trade-offs made in Phase 10

- **The Project/Task/Run rows the demo scripts create are not deleted.**
  Each scenario in `failure_scenarios.py`/`full_demo.py` cleans up its
  temporary git fixture repo (`tempfile.TemporaryDirectory`'s context
  manager), but the database rows are left in place — unlike the
  `real_client` test fixture, which deletes what it creates at teardown.
  This matches how a real "demo run" would look in the dashboard (it's a
  real run, not a fixture to be hidden), but it does mean repeated
  `make demo-failure`/`make demo` invocations accumulate rows in the dev
  database. Most tests are unaffected (the transactional `db_session`/
  `client` fixtures isolate each test via rollback, not raw table counts),
  but `test_operations_summary_reflects_real_run_status_counts` counts real
  rows visible to its transaction under Postgres' READ COMMITTED default —
  running the demos and that test back-to-back in the same dev database
  could make its counts drift. Verified clean in this environment (ran the
  demos, then the full suite, twice — no leftover rows and no flakiness
  observed since the dev Postgres volume was recreated fresh partway
  through this phase), but giving the demos their own cleanup, or scoping
  that test to only its own rows, is a reasonable follow-up, not done here.
- **Scenario 2/3/4's "Developer" step is a hand-written commit, not a real
  LLM Developer agent invocation.** This is the same trade-off spec §13
  calls for — proving the deterministic tail overrides an incorrect
  approval doesn't require spending an LLM call on the bug itself, only on
  making sure the bug is genuinely present in the file the deterministic
  nodes genuinely inspect. The bug/secret/migration content is real code
  actually committed to a real repo; only its authorship is scripted rather
  than LLM-generated.
- **Reviewer's approval in Scenarios 2–4 is simulated (`review_findings=
  []`), not a real LLM call**, and this is stated in the module docstring,
  in a code comment at the exact line it's set, and printed as "(simulated)"
  in every scenario's console output — never presented as if a real
  Reviewer approved the change.
