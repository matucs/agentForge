# Evaluation Harness

`app/evaluation/` (spec §14/§32) runs real tasks through the real
orchestration pipeline against disposable fixture repos — not a separate
simulated evaluation mode.

## Task format

Each YAML file under `evals/tasks/` is loaded by `app/evaluation/loader.py`
and validated against `EvalTask` (`app/evaluation/schemas.py`): `name`,
`requirement`, `expected_behavior`, `acceptance_criteria`,
`known_failure_modes`. A malformed task file is a real, visible loader
error — never silently skipped.

## Running an evaluation (`make eval` → `app/evaluation/runner.py`)

For each task: a fresh disposable git fixture repo is constructed
(`_init_fixture_repo`), a real `Project`/`Task`/`Run` row is created, and
`run_to_completion(run_id)` — the exact same entrypoint the API's
`start_run` background task uses — executes the full real graph against
it. Each run's real terminal status is recorded into an `EvaluationRun`
row (duration, cost, final status — all real, from the same `Run` row
`_run_graph` writes).

**No LLM credentials configured** → the runner prints spec §35's exact
"Integration unavailable" pattern and exits non-zero, rather than
producing a fabricated report. This is the always-tested path in CI (no
API key is ever configured there, by design) — confirmed by a real
subprocess invocation of `python -m app.evaluation.runner` in
`tests/test_evaluation.py`, asserting the exact message and exit code.

## What's honestly not measured yet

`EvaluationRun.reviewer_correct` (and the equivalent QA/Security detection-
rate fields) are left `None` rather than invented. Measuring a real
detection rate needs a task with a *known* injected bug to check the
agents' findings against — Phase 10's failure-injection demos prove the
deterministic gate catches a known-injected bug when its nodes are invoked
directly, but wiring that same known-bug signal into the eval harness's
per-run scoring (so `make eval` itself reports a detection rate across a
task suite) is a follow-up, not assumed done here.

## Frontend surface

`GET /api/evaluations` and `/api/evaluations/:id/runs` (Phase 9) expose
real aggregates computed from `EvaluationRun` rows — count, success rate,
avg duration/cost — for the dashboard's `/evaluations` page. If no
`make eval` has been run in a given environment, the page shows that
honestly (empty state), never placeholder rows.

## How this was verified

`tests/test_evaluation.py` covers both the credential-gated "unavailable"
path (a real subprocess call) and the loader's schema validation. Manually
run in this environment: `make eval` with no credentials configured
correctly printed the unavailable message and exited non-zero (see
[docs/limitations.md](limitations.md)'s Phase 8 section for the exact
verification record from when this was built).
