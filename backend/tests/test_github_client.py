"""Tests for the GitHub client's own request/response handling — using
httpx's MockTransport to control the HTTP layer deterministically (same
spirit as the scripted LLMProvider double in tests/test_llm_json.py:
testing our own code, not simulating GitHub's actual behavior)."""

import httpx
import pytest

from app.config import Settings
from app.git_integration.github_client import GitHubClient, GitHubClientUnavailable


def _settings(**overrides) -> Settings:
    defaults = {"github_token": None, "github_repo": None}
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.asyncio
async def test_is_configured_false_without_both_token_and_repo() -> None:
    assert GitHubClient(_settings()).is_configured() is False
    assert GitHubClient(_settings(github_token="t")).is_configured() is False
    assert GitHubClient(_settings(github_repo="o/r")).is_configured() is False
    assert GitHubClient(_settings(github_token="t", github_repo="o/r")).is_configured() is True


@pytest.mark.asyncio
async def test_create_pull_request_raises_unavailable_without_credentials() -> None:
    client = GitHubClient(_settings())
    with pytest.raises(GitHubClientUnavailable):
        await client.create_pull_request(
            head_branch="agentforge/task-1", base_branch="main", title="t", body="b"
        )


def _patch_async_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real_async_client = httpx.AsyncClient

    def _factory(**kwargs):
        kwargs.pop("transport", None)
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", _factory)


@pytest.mark.asyncio
async def test_create_pull_request_parses_a_real_looking_successful_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/repos/acme/widgets/pulls"
        assert request.headers["Authorization"] == "Bearer fake-token"
        return httpx.Response(
            201,
            json={"html_url": "https://github.com/acme/widgets/pull/42", "number": 42},
        )

    _patch_async_client(monkeypatch, handler)

    client = GitHubClient(_settings(github_token="fake-token", github_repo="acme/widgets"))
    result = await client.create_pull_request(
        head_branch="agentforge/task-1", base_branch="main", title="t", body="b"
    )
    assert result.url == "https://github.com/acme/widgets/pull/42"
    assert result.number == 42


@pytest.mark.asyncio
async def test_create_pull_request_raises_on_a_real_error_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "Validation Failed"})

    _patch_async_client(monkeypatch, handler)

    client = GitHubClient(_settings(github_token="fake-token", github_repo="acme/widgets"))
    with pytest.raises(RuntimeError, match="422"):
        await client.create_pull_request(
            head_branch="agentforge/task-1", base_branch="main", title="t", body="b"
        )
