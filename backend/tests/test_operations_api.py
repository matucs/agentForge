import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ProjectRepository, RunRepository, TaskRepository


@pytest.mark.asyncio
async def test_operations_summary_is_zero_with_no_data(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/operations/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["runs_total"] == 0
    assert body["success_rate"] is None
    assert body["avg_duration_seconds"] is None
    assert body["human_approvals_total"] == 0


@pytest.mark.asyncio
async def test_operations_summary_reflects_real_run_status_counts(
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
    await db_session.flush()

    resp = await client.get("/api/operations/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["runs_total"] == 2
    assert body["runs_by_status"]["completed"] == 1
    assert body["runs_by_status"]["failed"] == 1
    assert body["success_rate"] == pytest.approx(0.5)
