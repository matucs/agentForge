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

## Implementation status (Phase 1)

Implemented:

- **Shared Project State** — Postgres, via SQLAlchemy models + Alembic
  migrations (`backend/app/db/models.py`). Every entity called out in the
  spec (projects, tasks, runs, agents, agent_messages, artifacts, decisions,
  reviews, test_results, security_findings, verification_results, approvals,
  evaluations, evaluation_runs, tool_calls, audit_events) is a normalized
  table, not a JSON blob.
- **LLM provider abstraction** (`backend/app/llm/`) — `LLMProvider` ABC with
  real `AnthropicProvider` and `OpenAIProvider` implementations, selected by
  `DEFAULT_LLM_PROVIDER`. Cost is computed from each response's actual
  reported token usage against published per-model pricing, not estimated.
- **Web UI/API substrate** — FastAPI app (`backend/app/main.py`) with a real
  `/api/health` check, and a Next.js frontend that renders it live.

Not yet implemented (see roadmap in [README.md](../README.md)):

- Orchestrator (LangGraph graph), the seven agents' actual reasoning/tool use,
  the Verification Gate's rule engine, the Policy Gate, Git branch/PR
  automation, engineering memory, observability pipelines, and the dashboard
  UI beyond the health panel.

## Why these technology choices

See [docs/adr/](adr/) for the detailed reasoning:

- [ADR-001](adr/ADR-001-agent-orchestration.md) — LangGraph for orchestration
- [ADR-002](adr/ADR-002-shared-state.md) — Postgres (not in-memory) for shared state
- [ADR-003](adr/ADR-003-verification-gate.md) — Verification gate separate from LLM review
- [ADR-004](adr/ADR-004-human-in-the-loop.md) — Risk-based human-in-the-loop policy
