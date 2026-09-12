# Verification Gate

The one piece of this system with a hard rule: **no LLM call anywhere in
`app/verification/`.** See
[ADR-003](adr/ADR-003-verification-gate.md) for why this is a separate
module rather than "ask the Reviewer if it's safe."

## What it checks (`app/verification/gate.py`'s `evaluate_gate`)

| Gate | Source of truth | Blocks? |
|---|---|---|
| `typecheck` | `run_typecheck` (real `mypy`/`tsc` subprocess, `checks.py`) | Yes, if applicable and failed |
| `lint` | `run_lint` (real `ruff`/`eslint` subprocess) | No — informational only, per spec §10's rule table |
| `unit_tests` | Real `test_results` from QA's real `pytest`/test-runner subprocess | Yes, if any test's `passed` is `False` |
| `security` | Real `security_findings` from the regex scan | Yes, if any finding has `blocking=True` |
| `reviewer` | Real `review_findings` from the Reviewer's real LLM call | Yes, if any finding has `severity="high"` |

`typecheck`/`lint` being "not applicable" (no `pyproject.toml`/
`tsconfig.json` found in the repo) is explicitly not a failure — a project
with no type checker configured shouldn't be blocked for lacking one it
never had. This matters for the disposable git fixture repos Phase 10's
demos and `make eval` construct: they're minimal repos, so typecheck/lint
report "not applicable" while unit tests, security, and the reviewer gate
still run against real content.

`overall_passed` is `True` only if none of the four blocking gates failed.
`blocking_reasons` is a real list of which ones did, for both the API
response and the console demos.

## What happens after the gate (`app/policy/engine.py`)

The gate's `overall_passed` feeds `decide_policy`, alongside a risk
classification from `classify_risk` (see ADR-004 and the rule table
below) — both pure functions, no I/O, no LLM:

| `verification_passed` | `risk` | Decision |
|---|---|---|
| `False` | — | `BLOCKED_BY_VERIFICATION` |
| `True` | `low`/`medium` | `AUTO_APPROVED` |
| `True` | `high` | `PENDING_HUMAN_APPROVAL` (real `Approval` row created) |
| `True` | `critical` | `BLOCKED_BY_POLICY` |

`classify_risk(changed_files, diff_content)` looks at real changed file
paths and real diff content — a migration file path (`alembic/versions/`,
`migrations/`) is `high`, or `critical` if the diff also contains an
unguarded `DROP TABLE`/`DELETE FROM` (no `WHERE`); deploy config
(`.github/workflows/`, `Dockerfile`, `docker-compose.yml`, `k8s/`) is
`high`; docs/tests/frontend-only changes are `low`; dependency manifests
and API/route/schema paths are `medium`; everything else defaults to
`medium` (a deliberately conservative default — see
[docs/limitations.md](limitations.md)). This is the exact code path Phase
10's Scenario 4 exercises against a real migration file.

Crucially, this classification happens in `policy_node`
(`app/orchestration/nodes.py`), server-side, on every real run — a
frontend that simply doesn't render an approval prompt cannot bypass it
(ADR-004's whole point).

## How this was verified

- `tests/test_verification_checks.py`, `test_verification_gate.py`,
  `test_policy_engine.py` — table-driven unit tests of every gate rule and
  every `classify_risk`/`decide_policy` branch, including the
  not-applicable typecheck/lint case and the critical-migration-with-
  dangerous-SQL case.
- Phase 10's failure-injection demos (`make demo-failure`,
  `backend/app/demos/failure_scenarios.py`) run the real gate and real
  policy engine against real disposable git repos end to end — a
  genuinely broken `add()`, a genuinely hardcoded secret, and a genuine
  migration file each produced the exact documented outcome
  (`BLOCKED_BY_VERIFICATION`, `BLOCKED_BY_VERIFICATION`,
  `PENDING_HUMAN_APPROVAL`) in this environment. See
  [docs/limitations.md](limitations.md)'s Phase 10 section for the
  verification record.
