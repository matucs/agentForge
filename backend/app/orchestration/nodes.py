"""Orchestration graph nodes.

Planner/Architect/Researcher (Phase 4) call a real LLM via the provider
abstraction and persist real structured artifacts — see app/agents/. On any
failure (no configured provider, or output that never parses as valid
structured JSON after a retry) the node writes a failure message and
re-raises; it does not fall back to placeholder content, per spec §35.

Developer/Reviewer/QA/Security/Verification/Policy are still honest
placeholders (Phase 5/6): one real `agent_messages` row documenting that the
step ran, with a payload that plainly states no agent reasoning has been
implemented yet, and neutral `*_STEP_COMPLETED` message types rather than
the outcome-asserting spec §7 types (`TEST_PASSED`, `REVIEW_APPROVED`, ...)
— those would misrepresent a decision that was never actually made.
"""

from app.agents.architect import run_architect
from app.agents.planner import run_planner
from app.agents.researcher import run_researcher
from app.agents.schemas import ArchitectOutput, PlannerOutput
from app.db.repositories import AgentMessageRepository, ArtifactRepository
from app.db.session import async_session_factory
from app.orchestration.state import AgentState

NOT_IMPLEMENTED_NOTE = "Agent reasoning not implemented yet (see roadmap Phase 5/6)."


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


async def _persist_artifact_and_message(
    state: AgentState,
    *,
    artifact_type: str,
    produced_by: str,
    to_agent: str,
    message_type: str,
    content: dict,
    message_payload: dict,
) -> None:
    async with async_session_factory() as session:
        artifact = await ArtifactRepository(session).create(
            run_id=state["run_id"], type=artifact_type, produced_by=produced_by, content=content
        )
        await AgentMessageRepository(session).create(
            run_id=state["run_id"],
            task_id=state["task_id"],
            from_agent=produced_by,
            to_agent=to_agent,
            type=message_type,
            artifact_id=artifact.id,
            payload=message_payload,
        )
        await session.commit()


async def _emit_failure(
    state: AgentState, *, from_agent: str, to_agent: str, message_type: str, error: str
) -> None:
    async with async_session_factory() as session:
        await AgentMessageRepository(session).create(
            run_id=state["run_id"],
            task_id=state["task_id"],
            from_agent=from_agent,
            to_agent=to_agent,
            type=message_type,
            payload={"implemented": True, "error": error},
        )
        await session.commit()


async def planner_node(state: AgentState) -> dict:
    try:
        plan = await run_planner(state["requirement_text"])
    except Exception as exc:
        await _emit_failure(
            state,
            from_agent="orchestrator",
            to_agent="planner",
            message_type="PLANNER_FAILED",
            error=str(exc),
        )
        raise

    await _persist_artifact_and_message(
        state,
        artifact_type="plan",
        produced_by="planner",
        to_agent="architect",
        message_type="PLAN_CREATED",
        content=plan.model_dump(),
        message_payload={
            "subtask_count": len(plan.subtasks),
            "risk_count": len(plan.risks),
        },
    )
    return {"plan": plan.model_dump()}


async def architect_node(state: AgentState) -> dict:
    plan = PlannerOutput.model_validate(state["plan"])
    try:
        architecture = await run_architect(state["requirement_text"], plan)
    except Exception as exc:
        await _emit_failure(
            state,
            from_agent="planner",
            to_agent="architect",
            message_type="ARCHITECT_FAILED",
            error=str(exc),
        )
        raise

    await _persist_artifact_and_message(
        state,
        artifact_type="architecture",
        produced_by="architect",
        to_agent="researcher",
        message_type="ARCHITECTURE_PROPOSED",
        content=architecture.model_dump(),
        message_payload={
            "component_count": len(architecture.proposed_components),
            "challenge_count": len(architecture.challenges),
        },
    )
    return {"architecture": architecture.model_dump()}


async def researcher_node(state: AgentState) -> dict:
    plan = PlannerOutput.model_validate(state["plan"])
    architecture = ArchitectOutput.model_validate(state["architecture"])
    try:
        research, discarded = await run_researcher(
            state["requirement_text"], state["repo_path"], plan, architecture
        )
    except Exception as exc:
        await _emit_failure(
            state,
            from_agent="architect",
            to_agent="researcher",
            message_type="RESEARCHER_FAILED",
            error=str(exc),
        )
        raise

    await _persist_artifact_and_message(
        state,
        artifact_type="research",
        produced_by="researcher",
        to_agent="developer",
        message_type="RESEARCH_RESULT",
        content={
            "findings": [f.model_dump() for f in research.findings],
            "discarded_ungrounded_findings": [f.model_dump() for f in discarded],
        },
        message_payload={
            "finding_count": len(research.findings),
            "discarded_count": len(discarded),
        },
    )
    return {"research": research.model_dump()}


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
