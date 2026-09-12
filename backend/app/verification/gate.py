"""The deterministic Verification Gate (spec §10). This is the piece ADR-003
exists to justify: no LLM call anywhere in this module. It reads results
already produced by real subprocess execution (checks.py, qa.py) and real
persisted rows (Reviewer/Security findings), and applies fixed rules — the
same inputs always produce the same PASS/FAIL, independent of any model.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.verification.checks import CheckResult

Gate = Literal["typecheck", "lint", "unit_tests", "security", "reviewer"]


@dataclass(frozen=True)
class GateCheck:
    gate: Gate
    passed: bool
    detail: str


@dataclass(frozen=True)
class GateResult:
    checks: list[GateCheck]
    overall_passed: bool
    blocking_reasons: list[str] = field(default_factory=list)


def evaluate_gate(
    *,
    reviewer_findings: list[dict],
    test_results: list[dict],
    security_findings: list[dict],
    typecheck_result: CheckResult,
    lint_result: CheckResult,
) -> GateResult:
    checks: list[GateCheck] = []
    blocking_reasons: list[str] = []

    # Typecheck failed -> BLOCK. Not applicable (no type checker for this
    # project) is not a failure.
    typecheck_ok = (not typecheck_result.applicable) or typecheck_result.passed
    checks.append(
        GateCheck(
            gate="typecheck",
            passed=typecheck_ok,
            detail=typecheck_result.output if typecheck_result.applicable else "not applicable",
        )
    )
    if not typecheck_ok:
        blocking_reasons.append("Type check failed")

    # Lint is informational only per spec §10's rule table ("Optional
    # warning -> ALLOW") — it is recorded, never blocking.
    checks.append(
        GateCheck(
            gate="lint",
            passed=(not lint_result.applicable) or lint_result.passed,
            detail=lint_result.output if lint_result.applicable else "not applicable",
        )
    )

    # Required test failed -> BLOCK.
    failed_tests = [t for t in test_results if t.get("passed") is False]
    unit_tests_ok = len(failed_tests) == 0
    checks.append(
        GateCheck(
            gate="unit_tests",
            passed=unit_tests_ok,
            detail=f"{len(failed_tests)} failing test suite(s)" if failed_tests else "all passed",
        )
    )
    if not unit_tests_ok:
        blocking_reasons.append("Required test failed")

    # Critical/blocking security finding -> BLOCK.
    blocking_findings = [f for f in security_findings if f.get("blocking")]
    security_ok = len(blocking_findings) == 0
    checks.append(
        GateCheck(
            gate="security",
            passed=security_ok,
            detail=(
                f"{len(blocking_findings)} blocking finding(s)"
                if blocking_findings
                else "no blocking findings"
            ),
        )
    )
    if not security_ok:
        blocking_reasons.append("Critical security finding")

    # Reviewer high-severity finding -> BLOCK.
    high_findings = [f for f in reviewer_findings if f.get("severity") == "high"]
    reviewer_ok = len(high_findings) == 0
    checks.append(
        GateCheck(
            gate="reviewer",
            passed=reviewer_ok,
            detail=(
                f"{len(high_findings)} high-severity finding(s)"
                if high_findings
                else "no high-severity findings"
            ),
        )
    )
    if not reviewer_ok:
        blocking_reasons.append("Reviewer high-severity finding")

    return GateResult(
        checks=checks,
        overall_passed=len(blocking_reasons) == 0,
        blocking_reasons=blocking_reasons,
    )
