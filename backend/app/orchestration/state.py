from typing import Literal, TypedDict


class AgentState(TypedDict):
    """Shared state threaded through every node in the orchestration graph.

    Node bodies in this phase are honest placeholders (see
    app/orchestration/nodes.py) — the *shape* of this state is what Phase
    4/5 agents will actually populate with real plans, findings, and
    results. Keeping the shape final now means later phases only change
    node bodies, not the graph.
    """

    run_id: str
    task_id: str
    requirement_text: str
    repo_path: str

    plan: dict | None
    architecture: dict | None
    research: dict | None

    review_findings: list[dict]
    test_results: list[dict]
    security_findings: list[dict]
    verification_result: dict | None
    final_decision: str | None

    iteration_count: int
    status: Literal["running", "completed", "failed"]
    error: str | None
