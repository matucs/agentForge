"""Orchestration graph nodes.

Planner/Architect/Researcher (Phase 4) and Developer/Reviewer (Phase 5) call
a real LLM via the provider abstraction and persist real structured
artifacts/rows — see app/agents/. QA and Security (Phase 5) are
deterministic — real subprocess test execution and a real static scan, no
LLM. On any failure (no configured provider, git failure, etc.) a node
writes a `*_FAILED` message and re-raises; it does not fall back to
placeholder content, per spec §35.

Verification/Policy are still honest placeholders (Phase 6): one real
`agent_messages` row documenting that the step ran, with a payload that
plainly states no agent reasoning has been implemented yet, and a neutral
`*_STEP_COMPLETED` message type rather than an outcome-asserting spec §7
type (`VERIFICATION_PASSED`, ...) — that would misrepresent a decision that
was never actually made.
"""

import dataclasses

from app.agents.architect import run_architect
from app.agents.developer import apply_developer_output, run_developer
from app.agents.planner import run_planner
from app.agents.qa import run_qa
from app.agents.researcher import run_researcher
from app.agents.reviewer import run_reviewer
from app.agents.schemas import ArchitectOutput, PlannerOutput, ResearchOutput
from app.agents.security import run_security_scan
from app.db.repositories import (
    AgentMessageRepository,
    ArtifactRepository,
    ReviewRepository,
    RunRepository,
    SecurityFindingRepository,
    TestResultRepository,
)
from app.db.session import async_session_factory
from app.git_integration.git_ops import changed_files, get_diff
from app.orchestration.state import AgentState

_BASE_REF = "main"

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


def _build_retry_feedback(state: AgentState) -> str | None:
    """On a retry entry into Developer, tell it exactly what went wrong last
    time — the specific high-severity Reviewer findings and/or failed test
    output already sitting in state — rather than asking it to guess."""
    if state["iteration_count"] == 0:
        return None

    parts: list[str] = []
    high_findings = [f for f in state["review_findings"] if f.get("severity") == "high"]
    if high_findings:
        parts.append("Reviewer findings to fix:\n" + "\n".join(
            f"- [{f.get('file')}:{f.get('line')}] {f.get('finding')} — {f.get('reason')}"
            for f in high_findings
        ))
    failed_tests = [t for t in state["test_results"] if t.get("passed") is False]
    if failed_tests:
        parts.append("Failing test output:\n" + "\n".join(
            str(t.get("output", ""))[:2000] for t in failed_tests
        ))
    return "\n\n".join(parts) if parts else None


async def developer_node(state: AgentState) -> dict:
    plan = PlannerOutput.model_validate(state["plan"])
    architecture = ArchitectOutput.model_validate(state["architecture"])
    research = ResearchOutput.model_validate(state["research"])
    retry_feedback = _build_retry_feedback(state)

    try:
        output = await run_developer(
            state["requirement_text"],
            plan,
            architecture,
            research,
            retry_feedback=retry_feedback,
        )
        branch, commit_sha = apply_developer_output(
            state["repo_path"], state["task_id"], output, base_ref=_BASE_REF
        )
    except Exception as exc:
        await _emit_failure(
            state,
            from_agent="researcher",
            to_agent="developer",
            message_type="DEVELOPER_FAILED",
            error=str(exc),
        )
        raise

    async with async_session_factory() as session:
        await RunRepository(session).update(state["run_id"], branch_name=branch)
        artifact = await ArtifactRepository(session).create(
            run_id=state["run_id"],
            type="implementation",
            produced_by="developer",
            content={
                "branch": branch,
                "commit_sha": commit_sha,
                "files": [f.path for f in output.files],
                "test_files": [f.path for f in output.test_files],
                "summary": output.summary,
                "retried": retry_feedback is not None,
            },
        )
        await AgentMessageRepository(session).create(
            run_id=state["run_id"],
            task_id=state["task_id"],
            from_agent="developer",
            to_agent="reviewer",
            type="IMPLEMENTATION_READY",
            artifact_id=artifact.id,
            payload={"branch": branch, "commit_sha": commit_sha, "file_count": len(output.files)},
        )
        await session.commit()

    # Every entry into Developer — first pass or a Reviewer/QA-triggered
    # retry — counts as one iteration. Routing (routing.py) compares this
    # against the configured cap so retry loops are bounded.
    return {"iteration_count": state["iteration_count"] + 1}


async def reviewer_node(state: AgentState) -> dict:
    try:
        diff = get_diff(state["repo_path"], _BASE_REF)
        output = await run_reviewer(state["requirement_text"], diff)
    except Exception as exc:
        await _emit_failure(
            state,
            from_agent="developer",
            to_agent="reviewer",
            message_type="REVIEWER_FAILED",
            error=str(exc),
        )
        raise

    async with async_session_factory() as session:
        for finding in output.findings:
            await ReviewRepository(session).create(
                run_id=state["run_id"],
                severity=finding.severity,
                file=finding.file,
                line=finding.line,
                finding=finding.finding,
                reason=finding.reason,
                recommendation=finding.recommendation,
            )
        message_type = "REVIEW_FINDING" if output.findings else "REVIEW_APPROVED"
        await AgentMessageRepository(session).create(
            run_id=state["run_id"],
            task_id=state["task_id"],
            from_agent="reviewer",
            to_agent="qa",
            type=message_type,
            payload={"finding_count": len(output.findings)},
        )
        await session.commit()

    return {"review_findings": [f.model_dump() for f in output.findings]}


async def qa_node(state: AgentState) -> dict:
    result = run_qa(state["repo_path"])

    async with async_session_factory() as session:
        await TestResultRepository(session).create(
            run_id=state["run_id"],
            suite=result.suite,
            passed=result.passed,
            total=result.total,
            failed=result.failed,
            duration_seconds=result.duration_seconds,
            output=result.output,
        )
        message_type = "TEST_PASSED" if result.passed else "TEST_FAILED"
        await AgentMessageRepository(session).create(
            run_id=state["run_id"],
            task_id=state["task_id"],
            from_agent="qa",
            to_agent="security",
            type=message_type,
            payload={"suite": result.suite, "total": result.total, "failed": result.failed},
        )
        await session.commit()

    return {
        "test_results": [
            {
                "suite": result.suite,
                "passed": result.passed,
                "total": result.total,
                "failed": result.failed,
                "output": result.output,
            }
        ]
    }


async def security_node(state: AgentState) -> dict:
    changed = changed_files(state["repo_path"], _BASE_REF)
    drafts = run_security_scan(state["repo_path"], changed)

    async with async_session_factory() as session:
        for draft in drafts:
            await SecurityFindingRepository(session).create(
                run_id=state["run_id"],
                severity=draft.severity,
                category=draft.category,
                file=draft.file,
                detail=draft.detail,
                blocking=draft.blocking,
            )
        await AgentMessageRepository(session).create(
            run_id=state["run_id"],
            task_id=state["task_id"],
            from_agent="security",
            to_agent="verification",
            type="SECURITY_FINDING",
            payload={
                "finding_count": len(drafts),
                "blocking_count": sum(1 for d in drafts if d.blocking),
            },
        )
        await session.commit()

    return {"security_findings": [dataclasses.asdict(d) for d in drafts]}


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
