# Security

This covers both the Security *agent* (one node in the pipeline) and the
security posture of AgentForge's own backend code.

## The Security agent (`app/agents/security_scan.py`)

A deterministic regex scan over real changed file content — no LLM, no
dependency/CVE database. Two pattern classes:

- **Secret-shaped strings** (`blocking=True`, `severity="high"`): AWS
  access key IDs (`AKIA[0-9A-Z]{16}`), PEM private key headers, and a
  generic `api_key|secret|token|password = "<16+ chars>"` assignment
  pattern.
- **Risky constructs** (`blocking=False`, `severity="medium"`, recorded but
  not gate-blocking): `eval(`/`exec(`, `shell=True`, `pickle.loads(`.

This is intentionally narrow — a pattern scan catches obvious, common
footguns (the class of bug Phase 10's Scenario 3 demonstrates: a real
`AKIAABCDEFGHIJKLMNOP`-shaped string committed to `config.py` is genuinely
detected and genuinely blocks the Verification Gate), not a real
`pip-audit`/`npm audit`/CVE-database dependency scan. That's an explicit
gap, not a hidden one — see [docs/limitations.md](limitations.md).

### Dogfooding: scanning this repository's own backend source

As part of Phase 12's hardening pass, `scan_files` was run against every
`.py` file under `backend/app/` in this repository. It found exactly one
match: the `AKIA...`-shaped string in
`backend/app/demos/failure_scenarios.py`'s Scenario 3 — the deliberately
committed demo secret used to prove the scanner works, not a real
credential. No other match anywhere in the backend source. This is a real
scan of real source, not an assertion.

## No secrets reach a log line

Every place a credential or webhook URL is read
(`Settings.anthropic_api_key`, `.openai_api_key`, `.github_token`,
`.n8n_webhook_url`, `.slack_webhook_url`) was checked: the value itself is
used only to build an `Authorization` header or a request URL/target — it
is never passed to a `logger.*`/`print` call. `GET /api/health` reports
only a boolean `*_configured` per provider, never the key value. This was
verified by grepping every credential-shaped attribute access in
`backend/app/` against log/print call sites and finding no overlap (part
of this phase's hardening pass, re-checked against the current source, not
assumed from an earlier phase).

## Webhook input validation

`POST /api/webhooks/n8n` (Phase 11, see
[docs/integrations.md](integrations.md)) validates its payload two ways:
Pydantic's `WebhookTaskIn` schema (a malformed/incomplete JSON body is a
real `422` from FastAPI, not silently accepted) and an explicit business
rule — exactly one of `project_id` or (`project_name` + `repo_path`) must
be present, checked in `app/api/webhooks.py` and covered by
`tests/test_webhooks_api.py`. An unknown `project_id` returns a real `404`.
It has no authentication/signature verification — a real trade-off, not
built here (see [docs/limitations.md](limitations.md)'s Phase 11
trade-offs).

## Known gaps (not hidden)

- No dependency/CVE vulnerability scanning (`pip-audit`, `npm audit`,
  Snyk/Dependabot-equivalent) — only the pattern scan above.
- No SAST beyond the pattern scan (no Semgrep/Bandit-equivalent rule set).
- No webhook signature verification on the inbound n8n endpoint.
- No secrets-manager integration — credentials are read from environment
  variables / `.env` (gitignored), the same as any 12-factor app; nothing
  more sophisticated (Vault, AWS Secrets Manager) is wired in.

These match the pattern set in [docs/limitations.md](limitations.md): named
explicitly as gaps, not glossed over, because a portfolio project claiming
security coverage it doesn't have would be worse than one that's honest
about what it actually checks.
