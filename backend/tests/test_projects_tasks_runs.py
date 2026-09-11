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
