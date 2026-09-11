# ADR-003: Verification Gate Is Deterministic and Separate From LLM Review

## Status

Accepted. Rule engine implemented in Phase 6; this ADR fixes the design
constraint from the start so agent interfaces are built around it.

## Context

The Reviewer agent (an LLM) reads a diff and produces structured findings. An
LLM reviewer can miss bugs, hallucinate a false "looks good," or be
inconsistent between runs on the same input. If the Reviewer's approval were
the final gate, a single wrong LLM judgment would ship a broken change — the
project's central design principle explicitly forbids this ("Never rely on
an LLM alone to determine whether generated software is correct").

## Decision

The Reviewer's output is one more artifact in the shared state, not a
decision. A separate, independent **Verification Gate**
(`backend/app/verification/`) runs real tools — type checker, linter, unit
tests, integration tests, dependency/security scanner, schema/policy checks —
and applies fixed, code-defined rules:

```
Typecheck failed              → BLOCK
Critical security finding     → BLOCK
Required test failed          → BLOCK
Reviewer high-severity finding → BLOCK
Optional warning              → ALLOW
```

This means the QA agent's real test execution can override an incorrect
Reviewer approval: if the Reviewer says "looks good" but a unit test fails,
verification still blocks. This is deliberately tested as Failure Injection
Scenario 2 in the spec.

## Consequences

- The Verification Gate has zero dependency on any LLM provider — it must be
  able to run (and block) even if every LLM call in a run failed or was
  never made.
- The Reviewer's findings still matter: they are one of the deterministic
  gate's *inputs* (a high-severity finding is a hard rule, not a suggestion
  the gate merely considers), so LLM judgment still shapes the outcome — it
  just isn't the outcome's sole author.
- This forces a clean interface: agents write structured findings/results as
  rows (per ADR-002), and the gate reads those rows — it never re-derives
  "did tests pass" by re-parsing an LLM's prose summary of test output.
