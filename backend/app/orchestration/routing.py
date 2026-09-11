from typing import Literal

from app.config import get_settings
from app.orchestration.state import AgentState


def _has_high_severity_finding(findings: list[dict]) -> bool:
    return any(f.get("severity") == "high" for f in findings)


def _has_failed_test(test_results: list[dict]) -> bool:
    return any(t.get("passed") is False for t in test_results)


def _under_iteration_cap(state: AgentState) -> bool:
    return state["iteration_count"] < get_settings().max_agent_iterations


def route_after_reviewer(state: AgentState) -> Literal["developer", "qa"]:
    """A high-severity Reviewer finding sends the change back to the
    Developer — unless the iteration cap is already reached, in which case
    we force forward progress rather than loop forever (spec §6: "Limit
    retry loops. Do not create infinite agent loops.").

    `iteration_count` is incremented by the Developer node itself on every
    entry (see nodes.py), so comparing it here against the configured cap is
    a plain, side-effect-free read.
    """
    if _has_high_severity_finding(state["review_findings"]) and _under_iteration_cap(state):
        return "developer"
    return "qa"


def route_after_qa(state: AgentState) -> Literal["developer", "security"]:
    """A failed test sends the change back to the Developer, subject to the
    same iteration cap. This is the path that lets real test execution
    override an incorrect Reviewer approval (spec §13, Scenario 2) once
    Phase 4/5 nodes produce real findings/results."""
    if _has_failed_test(state["test_results"]) and _under_iteration_cap(state):
        return "developer"
    return "security"
