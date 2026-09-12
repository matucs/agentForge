# Operations

How to actually run, observe, and operate AgentForge locally. This is the
practical companion to [architecture.md](architecture.md); see
[limitations.md](limitations.md) for what's deliberately not built.

## Running the stack

```bash
cp .env.example .env        # fill in ANTHROPIC_API_KEY / OPENAI_API_KEY to enable real LLM calls
docker compose up -d --build
docker compose exec backend alembic upgrade head
curl http://localhost:8000/api/health
open http://localhost:3000
```

Postgres and Redis are on host ports **5433**/**6380** (not the Postgres/
Redis defaults) specifically to avoid clashing with any other local
instances — the containers themselves still listen on 5432/6379
internally, Compose just remaps the host side.

`GET /api/health` is the first thing to check after startup: it reports
real `database`/`redis` connectivity and real `anthropic_configured`/
`openai_configured` booleans (from whether the env vars are non-empty, not
whether they're valid — an invalid key still surfaces as a real failure
the first time an agent actually calls it, not at health-check time).

## Everyday commands (`Makefile`)

| Command | What it does |
|---|---|
| `make up` / `make down` | Docker Compose up (build + migrate) / down |
| `make backend-lint` / `backend-typecheck` / `backend-test` | `ruff` / `mypy` / `pytest` |
| `make frontend-typecheck` / `frontend-build` | `tsc --noEmit` / `next build` |
| `make test` | All of the above, backend then frontend |
| `make demo` | One real task through the full live pipeline (credential-gated) |
| `make demo-failure` | The four failure-injection scenarios (see [limitations.md](limitations.md)) |
| `make eval` | Runs `evals/tasks/` against the real pipeline (credential-gated) |

## Operating a run

- **Start**: `POST /api/runs` then `POST /api/runs/:id/start` (or the
  dashboard's `/tasks` "new task" form, or `POST /api/webhooks/n8n` — all
  three converge on the same `orchestration.service.start_run`).
- **Watch**: `GET /api/runs/:id` for status/cost/duration, or
  `GET /api/runs/:id/events` for the real per-node agent message trace —
  the dashboard's `/runs/:id` page polls both live while a run is active.
- **Cancel**: `POST /api/runs/:id/cancel` — only works while the run is
  active in *this backend process* (the cancellation registry is
  in-process, not durable; see [orchestration.md](orchestration.md)).
- **Approve/reject a pending change**: `GET /api/approvals?status=pending`,
  then `POST /api/approvals/:id/approve` or `/reject` (dashboard's
  `/approvals` page has the same buttons wired to the same endpoints).
- **Get notified without polling**: configure `N8N_WEBHOOK_URL`/
  `SLACK_WEBHOOK_URL` (see [integrations.md](integrations.md)) — a run
  reaching a terminal status or needing approval posts a real webhook.

## Observing the system

- `GET /api/metrics` — Prometheus-format text, computed live from the DB
  at request time (see [observability.md](observability.md)). Nothing
  currently scrapes this in the provided Compose file.
- `GET /api/operations/summary` — the same aggregates as JSON, backing the
  dashboard's `/operations` page.
- Structured JSON logs on stdout (`docker compose logs -f backend`); real
  OpenTelemetry spans to the configured OTLP endpoint, or Console/Simple
  exporter fallback if none is configured.

## Database

Alembic migrations under `backend/alembic/versions/`. `docker compose exec
backend alembic upgrade head` after any pull that touches
`backend/app/db/models.py`. There is no seed/reset script beyond dropping
the Postgres volume (`docker compose down -v`) — this is a local
development project, not a production deployment target (see
[limitations.md](limitations.md)'s explicitly-out-of-scope list: a real
cloud deployment was never attempted here by design).

## When something looks stuck

- A run stuck at `status="running"` after a backend restart: the
  cancellation registry doesn't survive a restart, so this row is an
  honest record that something was interrupted, not evidence of a bug by
  itself — check the logs for what the backend was doing when it stopped.
- A demo/`make eval` run failing immediately: check `GET /api/health`
  first — the overwhelming majority of "immediate failure" cases in this
  project's own development were simply no LLM key configured, reported
  correctly as "Integration unavailable," not a real defect.
