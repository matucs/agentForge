# ADR-004: Risk-Based Human-in-the-Loop, Enforced in the Backend

## Status

Accepted. Policy engine implemented in Phase 6; this ADR fixes the
constraint that enforcement must live in the backend, not just the UI.

## Context

Not every change carries the same risk. A documentation fix and a database
migration should not require the same level of human oversight — full manual
approval on every change makes the system too slow to be useful; full
autonomy on every change is unsafe for high-risk actions (schema migrations,
production deploys, data deletion).

## Decision

Every action AgentForge can take is classified by risk level, and the policy
is enforced as backend logic (`backend/app/policy/`), not as a UI convention:

| Action | Risk | Policy |
|---|---|---|
| Documentation change | Low | Autonomous |
| Unit test creation | Low | Autonomous |
| Frontend change | Low | Autonomous |
| API contract change | Medium | Review |
| Dependency upgrade | Medium | Review |
| Database migration | High | Human |
| Production deployment | Critical | Human |
| Delete production data | Critical | Block |

A run that reaches a High/Critical-risk action transitions to a
`HUMAN_APPROVAL_REQUIRED` state and halts (via the LangGraph checkpointer,
per ADR-001) until an operator calls `POST /api/approvals/:id/approve` or
`/reject`. There is no code path that lets the frontend "skip" this by simply
not rendering an approval prompt — the orchestrator will not advance past a
pending approval regardless of what the UI does.

## Consequences

- The frontend's `/approvals` queue is a read/write view over backend state,
  not the mechanism that creates the gate.
- A `Block`-classified action (e.g. deleting production data) has no
  approval path at all — the only way past it is to not attempt it.
- Because the check lives in the orchestrator, an approval timeout (spec
  §33) has one place to be enforced: if no decision arrives within a
  configured window, the run moves to a `STOPPED_BY_APPROVAL_TIMEOUT` state
  rather than hanging indefinitely.
