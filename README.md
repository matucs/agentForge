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
what's planned). **Phases 1–2 — repository scaffold, architecture
foundation, and backend domain services — are complete.** Agent
orchestration, the verification gate, and the dashboard UI are not
implemented yet; these phases establish the substrate they will be built on.

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
- A Next.js/TypeScript/Tailwind frontend that renders the *live* health
  response from the backend.
- Docker Compose bringing up Postgres, Redis, backend, and frontend together.
- CI (GitHub Actions) running lint, type-check, and tests on every push.

### What's not built yet

LangGraph orchestration, the seven engineering agents' actual reasoning
logic, the deterministic verification gate, the policy engine, Git
branch/PR automation, observability/evaluation pipelines, the full
dashboard, and failure-injection demos are all planned in later phases — see
the roadmap below and [docs/limitations.md](docs/limitations.md).

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
| 3 | LangGraph orchestration skeleton |
| 4 | Planner / Architect / Researcher agents |
| 5 | Developer / Reviewer / QA / Security agents |
| 6 | Deterministic verification gate + policy engine |
| 7 | Git integration (branches, diffs, PRs) |
| 8 | Observability + evaluation harness |
| 9 | Frontend dashboard (runs, tasks, agents, approvals, operations) |
| 10 | Failure-injection demos |
| 11 | n8n / Slack integration |
| 12 | Hardening, full test suite, deployment docs |

## License

MIT — see [LICENSE](LICENSE).
