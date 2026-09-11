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


def _has_real_llm_credentials() -> bool:
    settings = get_settings()
    return bool(settings.anthropic_api_key or settings.openai_api_key)


@pytest.mark.asyncio
async def test_run_fails_cleanly_when_no_llm_provider_configured(
    real_client: httpx.AsyncClient,
) -> None:
    """With Phase 4, Planner makes a real LLM call. Without credentials this
    must be a real, visible failure (spec §35: no fake AI) — never a
    placeholder plan and never a silently "completed" run."""
    if _has_real_llm_credentials():
        pytest.skip("a real LLM provider is configured; this tests the unconfigured path")

    _, _, run_id = await _create_project_task_run(real_client)

    start_resp = await real_client.post(f"/api/runs/{run_id}/start")
    assert start_resp.status_code == 202

    run = await _poll_until_terminal(real_client, run_id)
    assert run["status"] == "failed"

    events = (await real_client.get(f"/api/runs/{run_id}/events")).json()
    assert len(events) == 1
    assert events[0]["type"] == "PLANNER_FAILED"
    assert events[0]["payload"]["implemented"] is True
    assert "error" in events[0]["payload"]

    artifacts = (await real_client.get(f"/api/runs/{run_id}/artifacts")).json()
    assert artifacts == []  # no plan artifact — the agent never produced one


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _has_real_llm_credentials(),
    reason="requires a real ANTHROPIC_API_KEY or OPENAI_API_KEY in backend/.env",
)
async def test_run_produces_real_plan_architecture_research_with_live_llm(
    real_client: httpx.AsyncClient,
) -> None:
    """Only runs when a real provider is configured. Exercises actual LLM
    calls end to end for Planner/Architect/Researcher; Developer onward are
    still Phase 3 stubs, so the run still completes structurally."""
    _, _, run_id = await _create_project_task_run(real_client)

    start_resp = await real_client.post(f"/api/runs/{run_id}/start")
    assert start_resp.status_code == 202

    run = await _poll_until_terminal(real_client, run_id, timeout=60.0)
    assert run["status"] == "completed"

    artifacts = (await real_client.get(f"/api/runs/{run_id}/artifacts")).json()
    artifacts_by_type = {a["type"]: a for a in artifacts}
    assert set(artifacts_by_type) == {"plan", "architecture", "research"}
    assert artifacts_by_type["plan"]["content"]["subtasks"]

    events = (await real_client.get(f"/api/runs/{run_id}/events")).json()
    event_types = [e["type"] for e in events]
    assert event_types == [
        "PLAN_CREATED",
        "ARCHITECTURE_PROPOSED",
        "RESEARCH_RESULT",
        "DEVELOPER_STEP_COMPLETED",
        "REVIEWER_STEP_COMPLETED",
        "QA_STEP_COMPLETED",
        "SECURITY_STEP_COMPLETED",
        "VERIFICATION_STEP_COMPLETED",
        "POLICY_STEP_COMPLETED",
    ]


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
