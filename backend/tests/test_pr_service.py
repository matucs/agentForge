import httpx
import pytest

from app.config import get_settings
from app.db.repositories import RunRepository
from app.db.session import async_session_factory
from app.git_integration.pr_service import open_pull_request


def _has_real_github_credentials() -> bool:
    settings = get_settings()
    return bool(settings.github_token and settings.github_repo)


async def _create_run_with_branch(client: httpx.AsyncClient, repo_path: str) -> str:
    project = (
        await client.post(
            "/api/projects",
            json={"name": "AgentForge", "repo_path": repo_path, "description": None},
        )
    ).json()
    task = (
        await client.post(
            "/api/tasks",
            json={
                "project_id": project["id"],
                "title": "Add pagination",
                "requirement_text": "Add pagination to the users endpoint.",
            },
        )
    ).json()
    run = (await client.post("/api/runs", json={"task_id": task["id"]})).json()

    async with async_session_factory() as session:
        await RunRepository(session).update(
            run["id"], branch_name="agentforge/task-demo", status="completed"
        )
        await session.commit()

    return run["id"]


@pytest.mark.asyncio
async def test_open_pull_request_skips_cleanly_without_github_credentials(
    real_client: httpx.AsyncClient,
) -> None:
    if _has_real_github_credentials():
        pytest.skip("real GitHub credentials are configured; this tests the unconfigured path")

    run_id = await _create_run_with_branch(real_client, repo_path="/tmp/does-not-matter")

    await open_pull_request(run_id)

    events = (await real_client.get(f"/api/runs/{run_id}/events")).json()
    assert len(events) == 1
    assert events[0]["type"] == "PR_CREATION_SKIPPED"
    assert "GITHUB_TOKEN" in events[0]["payload"]["reason"]

    artifacts = (await real_client.get(f"/api/runs/{run_id}/artifacts")).json()
    assert artifacts == []  # no fabricated PR artifact


@pytest.mark.asyncio
async def test_open_pull_request_is_a_no_op_when_run_has_no_branch(
    real_client: httpx.AsyncClient,
) -> None:
    project = (
        await real_client.post(
            "/api/projects", json={"name": "P", "repo_path": "/repo", "description": None}
        )
    ).json()
    task = (
        await real_client.post(
            "/api/tasks",
            json={"project_id": project["id"], "title": "t", "requirement_text": "r"},
        )
    ).json()
    run = (await real_client.post("/api/runs", json={"task_id": task["id"]})).json()

    await open_pull_request(run["id"])  # Developer never ran — no branch_name

    events = (await real_client.get(f"/api/runs/{run['id']}/events")).json()
    assert events == []
