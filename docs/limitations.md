# Limitations (current state, Phase 2)

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

## What does not exist yet

- No agent (Planner, Architect, Researcher, Developer, Reviewer, QA,
  Security) has any reasoning logic implemented yet. `backend/app/agents/`
  is currently empty package scaffolding; only their registry rows
  (name/role/responsibilities/allowed_tools) exist.
- No LangGraph orchestration graph exists yet (`backend/app/orchestration/`
  is scaffolding only).
- No deterministic verification gate or policy engine exists yet
  (`backend/app/verification/`, `backend/app/policy/` are scaffolding only).
- No Git integration, no PR creation, no failure-injection demos, no
  evaluation harness, no observability pipeline (OpenTelemetry/LangSmith),
  and no dashboard pages beyond the single health panel on `/`.
- CI currently runs lint/type-check/tests for the scaffold that exists; it
  does not yet exercise agent workflows because none exist.

## Known trade-offs made in Phase 1

- Postgres/Redis are exposed on host ports 5433/6380 instead of the
  standard 5432/6379, because this development machine already runs other
  Postgres/Redis instances on the standard ports. Internal container-to-
  container communication still uses the standard ports.
- The frontend Docker image runs `next dev` rather than a production build,
  matching the "local development" scope of Docker Compose per the spec —
  a production image is deferred to the deployment-hardening phase.
