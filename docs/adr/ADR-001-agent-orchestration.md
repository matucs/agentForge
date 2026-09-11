# ADR-001: LangGraph for Agent Orchestration

## Status

Accepted and implemented (Phase 3): the graph, checkpointer, retry routing,
iteration cap, timeout, and cancellation are real and tested. Node bodies
are still honest placeholders — see docs/limitations.md — Phase 4/5 replace
them without changing anything described here.

## Context

AgentForge needs to run a multi-step, multi-agent workflow (Planner →
Architect → Researcher → Developer → Reviewer → QA → Security → Verification
→ Policy) with:

- branching (Reviewer finds issues → back to Developer; QA fails → back to
  Developer)
- bounded retries (never an infinite Developer↔Reviewer loop)
- durable state across steps, so a run can be inspected, resumed, or paused
- a hard pause point for human approval that can be resumed later, possibly
  after the process restarts

## Options considered

1. **Hand-rolled state machine** (a Python dict + if/elif dispatch). Simple,
   but reimplements retries, checkpointing, and resumability from scratch —
   exactly the failure-prone plumbing a framework exists to solve.
2. **Celery/task-queue based orchestration.** Good for independent background
   jobs, but conditional branching and shared mutable state between steps
   (the message passed from Reviewer to Developer, for example) is awkward to
   express as a queue topology.
3. **LangGraph.** Purpose-built for exactly this shape: a directed graph of
   nodes over a typed state object, with conditional edges, retry policies,
   and a checkpointer that persists state so a run can pause (human approval)
   and resume without re-running completed nodes.

## Decision

Use LangGraph. The graph's nodes are agent steps; the shared state object is
the run's `AgentState` (requirements, plan, architecture, diffs, review
findings, test results, security findings, verification result, iteration
count); conditional edges implement the Reviewer/QA retry loops with an
explicit `max_iterations` cutoff enforced in code, not by convention.

## Consequences

- As implemented, the API layer answers `GET /api/runs/:id` and
  `GET /api/runs/:id/events` from our own `runs`/`agent_messages` Postgres
  tables (per ADR-002), not by reading LangGraph's checkpointer directly —
  those tables are simpler to query relationally and are what the
  dashboard needs. LangGraph's checkpointer (`AsyncPostgresSaver`, its own
  `checkpoints`/`checkpoint_writes` tables in the same database) is real
  and durable, but its role turned out to be narrower than originally
  expected here: it lets a run resume from its last completed node — the
  actual within-run replay/resume mechanism — rather than being the API's
  read path.
- We take a dependency on LangGraph's abstractions (state reducers, node
  signatures) throughout `backend/app/orchestration/`. If LangGraph were
  abandoned, this layer — not the agents themselves, which only depend on
  `LLMProvider` and repositories — would need a rewrite.
- Retry limits, timeouts, and cancellation are graph-level concerns we must
  configure explicitly; LangGraph does not prevent an infinite loop by
  default, it gives us the primitives to bound one. Implemented as: an
  iteration cap compared in `routing.py`, `asyncio.wait_for` around the
  graph invocation for the timeout, and an in-process task registry for
  cancellation (see docs/limitations.md for that registry's one durability
  caveat).
