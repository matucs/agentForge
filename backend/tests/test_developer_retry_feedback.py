from app.orchestration.nodes import _build_retry_feedback
from app.orchestration.state import AgentState


def _state(**overrides) -> AgentState:
    base: AgentState = {
        "run_id": "run-1",
        "task_id": "task-1",
        "requirement_text": "req",
        "repo_path": "/tmp/does-not-matter",
        "plan": None,
        "architecture": None,
        "research": None,
        "review_findings": [],
        "test_results": [],
        "security_findings": [],
        "verification_result": None,
        "final_decision": None,
        "iteration_count": 0,
        "status": "running",
        "error": None,
    }
    base.update(overrides)
    return base


def test_no_feedback_on_first_entry() -> None:
    assert _build_retry_feedback(_state(iteration_count=0)) is None


def test_feedback_includes_high_severity_review_findings() -> None:
    state = _state(
        iteration_count=1,
        review_findings=[
            {"severity": "high", "file": "app.py", "line": 3, "finding": "SQL injection",
             "reason": "unsanitized input"},
            {"severity": "low", "file": "app.py", "line": 9, "finding": "nitpick",
             "reason": "style"},
        ],
    )
    feedback = _build_retry_feedback(state)
    assert feedback is not None
    assert "SQL injection" in feedback
    assert "nitpick" not in feedback  # low severity didn't trigger the retry, so omit it


def test_feedback_includes_failed_test_output() -> None:
    state = _state(
        iteration_count=1,
        test_results=[{"passed": False, "output": "AssertionError: expected 3 got 4"}],
    )
    feedback = _build_retry_feedback(state)
    assert feedback is not None
    assert "AssertionError" in feedback


def test_feedback_is_none_when_retry_happened_but_nothing_actionable_recorded() -> None:
    # iteration_count > 0 but no high findings / failed tests in state (e.g.
    # a retry triggered by something else) — don't fabricate feedback text.
    assert _build_retry_feedback(_state(iteration_count=1)) is None
