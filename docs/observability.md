# Observability

Three real signals, all sourced from the same instrumentation point
(`app/observability/instrumentation.py`'s `instrument_node`, wrapping every
orchestration node) or from live database queries at request time — never
an estimate or a fabricated number (spec §35).

## Structured logging (`app/observability/logging.py`)

`structlog`, JSON-rendered. Every node execution logs one `{agent}_node`
event with `run_id`, `task_id`, `agent`, `duration` (real elapsed seconds),
and `status` (`succeeded`/`failed`) — success or failure, in a `finally`
block, so a raised exception is still logged before it propagates.
`run_started`/`run_finished` bracket the whole run in
`app/orchestration/service.py`. Webhook delivery attempts log
`webhook_delivered`/`webhook_delivery_failed`/`webhook_delivery_error`/
`webhook_notify_skipped` (Phase 11).

A structlog gotcha bit this project directly: passing `event=` as an
explicit keyword when structlog's bound logger already consumes the first
positional argument as `event` raises `TypeError: got multiple values for
argument 'event'` — and because it happened inside instrumentation's
`finally` block, it silently replaced the *real* underlying exception,
hanging every run at `status="running"` forever (Phase 8's most severe bug,
and recurred narrowly in Phase 11's notifier before being caught the same
way — see [docs/limitations.md](limitations.md)'s bug log for both). The
fix in both places: never pass `event=` as a keyword; use `event_name=` or
similar for anything that isn't the log call's own event-name argument.

## Tracing (`app/observability/tracing.py`)

Real OpenTelemetry spans: one per node (via `instrument_node`) plus one
wrapping the whole run (`_tracer.start_as_current_span("run")` in
`service.py`). Exports to a real OTLP endpoint if
`OTEL_EXPORTER_OTLP_ENDPOINT` is configured; otherwise falls back to a
Console/Simple span exporter (so tracing is always real spans, just to a
different sink) — never a LangSmith/Braintrust SDK integration (an
explicit ADR-covered trade-off from Phase 8, not built).

## Metrics (`app/observability/metrics.py`, `GET /api/metrics`)

Prometheus-format text (`prometheus_client`), but every `Gauge` is
`.set()` fresh from a real SQL query against `Run`/`ToolCall`/
`VerificationResult`/`Approval` at request time — nothing is a stale
in-memory counter that could drift from the database. Includes
`agentforge_runs_total`, `agentforge_runs_by_status{status=...}`,
`agentforge_verification_failures_total`, `agentforge_human_approvals_total`,
and real summed `agentforge_llm_input_tokens_total`/`_output_tokens_total`
from every run's actual provider usage. `GET /api/operations/summary`
(Phase 9) computes the same real aggregates reshaped to JSON for the
dashboard's `/operations` page — same queries, no invented second source
of truth. Nothing currently scrapes `/api/metrics` in this repo's Docker
Compose setup (no Grafana/Prometheus server wired in) — the endpoint is
real and scrape-able, just not connected to a dashboard here.

## Per-node tool-call records

Beyond logs/traces/metrics, `instrument_node` writes one real `ToolCall`
row per node execution (`agent`, `tool_name`, `duration_seconds`,
`succeeded`, `result_summary` on failure) — this is what backs
`GET /api/runs/:id/tool-calls` and the dashboard's per-run trace view.

## How this was verified

`tests/test_instrumentation.py` and `tests/test_metrics.py` assert real
span/log/`ToolCall` creation and real metric values against a
`real_client`-committed set of runs (not a mocked DB). Manually confirmed
in earlier phases: live `curl` against `/api/metrics` compared byte-for-
byte against direct SQL counts; the OTel Console exporter's JSON span
output visible in this session's own `make demo-failure` run (see the
raw console output captured during Phase 10's verification).
