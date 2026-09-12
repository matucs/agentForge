# AgentForge — Final Engineering Report

## What this project is

AgentForge is a governed autonomous software-engineering platform: a
LangGraph-orchestrated multi-agent pipeline (Planner, Architect,
Researcher, Developer, Reviewer, QA, Security) whose output only ships
through a deterministic Verification Gate and a risk-based human-approval
Policy Engine. The core principle, enforced in code rather than only
stated in a README: **LLMs propose and reason. Deterministic systems
verify.** No agent's approval — including the Reviewer's — is sufficient
on its own; QA's real test execution, Security's real static scan, and the
Policy Engine's real risk classification are the final, non-LLM authority.

## What was built, phase by phase

| Phase | Delivered |
|---|---|
| 1 | Repo scaffold, DB schema, LLM provider abstraction, health check, CI |
| 2 | Domain services (projects/tasks/runs CRUD, repositories, agent registry) |
| 3 | LangGraph orchestration skeleton — graph, retries, checkpointing, timeout, cancellation |
| 4 | Planner/Architect/Researcher — real LLM calls, grounded research |
| 5 | Developer/Reviewer/QA/Security — real git commits, real test execution, real static scan |
| 6 | Deterministic Verification Gate + risk-based Policy Engine |
| 7 | Git integration — real GitHub PR creation (push + REST API) |
| 8 | Observability (structured logs, metrics, tracing, real cost/budget tracking) + evaluation harness |
| 9 | Frontend dashboard (runs, tasks, agents, approvals, operations, evaluations) |
| 10 | Failure-injection demos proving the deterministic gate overrides an incorrect simulated approval |
| 11 | n8n/Slack integration (inbound webhook + outbound notifications) |
| 12 | This report, remaining docs, security/hardening pass, final verification |

Each phase was lint/type/test-clean (`ruff`, `mypy`, `pytest`, and
`tsc`/`next build` for the frontend) before moving to the next, and
verified live against a running Docker Compose stack — not just unit
tests in isolation. [docs/limitations.md](limitations.md) records, per
phase, what was actually run and observed, including the exact bugs found
along the way (below) and how each was caught.

## The single most important thing this project demonstrates

Phase 10's Scenario 2: a real git fixture repo with `add(a, b): return a -
b` — a genuine bug — paired with a *simulated* Reviewer approval
(`review_findings=[]`, explicitly labeled as such, never hidden). QA's
real `pytest` execution against the real repo genuinely fails. The real
Verification Gate genuinely blocks the change
(`final_decision=BLOCKED_BY_VERIFICATION`) despite the "approval." This is
not a mocked assertion — it's the actual gate code, the actual test
runner, and an actual broken file, run for real in this environment.
Scenarios 3 (a real hardcoded secret blocked by the real Security scan)
and 4 (a real migration file correctly classified `high` risk, requiring
real human approval) make the same point with different deterministic
checks.

## Notable bugs found and fixed during development

(Full detail in [limitations.md](limitations.md)'s bug log; the two worth
calling out here for what they reveal about the engineering process.)

- **A `TypeError` inside a `finally` block silently replaced the real
  underlying exception**, hanging every run at `status="running"` forever.
  `structlog`'s bound logger consumes its first positional argument as
  `event`; passing an explicit `event=` keyword alongside it raises
  `got multiple values for argument 'event'` — and because this happened
  in a `finally`, it masked whatever exception was actually propagating.
  Found not by inspection but because timeout-sensitive orchestration
  tests started failing immediately after instrumentation was wired in.
  The exact same class of bug recurred narrowly in Phase 11's webhook
  notifier and was caught the same way, this time by the test suite before
  it ever reached a live run.
- **A `server_default="now()"` bound as a literal Python string parameter,
  not raw SQL** — every row's `created_at` since Phase 1 was frozen to
  whichever instant the column was created, not a per-row timestamp. Fixed
  to `server_default=text("now()")`, with a regression test comparing two
  rows created moments apart in separately-committed requests
  (`test_created_at_is_a_real_per_row_timestamp_not_a_frozen_default`).

## What's deliberately out of scope

A real cloud deployment (this stays a local Docker Compose project by
design), a full CRM/ticketing UI (the n8n webhook is the integration
point, per spec), PR update/merge/close handling or webhooks back from
GitHub, and a LangSmith/Braintrust SDK integration (OpenTelemetry plus a
Console/OTLP exporter fallback was chosen instead — see the relevant ADR).
None of these were attempted and abandoned; they were never started,
and are named here so nothing is implied by omission.

## Verification checklist

- [x] Every agent that claims to call an LLM does so through a real
  provider abstraction with real token/cost accounting, and reports
  "unavailable" — never a fabricated response — without credentials.
- [x] The Verification Gate contains no LLM call and is independently
  testable/tested (`tests/test_verification_*.py`).
- [x] The Policy Engine's risk classification runs server-side on every
  real run, not only in the frontend.
- [x] Git operations are real subprocess calls against a real working
  tree; GitHub PR creation is a real REST call, gated on real credentials.
- [x] Metrics are computed live from the database at request time, never
  a stale or estimated counter.
- [x] The evaluation harness and failure-injection demos run the real
  pipeline/real deterministic nodes against real disposable fixture repos.
- [x] The frontend has no mock data path — every page fetches the live
  backend.
- [x] n8n/Slack integration performs real HTTP requests and no-ops
  (logged, not faked) when unconfigured.
- [x] `ruff`, `mypy`, `pytest` (backend) and `tsc --noEmit`, `next build`
  (frontend) are clean as of this report; see the final verification run
  below.
- [x] Every phase's docs/limitations.md entry is written from what was
  actually observed running, not from what the code is intended to do.
- [ ] Dependency/CVE vulnerability scanning — not built (pattern-based
  Security scan only; see [security.md](security.md)).
- [ ] Webhook signature verification, outbound delivery retry — not built
  (see [integrations.md](integrations.md)'s trade-offs).
- [ ] Automated frontend test suite (Playwright/component tests) — not
  built; frontend verification is `tsc`/`next build` plus manual checks
  against a live backend.

## Final verification run (Phase 12)

`ruff check app tests`, `mypy app`, and `pytest -q -rs` against the full
backend test suite, `npx tsc --noEmit` and `npm run build` against the
frontend, and `docker compose up -d --build` for the full stack — see the
commit this report ships with for the exact output captured during this
pass.
