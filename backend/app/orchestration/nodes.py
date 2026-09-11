"""Orchestration graph nodes.

Every node here is an honest placeholder: it writes one real
`agent_messages` row documenting that the step ran, with a payload that
plainly states no agent reasoning has been implemented yet. Nothing here
calls an LLM or invents a plan/finding/result — that lands in Phase 4/5,
which will replace these bodies without changing the graph shape, state
schema, or routing.

Message `type` values here are deliberately neutral (`*_STEP_COMPLETED`),
not the outcome-asserting types from spec §7 (`TEST_PASSED`,
`REVIEW_APPROVED`, `VERIFICATION_PASSED`, ...). Emitting an "approved" or
"passed" message before any real review/test/verification ran would be
exactly the fabricated status this project forbids (spec §35). Phase 4/6
nodes emit the real spec §7 types once they compute a real outcome.
"""

from app.db.repositories import AgentMessageRepository
from app.db.session import async_session_factory
from app.orchestration.state import AgentState

NOT_IMPLEMENTED_NOTE = "Agent reasoning not implemented yet (see roadmap Phase 4/5)."


async def _emit(
    state: AgentState,
    *,
    from_agent: str,
    to_agent: str,
    message_type: str,
) -> None:
    async with async_session_factory() as session:
        await AgentMessageRepository(session).create(
            run_id=state["run_id"],
            task_id=state["task_id"],
            from_agent=from_agent,
            to_agent=to_agent,
            type=message_type,
            payload={"implemented": False, "note": NOT_IMPLEMENTED_NOTE},
        )
        await session.commit()


async def planner_node(state: AgentState) -> dict:
    await _emit(
        state, from_agent="orchestrator", to_agent="planner", message_type="PLANNER_STEP_COMPLETED"
    )
    return {"plan": {"implemented": False}}


async def architect_node(state: AgentState) -> dict:
    await _emit(
        state,
        from_agent="planner",
        to_agent="architect",
        message_type="ARCHITECT_STEP_COMPLETED",
    )
    return {"architecture": {"implemented": False}}


async def researcher_node(state: AgentState) -> dict:
    await _emit(
        state,
        from_agent="architect",
        to_agent="researcher",
        message_type="RESEARCHER_STEP_COMPLETED",
    )
    return {"research": {"implemented": False}}


async def developer_node(state: AgentState) -> dict:
    await _emit(
        state,
        from_agent="researcher",
        to_agent="developer",
        message_type="DEVELOPER_STEP_COMPLETED",
    )
    # Every entry into Developer — first pass or a Reviewer/QA-triggered
    # retry — counts as one iteration. Routing (routing.py) compares this
    # against the configured cap so retry loops are bounded.
    return {"iteration_count": state["iteration_count"] + 1}


async def reviewer_node(state: AgentState) -> dict:
    await _emit(
        state, from_agent="developer", to_agent="reviewer", message_type="REVIEWER_STEP_COMPLETED"
    )
    return {"review_findings": []}


async def qa_node(state: AgentState) -> dict:
    await _emit(state, from_agent="reviewer", to_agent="qa", message_type="QA_STEP_COMPLETED")
    return {"test_results": []}


async def security_node(state: AgentState) -> dict:
    await _emit(
        state, from_agent="qa", to_agent="security", message_type="SECURITY_STEP_COMPLETED"
    )
    return {"security_findings": []}


async def verification_node(state: AgentState) -> dict:
    await _emit(
        state,
        from_agent="security",
        to_agent="verification",
        message_type="VERIFICATION_STEP_COMPLETED",
    )
    return {"verification_result": {"implemented": False}}


async def policy_node(state: AgentState) -> dict:
    # Not "HUMAN_APPROVAL_REQUIRED" — no Approval row is created and nothing
    # actually pauses here yet. The real risk-based policy engine (spec
    # §11/ADR-004) is Phase 6; claiming an approval gate exists before one
    # does would be exactly the kind of fake status this project forbids.
    await _emit(
        state,
        from_agent="verification",
        to_agent="policy",
        message_type="POLICY_STEP_COMPLETED",
    )
    return {"final_decision": None, "status": "completed"}
