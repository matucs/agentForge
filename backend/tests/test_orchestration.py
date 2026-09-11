import asyncio

import httpx
import pytest

from app.config import get_settings


async def _create_project_task_run(client: httpx.AsyncClient) -> tuple[str, str, str]:
    project = (
        await client.post(
            "/api/projects",
            json={"name": "AgentForge", "repo_path": "/repo", "description": None},
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
    return project["id"], task["id"], run["id"]


async def _poll_until_terminal(
    client: httpx.AsyncClient, run_id: str, *, timeout: float = 5.0
) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        run = (await client.get(f"/api/runs/{run_id}")).json()
        if run["status"] not in {"pending", "running"}:
            return run
        await asyncio.sleep(0.05)
    raise AssertionError(f"run {run_id} did not reach a terminal state within {timeout}s")


@pytest.mark.asyncio
async def test_run_executes_through_stub_pipeline(real_client: httpx.AsyncClient) -> None:
    _, _, run_id = await _create_project_task_run(real_client)

    start_resp = await real_client.post(f"/api/runs/{run_id}/start")
    assert start_resp.status_code == 202

    run = await _poll_until_terminal(real_client, run_id)
    assert run["status"] == "completed"
    assert run["iteration_count"] == 1  # developer runs exactly once: no stub finding retries it

    events = (await real_client.get(f"/api/runs/{run_id}/events")).json()
    event_types = [e["type"] for e in events]
    assert event_types == [
        "PLANNER_STEP_COMPLETED",
        "ARCHITECT_STEP_COMPLETED",
        "RESEARCHER_STEP_COMPLETED",
        "DEVELOPER_STEP_COMPLETED",
        "REVIEWER_STEP_COMPLETED",
        "QA_STEP_COMPLETED",
        "SECURITY_STEP_COMPLETED",
        "VERIFICATION_STEP_COMPLETED",
        "POLICY_STEP_COMPLETED",
    ]
    assert all(e["payload"]["implemented"] is False for e in events)


@pytest.mark.asyncio
async def test_starting_a_run_twice_is_rejected(real_client: httpx.AsyncClient) -> None:
    _, _, run_id = await _create_project_task_run(real_client)

    first = await real_client.post(f"/api/runs/{run_id}/start")
    assert first.status_code == 202

    second = await real_client.post(f"/api/runs/{run_id}/start")
    assert second.status_code == 409

    await _poll_until_terminal(real_client, run_id)


@pytest.mark.asyncio
async def test_starting_unknown_run_returns_404(real_client: httpx.AsyncClient) -> None:
    resp = await real_client.post("/api/runs/does-not-exist/start")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_stops_an_in_flight_run(
    real_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _SlowGraph:
        def compile(self, **_kwargs) -> "_SlowGraph":
            return self

        async def ainvoke(self, state: dict, config: dict) -> dict:
            await asyncio.sleep(10)
            return state

    monkeypatch.setattr(
        "app.orchestration.service.build_graph", lambda: _SlowGraph()
    )

    _, _, run_id = await _create_project_task_run(real_client)
    await real_client.post(f"/api/runs/{run_id}/start")
    await asyncio.sleep(0.1)  # let the background task actually start

    cancel_resp = await real_client.post(f"/api/runs/{run_id}/cancel")
    assert cancel_resp.status_code == 200

    run = await _poll_until_terminal(real_client, run_id, timeout=2.0)
    assert run["status"] == "cancelled"


@pytest.mark.asyncio
async def test_run_stops_by_timeout_when_it_exceeds_max_workflow_seconds(
    real_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _SlowGraph:
        def compile(self, **_kwargs) -> "_SlowGraph":
            return self

        async def ainvoke(self, state: dict, config: dict) -> dict:
            await asyncio.sleep(10)
            return state

    monkeypatch.setattr(
        "app.orchestration.service.build_graph", lambda: _SlowGraph()
    )
    monkeypatch.setenv("MAX_WORKFLOW_SECONDS", "1")
    get_settings.cache_clear()

    _, _, run_id = await _create_project_task_run(real_client)
    await real_client.post(f"/api/runs/{run_id}/start")

    run = await _poll_until_terminal(real_client, run_id, timeout=5.0)
    assert run["status"] == "stopped_by_timeout"

    get_settings.cache_clear()
