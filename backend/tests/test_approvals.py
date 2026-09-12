import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ApprovalRepository, ProjectRepository, RunRepository, TaskRepository


async def _create_pending_approval(session: AsyncSession) -> tuple[str, str]:
    """Creates a Run directly (no LLM/orchestration needed) already in
    `awaiting_approval`, with a real pending Approval row — exactly the
    state policy_node leaves behind for a high-risk change."""
    project = await ProjectRepository(session).create(
        name="Demo", repo_path="/repo", description=None
    )
    task = await TaskRepository(session).create(
        project_id=project.id, title="Add migration", requirement_text="Add a DB migration"
    )
    run = await RunRepository(session).create(task_id=task.id)
    await RunRepository(session).update(run.id, status="awaiting_approval")
    approval = await ApprovalRepository(session).create(
        run_id=run.id,
        action=f"Merge changes for task {task.id}",
        risk_level="high",
        requested_reason="Risk classified as 'high'",
    )
    await session.flush()
    return run.id, approval.id


@pytest.mark.asyncio
async def test_list_approvals_shows_pending_entry(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    _, approval_id = await _create_pending_approval(db_session)

    resp = await client.get("/api/approvals", params={"status": "pending"})
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert approval_id in ids


@pytest.mark.asyncio
async def test_approve_marks_approval_approved_and_run_completed(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    run_id, approval_id = await _create_pending_approval(db_session)

    resp = await client.post(f"/api/approvals/{approval_id}/approve", json={"decided_by": "alice"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["decided_by"] == "alice"
    assert body["decided_at"] is not None

    run_resp = await client.get(f"/api/runs/{run_id}")
    assert run_resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_reject_marks_approval_rejected_and_run_rejected(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    run_id, approval_id = await _create_pending_approval(db_session)

    resp = await client.post(f"/api/approvals/{approval_id}/reject", json={"decided_by": "bob"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    run_resp = await client.get(f"/api/runs/{run_id}")
    assert run_resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_approving_twice_returns_409(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    _, approval_id = await _create_pending_approval(db_session)

    first = await client.post(f"/api/approvals/{approval_id}/approve", json={})
    assert first.status_code == 200

    second = await client.post(f"/api/approvals/{approval_id}/approve", json={})
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_approving_unknown_approval_returns_404(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/approvals/does-not-exist/approve", json={})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approval_decision_defaults_decided_by_to_operator(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    _, approval_id = await _create_pending_approval(db_session)
    resp = await client.post(f"/api/approvals/{approval_id}/approve", json={})
    assert resp.json()["decided_by"] == "operator"
