"""Pull request creation — the last real Git-integration step (spec §12).
Called after a run is already `completed` (auto-approved by policy, or
approved by a human): PR creation is additive, not a merge gate, so a
failure here is recorded but never reverts the policy decision that already
happened.
"""

import logging

from app.config import get_settings
from app.db.repositories import (
    AgentMessageRepository,
    ArtifactRepository,
    ProjectRepository,
    RunRepository,
    TaskRepository,
)
from app.db.session import async_session_factory
from app.git_integration.git_ops import GitOperationError, push_branch
from app.git_integration.github_client import GitHubClient, GitHubClientUnavailable

logger = logging.getLogger(__name__)

_BASE_BRANCH = "main"


async def open_pull_request(run_id: str) -> None:
    settings = get_settings()
    client = GitHubClient(settings)

    async with async_session_factory() as session:
        run = await RunRepository(session).get(run_id)
        if run is None or run.branch_name is None:
            return  # nothing to open a PR for (e.g. Developer never ran)
        task = await TaskRepository(session).get(run.task_id)
        assert task is not None
        project = await ProjectRepository(session).get(task.project_id)
        assert project is not None

    if not client.is_configured():
        await _emit(
            run_id,
            task_id=task.id,
            message_type="PR_CREATION_SKIPPED",
            payload={
                "reason": "GitHub integration unavailable: GITHUB_TOKEN/GITHUB_REPO not "
                "configured. Configure both to enable real pull request creation."
            },
        )
        return

    remote_url = (
        f"https://x-access-token:{settings.github_token}@github.com/"
        f"{settings.github_repo}.git"
    )

    try:
        push_branch(project.repo_path, run.branch_name, remote_url)
        result = await client.create_pull_request(
            head_branch=run.branch_name,
            base_branch=_BASE_BRANCH,
            title=f"AgentForge: {task.title}",
            body=f"Automated change for task {task.id}.\n\nRequirement:\n{task.requirement_text}",
        )
    except (GitOperationError, GitHubClientUnavailable, RuntimeError) as exc:
        logger.exception("PR creation failed for run %s", run_id)
        await _emit(
            run_id, task_id=task.id, message_type="PR_CREATION_FAILED", payload={"error": str(exc)}
        )
        return

    async with async_session_factory() as session:
        artifact = await ArtifactRepository(session).create(
            run_id=run_id,
            type="pull_request",
            produced_by="system",
            content={"url": result.url, "number": result.number},
        )
        await AgentMessageRepository(session).create(
            run_id=run_id,
            task_id=task.id,
            from_agent="system",
            to_agent="orchestrator",
            type="PR_CREATED",
            artifact_id=artifact.id,
            payload={"url": result.url, "number": result.number},
        )
        await session.commit()


async def _emit(run_id: str, *, task_id: str, message_type: str, payload: dict) -> None:
    async with async_session_factory() as session:
        await AgentMessageRepository(session).create(
            run_id=run_id,
            task_id=task_id,
            from_agent="system",
            to_agent="orchestrator",
            type=message_type,
            payload=payload,
        )
        await session.commit()
