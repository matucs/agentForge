# Architecture

## Core principle

**LLMs propose and reason. Deterministic systems verify.** No LLM agent's
approval — including the Reviewer's — is sufficient on its own to let a
change through. The Verification Gate (type checking, linting, tests,
security scanning, policy rules) and the Policy Engine (risk-based human
approval) are deterministic code paths that make the final pass/fail call.

## Target architecture

```
                         ┌───────────────┐
                         │     User      │
                         └───────┬───────┘
                                 │
                         ┌───────▼───────┐
                         │   Web UI/API   │
                         └───────┬───────┘
                                 │
                    ┌────────────▼────────────┐
                    │      Orchestrator       │
                    │       LangGraph         │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
          Planner           Architect          Researcher
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 │
                         Shared Project State (Postgres)
                                 │
                         ┌───────▼───────┐
                         │   Developer   │
                         └───────┬───────┘
                                 │
                         ┌───────▼───────┐
                         │    Reviewer   │
                         └───────┬───────┘
                                 │
                         ┌───────▼───────┐
                         │      QA       │
                         └───────┬───────┘
                                 │
                         ┌───────▼───────┐
                         │   Security    │
                         └───────┬───────┘
                                 │
                    ┌────────────▼────────────┐
                    │ Deterministic Verifier   │
                    └────────────┬────────────┘
                                 │
                         ┌───────▼───────┐
                         │  Policy Gate  │
                         └───────┬───────┘
                                 │
                       ┌─────────┴─────────┐
                       ▼                   ▼
                     Merge            Human Approval
```

## Implementation status (Phase 11 complete; see roadmap)

Every box in the diagram above is a real, working implementation as of
Phase 11 — not a placeholder. In brief (each linked doc has the full
detail, including exactly how it was verified):

- **Shared Project State** — Postgres, via SQLAlchemy models + Alembic
  migrations (`backend/app/db/models.py`). Every entity in the diagram
  (projects, tasks, runs, agents, agent_messages, artifacts, reviews,
  test_results, security_findings, verification_results, approvals,
  evaluations, evaluation_runs, tool_calls) is a normalized table.
- **Orchestrator** — a real LangGraph `StateGraph` with conditional
  retry edges and Postgres checkpointing. See
  [orchestration.md](orchestration.md).
- **Planner/Architect/Researcher/Developer/Reviewer** — real LLM calls
  through a provider-agnostic `LLMProvider` abstraction (Anthropic/OpenAI),
  real git commits for Developer. **QA/Security** — real `pytest`/static-
  scan subprocess execution, no LLM. See [agent-model.md](agent-model.md).
- **Verification Gate + Policy Engine** — deterministic, no LLM anywhere in
  either module; this is the piece the whole project's core principle
  rests on. See [verification.md](verification.md) and
  [security.md](security.md).
- **Git/GitHub integration** — real branch/commit/diff operations, real
  GitHub PR creation via the REST API (credential-gated).
- **Observability** — real structured logs, OpenTelemetry spans, and
  live-computed Prometheus metrics. See [observability.md](observability.md).
- **Evaluation harness** — real pipeline runs against disposable fixture
  repos. See [evaluation.md](evaluation.md).
- **Frontend dashboard** — Next.js pages, all fetching the live backend,
  no mock data.
- **Failure-injection demos** (`make demo-failure`) — real proof that the
  deterministic gate overrides an incorrect simulated approval.
- **n8n/Slack integration** — real inbound webhook, real outbound
  notifications. See [integrations.md](integrations.md).

What's explicitly not built, and why, is tracked continuously in
[limitations.md](limitations.md) rather than here — that file is the
single source of truth for "what's real right now" and is updated at the
end of every phase, so it never goes stale the way a status section in
this file would.

## Why these technology choices

See [docs/adr/](adr/) for the detailed reasoning:

- [ADR-001](adr/ADR-001-agent-orchestration.md) — LangGraph for orchestration
- [ADR-002](adr/ADR-002-shared-state.md) — Postgres (not in-memory) for shared state
- [ADR-003](adr/ADR-003-verification-gate.md) — Verification gate separate from LLM review
- [ADR-004](adr/ADR-004-human-in-the-loop.md) — Risk-based human-in-the-loop policy
