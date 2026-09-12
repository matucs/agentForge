"""Tests for the n8n webhook endpoint (spec §22) — real project/task/run
creation and a real `start_run` invocation, same path the dashboard's "new
task" form takes. Needs `real_client`: `start_run` schedules a background
task that runs on its own DB connection (via `async_session_factory`) and
must see rows already committed by this request, the same constraint
documented on the `real_client` fixture itself.
"""

import asyncio

import httpx
import pytest


@pytest.mark.asyncio
async def test_webhook_creates_and_starts_a_real_run_for_an_existing_project(
    real_client: httpx.AsyncClient,
) -> None:
    project = (
        await real_client.post(
            "/api/projects", json={"name": "Webhook-P1", "repo_path": "/repo", "description": None}
        )
    ).json()

    resp = await real_client.post(
        "/api/webhooks/n8n",
        json={
            "project_id": project["id"],
            "title": "Fix reported bug",
            "requirement_text": "Ticket #123: users can't log in.",
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["project_id"] == project["id"]

    # start_run was really invoked: the run leaves "pending" on its own.
    for _ in range(20):
        run = (await real_client.get(f"/api/runs/{body['run_id']}")).json()
        if run["status"] != "pending":
            break
        await asyncio.sleep(0.05)
    assert run["status"] != "pending"


@pytest.mark.asyncio
async def test_webhook_finds_or_creates_a_project_by_name(
    real_client: httpx.AsyncClient,
) -> None:
    payload = {
        "project_name": "Webhook-Found-Or-Created",
        "repo_path": "/repo2",
        "title": "First ticket",
        "requirement_text": "First.",
    }
    first = (await real_client.post("/api/webhooks/n8n", json=payload)).json()

    payload2 = {**payload, "title": "Second ticket", "requirement_text": "Second."}
    second = (await real_client.post("/api/webhooks/n8n", json=payload2)).json()

    assert first["project_id"] == second["project_id"]

    projects = (await real_client.get("/api/projects")).json()
    matching = [p for p in projects if p["name"] == "Webhook-Found-Or-Created"]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_webhook_requires_project_id_or_name_and_repo_path(
    real_client: httpx.AsyncClient,
) -> None:
    resp = await real_client.post(
        "/api/webhooks/n8n", json={"title": "t", "requirement_text": "r"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_webhook_404s_for_an_unknown_project_id(real_client: httpx.AsyncClient) -> None:
    resp = await real_client.post(
        "/api/webhooks/n8n",
        json={"project_id": "does-not-exist", "title": "t", "requirement_text": "r"},
    )
    assert resp.status_code == 404
