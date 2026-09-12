# AgentForge

**Governed Autonomous Software Engineering Platform.**

> Autonomy without verification is not production engineering.

AgentForge is a multi-agent system where LLM agents (Planner, Architect,
Researcher, Developer, Reviewer, QA, Security) propose and implement software
changes against a real Git working tree — but no agent's opinion is the final
authority. A deterministic verification gate (type checking, linting, tests,
security scanning, policy rules) and a risk-based human-approval policy decide
what actually merges. AgentForge does not try to make AI infallible; it
designs the system so AI mistakes are detectable, recoverable, and blocked
before they reach the final result.

## Status

This repository is being built incrementally, phase by phase (see
[docs/limitations.md](docs/limitations.md) for exactly what exists today vs.
what's planned). **Phases 1–8 — repository scaffold, backend domain
services, the LangGraph orchestration skeleton, all seven engineering
agents, the deterministic verification gate, the risk-based policy engine,
GitHub PR creation, and observability/evaluation — are complete.** The
dashboard UI is not implemented yet.

### What works right now

- FastAPI backend with a real Postgres + Redis health check (`/api/health`) —
  no hard-coded "healthy", verified by stopping/starting Redis and observing
  the reported status change.
- A normalized Postgres schema (Alembic-migrated) for the full entity model
  described in [docs/architecture.md](docs/architecture.md): projects,
  tasks, runs, agents, agent messages, artifacts, reviews, test results,
  security findings, verification results, approvals, evaluations, tool
  calls, and audit events.
- Real CRUD APIs over that schema — `POST/GET /api/projects`,
  `/api/tasks`, `/api/runs` — backed by a repository layer
  (`backend/app/db/repositories.py`), with real foreign-key validation
  (creating a task against an unknown project returns 404, not a raw DB
  error).
- A seeded agent registry (`GET /api/agents`) — the seven agents from the
  spec (Planner, Architect, Researcher, Developer, Reviewer, QA, Security),
  each with its real permission set (`allowed_tools`) from a data migration,
  not hard-coded in a UI component.
- A provider-agnostic `LLMProvider` abstraction with real Anthropic and
  OpenAI implementations (real API calls, real token/cost accounting from
  each response's actual usage) — a provider with no API key configured
  reports itself as unavailable rather than faking a response.
- A real **LangGraph orchestration graph** (`backend/app/orchestration/`)
  wiring all nine steps (Planner → Architect → Researcher → Developer →
  Reviewer → QA → Security → Verification → Policy) with conditional retry
  edges, a hard iteration cap (`MAX_AGENT_ITERATIONS`), a workflow timeout
  (`MAX_WORKFLOW_SECONDS`), and cancellation — checkpointed into Postgres via
  `AsyncPostgresSaver` (real rows, verified directly in `checkpoints`/
  `checkpoint_writes`).
- **Real Planner, Architect, and Researcher agents** (`backend/app/agents/`)
  — each makes a real LLM call through the provider abstraction and produces
  a schema-validated structured artifact (`GET /api/runs/:id/artifacts`):
  a plan (requirements/subtasks/acceptance criteria/risks/dependencies), an
  architecture proposal (the Architect is explicitly instructed to
  challenge the plan, not rubber-stamp it), and research findings. The
  Researcher's findings are grounded in a real, deterministic repository
  scan (`repo_tools.py`) done *before* the LLM call — any finding citing a
  file that scan never actually saw is discarded, not trusted. If no
  provider is configured, the run fails cleanly with a real error message
  (no fallback plan) — verified for both cases.
- **Real Developer, Reviewer, QA, and Security agents** — the full agent
  roster is now real:
  - **Developer** (`app/agents/developer.py`) makes a real LLM call and
    applies its output to an actual Git working tree: creates a real
    `agentforge/task-<id>` branch (`backend/app/git_integration/git_ops.py`,
    a thin real `git` CLI wrapper — no simulated repo state), writes files,
    and commits for real. On a Reviewer/QA-triggered retry, it's given the
    *specific* findings or failing test output that caused the retry, so it
    attempts an actual fix rather than repeating itself.
  - **Reviewer** makes a real LLM call over the actual `git diff` and
    persists structured findings as real `Review` rows — these now drive
    Phase 3's `route_after_reviewer` retry loop for the first time.
  - **QA and Security are deliberately deterministic — no LLM.** QA detects
    and actually executes the target repo's real test suite via subprocess
    (`app/agents/qa.py`) and persists a real `TestResult` row, driving
    `route_after_qa` for real. Security runs a real static pattern scan
    (`app/agents/security_scan.py`: secret-shaped strings, `eval`/`exec`/
    `shell=True`/`pickle.loads`) over the files Developer actually changed
    and persists real `SecurityFinding` rows. This is the "verify" half of
    the core principle showing up in the agents themselves, not only in the
    (still Phase 6) gate.
  - New endpoints: `GET /api/runs/:id/reviews`, `/test-results`,
    `/security-findings`.
- **A real deterministic Verification Gate** (`backend/app/verification/`) —
  the piece ADR-003 exists to justify. It runs its own real type-check/lint
  subprocess (mypy/ruff or tsc/eslint, whichever applies) and combines that
  with the Reviewer/QA/Security results already sitting in state, applying
  spec §10's fixed rules: a failed type check, a required test failure, a
  blocking security finding, or a high-severity Reviewer finding each BLOCK
  the run — a lint issue or low-severity finding does not. No LLM call
  anywhere in this module; the same inputs always produce the same
  PASS/FAIL. New endpoint: `GET /api/runs/:id/verification-results`.
- **A real risk-based Policy engine** (`backend/app/policy/engine.py`,
  ADR-004) — classifies the actual changed files/diff (docs/tests/frontend
  → low, dependency/API-shaped paths → medium, migration/deploy-config
  paths → high, an unguarded `DROP TABLE`/`DELETE FROM` inside a migration
  → critical) and enforces it in the backend: low/medium auto-merge
  (`Run.status = "completed"`), high creates a real `Approval` row and
  pauses the run (`Run.status = "awaiting_approval"`), critical or a failed
  verification gate blocks outright (`Run.status = "blocked"`) with no
  approval path at all. New endpoints: `GET /api/approvals`, `POST
  /api/approvals/:id/approve|reject` (spec §22) — enforcement lives here,
  not in whatever a client chooses to render.
- **Real GitHub PR creation** (`backend/app/git_integration/`) once a
  change is authorized to merge (auto-approved by policy, or a human
  approval): `git_ops.push_branch` really pushes the Developer's branch,
  and `github_client.py` makes a real `POST .../pulls` call to the GitHub
  REST API. No `GITHUB_TOKEN`/`GITHUB_REPO` configured → a real
  `PR_CREATION_SKIPPED` message explaining exactly why, never a fabricated
  PR link — the only path exercised live in this environment (verified via
  a real HTTP request: approve → run completed → real skip event, no
  fake artifact). A real-PR test exists, `skipif`-guarded on credentials
  being configured.
- **Real token/cost tracking and budget enforcement**: `Run.total_input_tokens`/
  `total_output_tokens`/`estimated_cost_usd` — silently `0` forever until
  this phase, which read exactly like the "fake token usage" spec §35
  forbids even though it was an omission, not a fabrication — now
  accumulate real usage from every LLM call. A run whose real accumulated
  cost exceeds `MAX_RUN_BUDGET_USD` (spec §34) stops with a real
  `stopped_by_budget` status, not a generic failure.
- **Real observability** (`backend/app/observability/`): structured JSON
  logs (`structlog`) with the spec §16 fields (timestamp/run_id/task_id/
  agent/event/duration/status); OpenTelemetry spans around every node and
  the overall run (a real OTLP exporter if `OTEL_EXPORTER_OTLP_ENDPOINT` is
  set, a real console exporter otherwise — spans are always real, only the
  export target differs); a real per-node `ToolCall` row
  (`GET /api/runs/:id/tool-calls`) recording actual duration/success, the
  real data source behind the metrics below (not an estimate).
- **`GET /api/metrics`** (Prometheus text format): every value is computed
  live from a real DB query at request time — runs by status, verification
  failures, human approvals, summed real token usage/cost, and per-agent
  average duration/error counts from `tool_calls`. Verified live: seeded
  real rows, confirmed the endpoint's numbers match a direct SQL count.
- **A real evaluation harness** (`evals/tasks/*.yaml` + `make eval`): five
  task definitions (the spec's own examples — pagination, authentication,
  websocket-reconnect, database-index, api-validation) executed through
  the actual orchestration service against a disposable git fixture repo,
  not a separate simulation path. No LLM credentials configured → prints
  spec §35's exact "Integration unavailable" message and exits non-zero —
  verified live in this environment (no key configured here) — never a
  fabricated report. Reviewer/QA/Security "detection rate" is honestly
  reported as not-yet-measurable rather than invented, since computing it
  for real needs the Phase 10 failure-injection harness.
- A Next.js/TypeScript/Tailwind frontend that renders the *live* health
  response from the backend.
- Docker Compose bringing up Postgres, Redis, backend, and frontend together
  (the backend image includes a real `git` CLI + identity, needed by
  Developer/Reviewer).
- CI (GitHub Actions) running lint, type-check, and tests on every push.

### What's not built yet

The full dashboard UI and failure-injection demos are planned in later
phases — see the roadmap below and [docs/limitations.md](docs/limitations.md).

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full target
architecture and [docs/adr/](docs/adr/) for the reasoning behind the key
decisions (why LangGraph, why Postgres over an in-memory store, why
verification is separate from LLM review, why risk-based human approval).

```
User → Web UI/API → Orchestrator (LangGraph)
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
    Planner         Architect       Researcher
        └───────────────┼───────────────┘
                  Shared Project State (Postgres)
                        │
                    Developer → Reviewer → QA → Security
                        │
                Deterministic Verification Gate
                        │
                    Policy Gate → Merge | Human Approval
```

## Repository layout

```
agentforge/
  backend/     FastAPI + SQLAlchemy + Alembic + LangGraph (Python)
  frontend/    Next.js + TypeScript + Tailwind
  evals/       Evaluation task dataset (planned, Phase 8)
  docs/        Architecture docs and ADRs
```

## Running locally

```bash
cp .env.example .env        # fill in ANTHROPIC_API_KEY / OPENAI_API_KEY to enable real LLM calls
docker compose up -d --build
docker compose exec backend alembic upgrade head
curl http://localhost:8000/api/health
open http://localhost:3000
```

Postgres and Redis are exposed on host ports **5433** and **6380** (not the
defaults) to avoid clashing with any other local instances.

## Development (without Docker)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check app && mypy app && pytest -q
```

```bash
cd frontend
npm install
npx tsc --noEmit && npm run build
```

## Roadmap

| Phase | Scope |
|---|---|
| 1 ✅ | Repo scaffold, DB schema, LLM provider abstraction, health check, CI |
| 2 ✅ | Backend domain services (projects/tasks/runs CRUD, repositories, agent registry) |
| 3 ✅ | LangGraph orchestration skeleton (graph, retries, checkpointing, timeout, cancellation) |
| 4 ✅ | Planner / Architect / Researcher agents (real LLM calls, grounded research) |
| 5 ✅ | Developer / Reviewer / QA / Security agents (real git commits, real test execution, real static scan) |
| 6 ✅ | Deterministic verification gate + risk-based policy engine |
| 7 ✅ | Git integration: real GitHub PR creation (push + REST API) |
| 8 ✅ | Observability (structured logs, metrics, tracing, real cost/budget tracking) + evaluation harness |
| 9 | Frontend dashboard (runs, tasks, agents, approvals, operations) |
| 10 | Failure-injection demos |
| 11 | n8n / Slack integration |
| 12 | Hardening, full test suite, deployment docs |

## License

MIT — see [LICENSE](LICENSE).
