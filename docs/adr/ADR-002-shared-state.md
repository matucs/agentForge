# ADR-002: Postgres for Shared Project State (Not In-Memory, Not Kafka)

## Status

Accepted. Schema implemented in Phase 1 (`backend/app/db/models.py`).

## Context

Agents need to share structured artifacts (plans, architecture decisions,
research findings, diffs, review findings, test results, security findings,
verification results, approvals) with each other and with the API/UI layer.
This state must survive a backend restart mid-run and must be queryable by
the operations dashboard (e.g. "show me every high-severity Reviewer finding
across the last 100 runs").

## Options considered

1. **In-memory only (a Python dict per run).** Fast, but a restart loses
   every in-flight run, and there is no way to query across runs for the
   evaluation/operations dashboard. Explicitly ruled out by the spec ("Do not
   rely exclusively on in-memory state").
2. **Kafka (or another event log) as the system of record.** Excellent for
   very high-throughput, many-consumer event streaming, but for this
   project's scale (single-tenant, tens of concurrent runs) it adds an
   operational dependency (broker, topic/partition management) that buys
   nothing an application database doesn't already give us, and makes
   relational queries ("all reviews with severity=high") awkward — you'd
   still need a queryable projection, i.e. Postgres, downstream of Kafka.
3. **PostgreSQL**, with each entity type as its own normalized table (per
   spec §23), plus Redis for ephemeral pub/sub (live run event streaming to
   the UI) and short-lived locks.

## Decision

Postgres is the system of record for everything that must survive a restart
or be queried relationally: projects, tasks, runs, agent_messages, artifacts,
decisions, reviews, test_results, security_findings, verification_results,
approvals, evaluations, evaluation_runs, tool_calls, audit_events. Redis is
used only for transient concerns — live event pub/sub to connected UI
clients and short-lived coordination — never as the durable record.

## Consequences

- Every agent message and artifact is a row, not a blob buried in a run's
  JSON state, so the dashboard's `/runs/:id` trace and cross-run analytics
  (`/evaluations`, `/operations`) are plain SQL queries.
- We accept Postgres write load proportional to agent chattiness (one row per
  message/tool call). At this project's scale this is a non-issue; it would
  need revisiting only at a throughput this MVP does not target.
- If a Redis pub/sub message is dropped (e.g. a WebSocket subscription
  established after the event was published), the UI can always fall back to
  polling Postgres for the authoritative state — Redis data loss cannot lose
  engineering history, only delay a live update.
