# Integrations: n8n / Slack (Phase 11)

This describes the two integration points that exist right now: an inbound
webhook that lets an external automation (n8n, or anything that can POST
JSON) create and start a real AgentForge run, and outbound notifications
that fire on real run-state transitions. Both follow the project's standing
rule: an unconfigured integration must report itself as unavailable or
silently no-op, never fabricate the effect of being configured.

## Inbound: `POST /api/webhooks/n8n`

Spec §22's exact endpoint. Accepts:

```json
{
  "project_id": "existing-project-id",
  "title": "Fix login bug",
  "requirement_text": "Ticket #123: users can't log in with SSO."
}
```

or, to find-or-create a project by name instead of an id:

```json
{
  "project_name": "billing-service",
  "repo_path": "/srv/repos/billing-service",
  "title": "Fix login bug",
  "requirement_text": "Ticket #123: users can't log in with SSO."
}
```

Exactly one of `project_id` or (`project_name` + `repo_path`) must be given
— otherwise the endpoint returns `422`. An unknown `project_id` returns
`404`. On success it returns `202` with:

```json
{"project_id": "...", "task_id": "...", "run_id": "...", "status": "pending"}
```

This endpoint creates the `Project`(if needed)/`Task`/`Run` rows and calls
`start_run` — the exact same repository calls and `orchestration.service`
entrypoint the dashboard's "new task" form uses (`app/api/webhooks.py`).
There is no separate "webhook demo" code path: a task created this way goes
through the real Planner → Architect → Researcher → Developer → Reviewer →
QA → Security → Verification → Policy pipeline, with real LLM calls if
credentials are configured and a real (if immediate) failure if they
aren't — the same as any other run.

### Worked example: spec §19's support-ticket flow

Spec §19 asks for "a support ticket becomes an engineering task," not a
full CRM — no ticketing UI is built here. The intended shape, using n8n (or
any workflow tool) as the glue:

1. A support ticket is created in an external system (Zendesk, Linear,
   whatever the team already uses).
2. An n8n workflow triggers on that event, extracts the ticket's title and
   body, and maps them to `title`/`requirement_text`.
3. n8n calls `POST /api/webhooks/n8n` with the repo's existing
   `project_id` (looked up once per project, cached in the n8n workflow) or
   `project_name`/`repo_path` on first use.
4. AgentForge creates and starts a real run. n8n (or a human) can poll
   `GET /api/runs/:id` — or wait for the outbound webhook below — to learn
   the outcome and post it back to the ticket.

Step 4's "post it back to the ticket" is not built here — that would be a
second n8n workflow node reacting to the outbound webhook payload below,
external to this repository.

## Outbound: run-state webhooks

`app/integrations/notifier.py` posts real `httpx` requests when:

- A run reaches a terminal status: `completed`, `blocked`,
  `stopped_by_timeout`, `stopped_by_budget`, or `failed` (wired into
  `app/orchestration/service.py`'s `_run_graph`, after the same code path
  that writes the real terminal `Run.status`).
- `policy_node` classifies a change as needing human sign-off before merge
  (wired into `app/orchestration/nodes.py`, right after the real `Approval`
  row is created).

Two settings control this, both optional (absent = no-op, logged as
`webhook_notify_skipped`, never a fabricated delivery):

| Setting | Purpose |
|---|---|
| `N8N_WEBHOOK_URL` | Receives the raw event JSON (below) via `POST`. |
| `SLACK_WEBHOOK_URL` | Receives a Slack-formatted `{"text": "..."}` message via `POST`, per Slack's incoming-webhook contract. |

Either, both, or neither can be set. A delivery failure (non-2xx response,
or a network error) is logged (`webhook_delivery_failed` /
`webhook_delivery_error`) and swallowed — a broken webhook must never fail
the actual orchestration run it's reporting on.

### `run.finished` payload (to `N8N_WEBHOOK_URL`)

```json
{
  "event": "run.finished",
  "run_id": "...",
  "task_id": "...",
  "status": "blocked",
  "final_decision": "BLOCKED_BY_VERIFICATION"
}
```

`status` is the real `Run.status` value; `final_decision` mirrors
`Run.final_decision` (`null` for timeout/budget/failure paths, since the
policy gate never ran).

### `run.approval_required` payload (to `N8N_WEBHOOK_URL`)

```json
{
  "event": "run.approval_required",
  "run_id": "...",
  "task_id": "...",
  "risk_level": "high",
  "reason": "Risk classified as 'high' — requires human sign-off before merge (spec §11)."
}
```

### Slack payloads

Both events become a single-line `{"text": "..."}` message, e.g.:

> AgentForge run `b4cbc8c0-...` finished: *blocked* (BLOCKED_BY_VERIFICATION)

> AgentForge run `29864110-...` needs human approval — risk: *high*. Risk
> classified as 'high' — requires human sign-off before merge (spec §11).

## How this was verified

- `tests/test_notifier.py`: `httpx.MockTransport` (same technique as
  `tests/test_github_client.py`) asserts the real JSON body posted to n8n,
  the real Slack text format, delivery to both when both are configured, a
  silent no-op with neither configured (assert no request is made at all),
  and that a `500` response or a connection error is swallowed rather than
  propagated.
- `tests/test_webhooks_api.py`: creates a project via the real API, POSTs
  to `/api/webhooks/n8n`, and polls `GET /api/runs/:id` until the run
  leaves `pending` — proving `start_run` was genuinely invoked, not just
  that rows were created. Also covers the find-or-create-by-name path, the
  422 validation error, and the 404 for an unknown `project_id`.
- Manually verified in this environment end to end: started the backend
  locally, POSTed a real ticket-shaped payload to `/api/webhooks/n8n` with
  no webhook URL configured, and confirmed the real run genuinely failed
  (no LLM credentials configured here) and the structured log line read
  `"webhook_notify_skipped", "reason": "no_webhook_configured"` — not
  fabricated as delivered. Then restarted the backend with
  `N8N_WEBHOOK_URL` pointed at a throwaway local HTTP server, repeated the
  request, and confirmed the exact `run.finished` JSON shown above arrived
  at that server for real.

## What is not built

- No webhook signature verification (e.g. an HMAC secret shared with n8n)
  on the inbound endpoint — anyone who can reach `/api/webhooks/n8n` can
  create and start a run. Fine for a local/portfolio deployment; a real
  deployment behind the public internet would need this.
- No retry/backoff on outbound delivery — a failed webhook is logged once
  and dropped, not queued for retry.
- No webhook-back-from-GitHub handling (PR merged/closed) — only PR
  *creation* exists (Phase 7); this is unrelated to n8n/Slack but is the
  other "webhook" gap worth naming here for completeness.
