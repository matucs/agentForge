import asyncio

import httpx
import pytest


@pytest.mark.asyncio
async def test_project_task_run_lifecycle(client: httpx.AsyncClient) -> None:
    project_resp = await client.post(
        "/api/projects",
        json={"name": "AgentForge", "repo_path": "/repo", "description": "test project"},
    )
    assert project_resp.status_code == 201
    project = project_resp.json()
    assert project["name"] == "AgentForge"

    get_project_resp = await client.get(f"/api/projects/{project['id']}")
    assert get_project_resp.status_code == 200

    list_projects_resp = await client.get("/api/projects")
    assert any(p["id"] == project["id"] for p in list_projects_resp.json())

    task_resp = await client.post(
        "/api/tasks",
        json={
            "project_id": project["id"],
            "title": "Add pagination",
            "requirement_text": "Add pagination to the users endpoint.",
        },
    )
    assert task_resp.status_code == 201
    task = task_resp.json()
    assert task["status"] == "pending"

    get_task_resp = await client.get(f"/api/tasks/{task['id']}")
    assert get_task_resp.status_code == 200

    list_tasks_resp = await client.get("/api/tasks", params={"project_id": project["id"]})
    assert any(t["id"] == task["id"] for t in list_tasks_resp.json())

    run_resp = await client.post("/api/runs", json={"task_id": task["id"]})
    assert run_resp.status_code == 201
    run = run_resp.json()
    assert run["status"] == "pending"
    assert run["total_input_tokens"] == 0
    assert run["estimated_cost_usd"] == 0.0

    get_run_resp = await client.get(f"/api/runs/{run['id']}")
    assert get_run_resp.status_code == 200

    list_runs_resp = await client.get("/api/runs", params={"task_id": task["id"]})
    assert any(r["id"] == run["id"] for r in list_runs_resp.json())


@pytest.mark.asyncio
async def test_task_creation_rejects_unknown_project(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/tasks",
        json={
            "project_id": "does-not-exist",
            "title": "x",
            "requirement_text": "y",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_creation_rejects_unknown_task(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/runs", json={"task_id": "does-not-exist"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_missing_project_returns_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/projects/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_created_at_is_a_real_per_row_timestamp_not_a_frozen_default(
    real_client: httpx.AsyncClient,
) -> None:
    """Regression test: `server_default="now()"` (a bare Python string) binds
    as a literal parameter, not raw SQL — Postgres then defaults every row to
    whatever instant the column was created, forever. It must be
    `server_default=text("now()")` (see app/db/models.py TimestampMixin).
    Caught by comparing two rows created moments apart in separate,
    separately-committed requests: with the bug, every created_at in the
    table is bit-for-bit identical no matter when the row was inserted. This
    needs `real_client` (real per-request commits), not `client` — the
    latter wraps a whole test in one transaction, and Postgres's `now()` is
    constant for the life of a transaction by design, which would make this
    assertion meaningless."""
    from datetime import UTC, datetime

    first = (
        await real_client.post(
            "/api/projects", json={"name": "P1", "repo_path": "/r1", "description": None}
        )
    ).json()
    await asyncio.sleep(0.05)
    second = (
        await real_client.post(
            "/api/projects", json={"name": "P2", "repo_path": "/r2", "description": None}
        )
    ).json()

    first_created = datetime.fromisoformat(first["created_at"])
    second_created = datetime.fromisoformat(second["created_at"])

    assert second_created > first_created
    assert (datetime.now(UTC) - second_created).total_seconds() < 30


@pytest.mark.asyncio
async def test_agent_registry_is_seeded(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/agents")
    assert resp.status_code == 200
    agents = resp.json()
    names = {a["name"] for a in agents}
    assert names == {
        "planner",
        "architect",
        "researcher",
        "developer",
        "reviewer",
        "qa",
        "security",
    }
    developer = next(a for a in agents if a["name"] == "developer")
    assert "modify_files" in developer["allowed_tools"]
