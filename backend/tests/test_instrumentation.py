from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.db.repositories import (
    ProjectRepository,
    RunRepository,
    TaskRepository,
    ToolCallRepository,
)
from app.db.session import async_session_factory, engine
from app.observability.instrumentation import instrument_node
from app.orchestration.state import AgentState


def _state(run_id: str, task_id: str) -> AgentState:
    return AgentState(
        run_id=run_id,
        task_id=task_id,
        requirement_text="req",
        repo_path="/tmp",
        plan=None,
        architecture=None,
        research=None,
        review_findings=[],
        test_results=[],
        security_findings=[],
        verification_result=None,
        final_decision=None,
        iteration_count=0,
        status="running",
        error=None,
    )


@pytest_asyncio.fixture
async def committed_run() -> AsyncIterator[tuple[str, str]]:
    """instrument_node writes on its own connection (async_session_factory),
    independent of any per-test transactional-rollback session — so the
    Run it references must be genuinely committed, not just flushed in a
    transaction that later rolls back (the same real-connection-visibility
    constraint documented for the `real_client` fixture)."""
    async with async_session_factory() as session:
        project = await ProjectRepository(session).create(
            name="P", repo_path="/repo", description=None
        )
        task = await TaskRepository(session).create(
            project_id=project.id, title="t", requirement_text="r"
        )
        run = await RunRepository(session).create(task_id=task.id)
        await session.commit()
        run_id, task_id = run.id, task.id

    yield run_id, task_id

    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM tool_calls WHERE run_id = :run_id"), {"run_id": run_id}
        )
        await conn.execute(text("DELETE FROM runs WHERE id = :run_id"), {"run_id": run_id})
        await conn.execute(text("DELETE FROM tasks WHERE id = :task_id"), {"task_id": task_id})


@pytest.mark.asyncio
async def test_instrument_node_records_a_successful_tool_call(
    committed_run: tuple[str, str],
) -> None:
    run_id, task_id = committed_run

    @instrument_node("test_agent")
    async def node(state: AgentState) -> dict:
        return {"ok": True}

    result = await node(_state(run_id, task_id))
    assert result == {"ok": True}

    async with async_session_factory() as session:
        calls = await ToolCallRepository(session).list_by_run(run_id)
    assert len(calls) == 1
    assert calls[0].agent == "test_agent"
    assert calls[0].succeeded is True
    assert calls[0].duration_seconds >= 0


@pytest.mark.asyncio
async def test_instrument_node_records_a_failed_tool_call_and_reraises(
    committed_run: tuple[str, str],
) -> None:
    run_id, task_id = committed_run

    @instrument_node("test_agent")
    async def node(state: AgentState) -> dict:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await node(_state(run_id, task_id))

    async with async_session_factory() as session:
        calls = await ToolCallRepository(session).list_by_run(run_id)
    assert len(calls) == 1
    assert calls[0].succeeded is False
    assert calls[0].result_summary == "boom"
