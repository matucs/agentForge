import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import (
    ApprovalRepository,
    ProjectRepository,
    RunRepository,
    TaskRepository,
    ToolCallRepository,
    VerificationResultRepository,
)


def _metric_value(text: str, metric_line_prefix: str) -> float | None:
    for line in text.splitlines():
        if line.startswith(metric_line_prefix):
            return float(line.rsplit(" ", 1)[1])
    return None


@pytest.mark.asyncio
async def test_metrics_reflects_real_seeded_rows(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await ProjectRepository(db_session).create(
        name="P", repo_path="/repo", description=None
    )
    task = await TaskRepository(db_session).create(
        project_id=project.id, title="t", requirement_text="r"
    )
    run_repo = RunRepository(db_session)
    run1 = await run_repo.create(task_id=task.id)
    run2 = await run_repo.create(task_id=task.id)
    await run_repo.update(run1.id, status="completed")
    await run_repo.update(run2.id, status="failed")
    await run_repo.increment_usage(run1.id, input_tokens=100, output_tokens=40, cost_usd=0.05)

    await VerificationResultRepository(db_session).create(
        run_id=run1.id, gate="unit_tests", passed=False, detail={}
    )
    await ApprovalRepository(db_session).create(
        run_id=run1.id, action="merge", risk_level="high"
    )
    await ToolCallRepository(db_session).create(
        run_id=run1.id, agent="planner", tool_name="planner_node",
        duration_seconds=1.5, succeeded=True,
    )
    await ToolCallRepository(db_session).create(
        run_id=run1.id, agent="planner", tool_name="planner_node",
        duration_seconds=2.5, succeeded=False,
    )
    await db_session.flush()

    resp = await client.get("/api/metrics")
    assert resp.status_code == 200
    body = resp.text

    assert _metric_value(body, "agentforge_runs_total") == 2.0
    assert (
        _metric_value(body, 'agentforge_runs_by_status{status="completed"}') == 1.0
    )
    assert _metric_value(body, 'agentforge_runs_by_status{status="failed"}') == 1.0
    assert _metric_value(body, "agentforge_verification_failures_total") == 1.0
    assert _metric_value(body, "agentforge_human_approvals_total") == 1.0
    assert _metric_value(body, "agentforge_llm_input_tokens_total") == 100.0
    assert _metric_value(body, "agentforge_llm_output_tokens_total") == 40.0
    assert _metric_value(body, "agentforge_estimated_llm_cost_usd_total") == 0.05
    assert (
        _metric_value(body, 'agentforge_agent_duration_seconds_avg{agent="planner"}') == 2.0
    )
    assert _metric_value(body, 'agentforge_agent_errors_total{agent="planner"}') == 1.0


@pytest.mark.asyncio
async def test_metrics_is_zero_with_no_data(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/metrics")
    assert resp.status_code == 200
    assert _metric_value(resp.text, "agentforge_runs_total") == 0.0
