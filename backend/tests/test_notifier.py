"""Tests for the outbound n8n/Slack webhook notifier — httpx's MockTransport
controls the HTTP layer deterministically (same technique as
tests/test_github_client.py): this tests our own request-building code, not
a real n8n/Slack endpoint.
"""

import httpx
import pytest

from app.config import Settings
from app.integrations.notifier import notify_approval_required, notify_run_finished


def _settings(**overrides) -> Settings:
    defaults = {"n8n_webhook_url": None, "slack_webhook_url": None}
    defaults.update(overrides)
    return Settings(**defaults)


def _patch_async_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real_async_client = httpx.AsyncClient

    def _factory(**kwargs):
        kwargs.pop("transport", None)
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", _factory)


@pytest.mark.asyncio
async def test_notify_run_finished_is_a_silent_noop_without_any_webhook_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no HTTP request should be made when unconfigured")

    _patch_async_client(monkeypatch, handler)

    await notify_run_finished(
        _settings(), run_id="r1", task_id="t1", status="completed", final_decision="AUTO_APPROVED"
    )


@pytest.mark.asyncio
async def test_notify_run_finished_posts_real_json_to_n8n(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://n8n.example.com/webhook/agentforge"
        return httpx.Response(200, json={"ok": True})

    _patch_async_client(monkeypatch, handler)

    await notify_run_finished(
        _settings(n8n_webhook_url="https://n8n.example.com/webhook/agentforge"),
        run_id="r1",
        task_id="t1",
        status="blocked",
        final_decision="BLOCKED_BY_VERIFICATION",
    )

    assert len(calls) == 1
    body = calls[0].content
    import json

    payload = json.loads(body)
    assert payload == {
        "event": "run.finished",
        "run_id": "r1",
        "task_id": "t1",
        "status": "blocked",
        "final_decision": "BLOCKED_BY_VERIFICATION",
    }


@pytest.mark.asyncio
async def test_notify_run_finished_posts_slack_formatted_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    _patch_async_client(monkeypatch, handler)

    await notify_run_finished(
        _settings(slack_webhook_url="https://hooks.slack.com/services/xyz"),
        run_id="r1",
        task_id="t1",
        status="completed",
        final_decision="AUTO_APPROVED",
    )

    assert len(calls) == 1
    import json

    payload = json.loads(calls[0].content)
    assert "text" in payload
    assert "r1" in payload["text"]
    assert "completed" in payload["text"]


@pytest.mark.asyncio
async def test_notify_run_finished_posts_to_both_when_both_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    _patch_async_client(monkeypatch, handler)

    await notify_run_finished(
        _settings(
            n8n_webhook_url="https://n8n.example.com/hook",
            slack_webhook_url="https://hooks.slack.com/services/xyz",
        ),
        run_id="r1",
        task_id="t1",
        status="completed",
        final_decision=None,
    )

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_notify_run_finished_swallows_a_failed_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    _patch_async_client(monkeypatch, handler)

    # Must not raise even though the webhook returns a server error.
    await notify_run_finished(
        _settings(n8n_webhook_url="https://n8n.example.com/hook"),
        run_id="r1",
        task_id="t1",
        status="completed",
        final_decision=None,
    )


@pytest.mark.asyncio
async def test_notify_run_finished_swallows_a_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _patch_async_client(monkeypatch, handler)

    await notify_run_finished(
        _settings(n8n_webhook_url="https://n8n.example.com/hook"),
        run_id="r1",
        task_id="t1",
        status="completed",
        final_decision=None,
    )


@pytest.mark.asyncio
async def test_notify_approval_required_posts_real_json_to_n8n(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    _patch_async_client(monkeypatch, handler)

    await notify_approval_required(
        _settings(n8n_webhook_url="https://n8n.example.com/hook"),
        run_id="r1",
        task_id="t1",
        risk_level="high",
        reason="Risk classified as 'high'.",
    )

    import json

    payload = json.loads(calls[0].content)
    assert payload["event"] == "run.approval_required"
    assert payload["risk_level"] == "high"
