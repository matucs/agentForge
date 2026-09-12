# Agent Model

Seven agents, each a thin wrapper around either a real LLM call or a real
deterministic check. None of them is the final authority on whether a
change ships — see [verification.md](verification.md) and
[docs/adr/ADR-003-verification-gate.md](adr/ADR-003-verification-gate.md).

| Agent | Real LLM call? | What it actually does | Source |
|---|---|---|---|
| Planner | Yes | Breaks `requirement_text` into a structured plan (`PlannerOutput`) | `app/agents/planner.py` |
| Architect | Yes | Proposes a design/approach given the plan (`ArchitectOutput`) | `app/agents/architect.py` |
| Researcher | Yes | Grounded research pass feeding the Developer (`ResearchOutput`) | `app/agents/researcher.py` |
| Developer | Yes | Writes real file changes and commits them to a real git branch | `app/agents/developer.py` |
| Reviewer | Yes | Reviews the real diff, returns structured `findings` with severities | `app/agents/reviewer.py` |
| QA | No | Runs the real test suite via subprocess (`pytest`) against the repo | `app/agents/qa.py` |
| Security | No | Regex-based static scan of real changed file content | `app/agents/security_scan.py` |

All four real-LLM agents go through the same `LLMProvider` abstraction
(`app/llm/base.py`, `anthropic_provider.py`, `openai_provider.py`): a
`generate_structured` call that returns both a Pydantic-validated output and
an `LLMUsage` (real `input_tokens`/`output_tokens` from the provider's own
response, priced against a per-model table — never estimated). No
configured API key means every one of these agents raises rather than
fabricates a plausible-looking response (spec §35); `GET /api/health`
reports `anthropic_configured`/`openai_configured` from the same settings.

## Structured output, not free text

Every LLM-backed agent call goes through `app/agents/llm_json.py`, which
asks the model for JSON matching a Pydantic schema and validates the
response — a schema violation is a real error surfaced to the caller, not
silently coerced or retried into looking valid.

## Tools

- Developer/Reviewer/QA/Security all operate on `state["repo_path"]`, a
  real path to a git working tree, through `app/git_integration/git_ops.py`
  (`ensure_branch`, `write_files`, `commit_all`, `get_diff`,
  `changed_files`) — real `git` subprocess calls, no libgit2/simulated diff.
- The agent registry seeded in the database (`GET /api/agents`, seen on the
  frontend's `/agents` page) records each agent's declared
  `allowed_tools`/`responsibilities` — descriptive metadata, not an
  enforcement mechanism; nothing currently stops an agent's LLM output from
  requesting an undeclared tool, since the only tools that exist today
  (git/pytest/regex scan) are hardcoded into each node, not dynamically
  dispatched.

## Retry loops (spec §6)

`route_after_reviewer`/`route_after_qa` (`app/orchestration/routing.py`)
send a change back to the Developer on a high-severity Reviewer finding or
a failed test — but only while `state["iteration_count"] <
MAX_AGENT_ITERATIONS` (default 6). Past the cap, forward progress is
forced (on to QA/Security respectively) rather than looping forever; the
Verification Gate downstream still blocks a genuinely broken change
regardless of how it got there. `iteration_count` is incremented by the
Developer node itself on every real entry, not estimated.

## How this was verified

Real `pytest` runs of `tests/test_developer_apply.py`,
`test_developer_retry_feedback.py`, `test_researcher.py`, `test_qa.py`,
`test_security_scan.py`, `test_routing.py`, and `test_orchestration.py`
(scripted `LLMProvider` doubles for deterministic unit tests of parsing/
validation/routing logic, and — separately, spec §13's failure-injection
demos and `make demo`/`make eval` — real live calls when credentials are
configured).
See [docs/limitations.md](limitations.md) for exactly which paths have been
exercised with a real API key in this environment versus which are
credential-gated and confirmed only to report "unavailable" correctly.
