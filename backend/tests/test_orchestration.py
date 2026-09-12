import asyncio
import subprocess

import httpx
import pytest

from app.config import get_settings


async def _create_project_task_run(
    client: httpx.AsyncClient, *, repo_path: str = "/repo"
) -> tuple[str, str, str]:
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


def _init_fixture_repo(tmp_path) -> str:
    """A tiny real git repo with a Python package and a passing test, so
    Developer has something to branch from and QA has a real test suite to
    execute against."""
    repo_path = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=repo_path, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=repo_path, check=True)
    (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "test_app.py").write_text(
        "from app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=repo_path, check=True)
    return repo_path


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _has_real_llm_credentials(),
    reason="requires a real ANTHROPIC_API_KEY or OPENAI_API_KEY in backend/.env",
)
async def test_run_executes_full_pipeline_with_live_llm(
    real_client: httpx.AsyncClient, tmp_path
) -> None:
    """Only runs when a real provider is configured. Exercises actual LLM
    calls for Planner/Architect/Researcher/Developer/Reviewer against a real
    temp git repo, and real subprocess test execution + static security scan
    for QA/Security. Loose on exact event sequence/iteration count since
    real LLM output can trigger a genuine Reviewer/QA retry loop — that's a
    feature (Phase 3's routing actually firing), not something to pin down
    to one exact path."""
    repo_path = _init_fixture_repo(tmp_path)
    _, _, run_id = await _create_project_task_run(real_client, repo_path=repo_path)

    start_resp = await real_client.post(f"/api/runs/{run_id}/start")
    assert start_resp.status_code == 202

    run = await _poll_until_terminal(real_client, run_id, timeout=120.0)
    # Terminal status now depends on the real, deterministic verification
    # gate and policy engine (Phase 6) — see the status assertion below,
    # after the events/verification-results checks establish the pipeline
    # actually ran all the way through.

    artifacts = (await real_client.get(f"/api/runs/{run_id}/artifacts")).json()
    artifact_types = [a["type"] for a in artifacts]
    assert "plan" in artifact_types
    assert "architecture" in artifact_types
    assert "research" in artifact_types
    assert "implementation" in artifact_types

    implementation = next(a for a in artifacts if a["type"] == "implementation")
    assert implementation["content"]["commit_sha"]
    assert len(implementation["content"]["commit_sha"]) == 40

    branch_output = subprocess.run(
        ["git", "branch", "--list", implementation["content"]["branch"]],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert implementation["content"]["branch"] in branch_output.stdout

    events = (await real_client.get(f"/api/runs/{run_id}/events")).json()
    event_types = [e["type"] for e in events]
    assert event_types[:3] == ["PLAN_CREATED", "ARCHITECTURE_PROPOSED", "RESEARCH_RESULT"]
    assert event_types[-1] == "POLICY_DECIDED"
    assert "IMPLEMENTATION_READY" in event_types
    assert any(t in event_types for t in ("VERIFICATION_PASSED", "VERIFICATION_FAILED"))

    test_results = (await real_client.get(f"/api/runs/{run_id}/test-results")).json()
    assert len(test_results) >= 1

    security_findings_resp = await real_client.get(f"/api/runs/{run_id}/security-findings")
    assert security_findings_resp.status_code == 200  # real endpoint, even if list is empty

    verification_results_resp = await real_client.get(
        f"/api/runs/{run_id}/verification-results"
    )
    assert len(verification_results_resp.json()) >= 1

    # This run's final status depends on the real risk classification of
    # whatever the live LLM actually changed and whether verification
    # passed — assert it's a real, recognized terminal state rather than
    # hardcoding "completed" (a Reviewer/QA retry loop, or the model
    # touching a path classify_risk treats as high-risk, are both
    # legitimate real outcomes here).
    assert run["status"] in {"completed", "awaiting_approval", "blocked"}


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
