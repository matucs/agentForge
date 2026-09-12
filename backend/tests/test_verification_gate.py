from app.verification.checks import CheckResult
from app.verification.gate import evaluate_gate

_NOT_APPLICABLE_TYPECHECK = CheckResult(tool="none", applicable=False, passed=True, output="")
_PASSING_TYPECHECK = CheckResult(tool="mypy", applicable=True, passed=True, output="Success")
_FAILING_TYPECHECK = CheckResult(tool="mypy", applicable=True, passed=False, output="error: bad")
_NOT_APPLICABLE_LINT = CheckResult(tool="none", applicable=False, passed=True, output="")
_FAILING_LINT = CheckResult(tool="ruff", applicable=True, passed=False, output="1 issue found")


def _clean_gate(**overrides):
    defaults = dict(
        reviewer_findings=[],
        test_results=[],
        security_findings=[],
        typecheck_result=_NOT_APPLICABLE_TYPECHECK,
        lint_result=_NOT_APPLICABLE_LINT,
    )
    defaults.update(overrides)
    return evaluate_gate(**defaults)


def test_all_clean_passes() -> None:
    result = _clean_gate()
    assert result.overall_passed is True
    assert result.blocking_reasons == []


def test_typecheck_failure_blocks() -> None:
    result = _clean_gate(typecheck_result=_FAILING_TYPECHECK)
    assert result.overall_passed is False
    assert "Type check failed" in result.blocking_reasons


def test_lint_failure_does_not_block() -> None:
    # Spec §10's rule table only lists Typecheck/Security/Tests/Reviewer as
    # BLOCK conditions — lint is "Optional warning -> ALLOW".
    result = _clean_gate(lint_result=_FAILING_LINT)
    assert result.overall_passed is True
    assert result.blocking_reasons == []
    lint_check = next(c for c in result.checks if c.gate == "lint")
    assert lint_check.passed is False  # recorded, just not blocking


def test_failed_test_blocks() -> None:
    result = _clean_gate(test_results=[{"passed": False, "output": "boom"}])
    assert result.overall_passed is False
    assert "Required test failed" in result.blocking_reasons


def test_blocking_security_finding_blocks() -> None:
    result = _clean_gate(
        security_findings=[{"severity": "high", "blocking": True, "category": "aws_access_key"}]
    )
    assert result.overall_passed is False
    assert "Critical security finding" in result.blocking_reasons


def test_non_blocking_security_finding_does_not_block() -> None:
    result = _clean_gate(
        security_findings=[{"severity": "medium", "blocking": False, "category": "eval_usage"}]
    )
    assert result.overall_passed is True


def test_high_severity_reviewer_finding_blocks() -> None:
    result = _clean_gate(reviewer_findings=[{"severity": "high", "file": "a.py"}])
    assert result.overall_passed is False
    assert "Reviewer high-severity finding" in result.blocking_reasons


def test_low_severity_reviewer_finding_does_not_block() -> None:
    result = _clean_gate(reviewer_findings=[{"severity": "low", "file": "a.py"}])
    assert result.overall_passed is True


def test_multiple_block_reasons_are_all_reported() -> None:
    result = _clean_gate(
        typecheck_result=_FAILING_TYPECHECK,
        test_results=[{"passed": False}],
    )
    assert result.overall_passed is False
    assert len(result.blocking_reasons) == 2
