# ADR-001: LangGraph for Agent Orchestration

## Status

Accepted (orchestration graph itself is implemented in Phase 3, not yet built).

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

- LangGraph's checkpointer becomes the source of truth for "where is this run
  right now," which the API layer queries to answer `GET /api/runs/:id`.
- We take a dependency on LangGraph's abstractions (state reducers, node
  signatures) throughout `backend/app/orchestration/`. If LangGraph were
  abandoned, this layer — not the agents themselves, which only depend on
  `LLMProvider` and repositories — would need a rewrite.
- Retry limits, timeouts, and cancellation are graph-level concerns we must
  configure explicitly; LangGraph does not prevent an infinite loop by
  default, it gives us the primitives to bound one.
