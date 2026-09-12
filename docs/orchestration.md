# Orchestration

`app/orchestration/` implements the spec §6 graph on top of LangGraph. See
[docs/adr/ADR-001-agent-orchestration.md](adr/ADR-001-agent-orchestration.md)
for why LangGraph specifically.

## The graph

`app/orchestration/graph.py`'s `build_graph()`:

```
planner -> architect -> researcher -> developer -> reviewer
                                                       │
                                    ┌──────────────────┴──────────────────┐
                                    ▼ (high-severity finding, under cap)   ▼
                                developer                                 qa
                                                                           │
                                    ┌──────────────────────────────────────┴──┐
                                    ▼ (failed test, under cap)                ▼
                                developer                                 security -> verification -> policy -> END
```

The two conditional edges (`route_after_reviewer`, `route_after_qa` in
`app/orchestration/routing.py`) are the concrete mechanism behind spec
§13's headline claim: a failed real test sends control back to the
Developer regardless of what the Reviewer approved, and this happens
*before* the Verification Gate even runs — the gate is a second,
independent check on top, not the only place this is enforced. Both edges
respect `MAX_AGENT_ITERATIONS` (default 6) to guarantee forward progress
rather than looping forever, per spec §6.

## Shared state

`app/orchestration/state.py`'s `AgentState` (a `TypedDict`) is the one
object every node reads and returns a partial update to — LangGraph merges
each node's returned `dict` into the running state. It's the same shape
described in ADR-002: a single `run_id`-scoped state, not per-agent
private memory, so every agent downstream sees exactly what happened
upstream (the real `review_findings`, the real `test_results`, etc.) with
no possibility of one agent's LLM call independently claiming a different
version of reality.

## Execution and persistence

- **Checkpointing**: `AsyncPostgresSaver` (`langgraph.checkpoint.postgres`),
  keyed by `run_id` as the LangGraph `thread_id`, on the same Postgres
  instance as the domain schema but through `psycopg` rather than
  `asyncpg` — a separate driver/connection pool per LangGraph's own
  recommended setup (see the comment on `_checkpointer_conn_string` in
  `graph.py`).
- **Timeout**: `asyncio.wait_for(..., timeout=settings.max_workflow_seconds)`
  around the whole graph invocation (`app/orchestration/service.py`) — a
  real `TimeoutError` sets `status="stopped_by_timeout"`, not a silent hang.
- **Budget**: `BudgetExceededError`, raised wherever an LLM call would push
  `Run`'s running token-cost total past `MAX_RUN_BUDGET_USD` — checked
  against real accumulated cost from real provider responses, not
  estimated up front.
- **Cancellation**: `start_run`/`cancel_run` maintain an in-process
  `dict[str, asyncio.Task]`. Cancelling calls `task.cancel()`; the running
  node's `asyncio.CancelledError` propagates out and sets
  `status="cancelled"`. This registry is intentionally not durable — a
  backend restart mid-run leaves the `Run` row at whatever status it was
  last written to (usually `"running"`), which is itself the honest record
  that something was interrupted, not silently reported as complete (see
  [docs/limitations.md](limitations.md)).
- **Instrumentation**: every node is wrapped by `instrument_node` (see
  [observability.md](observability.md)) for a real span, log line, and
  `ToolCall` row per invocation, success or failure.

## Two entrypoints, one code path

- `start_run(run_id)` (`app/api/runs.py`'s `/start` endpoint,
  `app/api/webhooks.py`'s n8n endpoint) — fire-and-forget via
  `asyncio.create_task`, tracked in the cancellation registry.
- `run_to_completion(run_id)` (`app/evaluation/runner.py`, `make demo`) —
  awaits the same `_run_graph` coroutine directly, for a caller that wants
  to run one task and block on the real result.

Both call the exact same `_run_graph`; there is no separate "batch mode" or
"eval mode" graph.

## Terminal statuses

`pending -> running -> {completed, blocked, awaiting_approval, failed,
stopped_by_timeout, stopped_by_budget, cancelled}`. `policy_node` sets the
first three (see [verification.md](verification.md)); `_run_graph`'s
exception handlers set the rest. `_run_graph` only ever defaults an
unresolved `"running"` status to `"completed"` as a fallback — never
overwriting a real terminal decision policy_node already wrote (a bug fixed
in Phase 6, see [docs/limitations.md](limitations.md)'s bug log).

## How this was verified

`tests/test_orchestration.py` runs the real graph against a real fixture
repo end to end (credential-gated for the LLM-dependent path; the timeout/
budget/cancellation paths are exercised without needing a real LLM call by
constructing the relevant error conditions directly). `tests/test_routing.py`
unit-tests the conditional-edge functions in isolation. Phase 10's
failure-injection demos additionally prove the deterministic tail
(qa/security/verification/policy) produces the right outcome when invoked
directly, outside the full graph — see
[docs/limitations.md](limitations.md)'s Phase 10 section for the live
verification record.
