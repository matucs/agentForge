"""Real GitHub REST API client — same shape as app/llm/base.py's provider
abstraction. No credentials configured means "unavailable," never a
fabricated PR URL (spec §35/§12).
"""

from dataclasses import dataclass

import httpx

from app.config import Settings

_API_BASE = "https://api.github.com"


class GitHubClientUnavailable(RuntimeError):
    """Raised when GITHUB_TOKEN/GITHUB_REPO aren't both configured. Callers
    must surface this as an explicit unavailable state, never fall back to
    a simulated PR."""


@dataclass(frozen=True)
class PullRequestResult:
    url: str
    number: int


class GitHubClient:
    def __init__(self, settings: Settings) -> None:
        self._token = settings.github_token
        self._repo = settings.github_repo

    def is_configured(self) -> bool:
        return bool(self._token) and bool(self._repo)

    async def create_pull_request(
        self, *, head_branch: str, base_branch: str, title: str, body: str
    ) -> PullRequestResult:
        if not self.is_configured():
            raise GitHubClientUnavailable(
                "GitHub integration unavailable: GITHUB_TOKEN/GITHUB_REPO not configured. "
                "Set both to enable real pull request creation."
            )

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{_API_BASE}/repos/{self._repo}/pulls",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github+json",
                },
                json={
                    "title": title,
                    "body": body,
                    "head": head_branch,
                    "base": base_branch,
                },
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"GitHub PR creation failed ({response.status_code}): {response.text[:500]}"
            )

        data = response.json()
        return PullRequestResult(url=data["html_url"], number=data["number"])
