from app.orchestration.routing import route_after_qa, route_after_reviewer
from app.orchestration.state import AgentState


def _state(**overrides) -> AgentState:
    base: AgentState = {
        "run_id": "run-1",
        "task_id": "task-1",
        "requirement_text": "req",
        "repo_path": "/tmp/does-not-matter-for-routing",
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


def test_route_after_reviewer_passes_through_with_no_findings() -> None:
    assert route_after_reviewer(_state()) == "qa"


def test_route_after_reviewer_retries_developer_on_high_severity_finding() -> None:
    state = _state(review_findings=[{"severity": "high", "finding": "missing auth check"}])
    assert route_after_reviewer(state) == "developer"


def test_route_after_reviewer_ignores_low_severity_findings() -> None:
    state = _state(review_findings=[{"severity": "low", "finding": "style nit"}])
    assert route_after_reviewer(state) == "qa"


def test_route_after_reviewer_forces_forward_once_iteration_cap_reached(monkeypatch) -> None:
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MAX_AGENT_ITERATIONS", "2")
    state = _state(
        review_findings=[{"severity": "high", "finding": "still broken"}], iteration_count=2
    )
    assert route_after_reviewer(state) == "qa"
    get_settings.cache_clear()


def test_route_after_qa_passes_through_when_all_tests_pass() -> None:
    state = _state(test_results=[{"passed": True}, {"passed": True}])
    assert route_after_qa(state) == "security"


def test_route_after_qa_retries_developer_on_failed_test() -> None:
    state = _state(test_results=[{"passed": True}, {"passed": False}])
    assert route_after_qa(state) == "developer"


def test_route_after_qa_forces_forward_once_iteration_cap_reached(monkeypatch) -> None:
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MAX_AGENT_ITERATIONS", "1")
    state = _state(test_results=[{"passed": False}], iteration_count=1)
    assert route_after_qa(state) == "security"
    get_settings.cache_clear()
