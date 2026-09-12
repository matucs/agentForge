"""Spec §30: one real "add pagination" task through the complete live
pipeline. Requires real LLM credentials — prints the standard "Integration
unavailable" message and exits non-zero without them, never a fake run.
"""

import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

from app.config import get_settings
from app.db.repositories import (
    AgentMessageRepository,
    ProjectRepository,
    RunRepository,
    TaskRepository,
)
from app.db.session import async_session_factory
from app.orchestration.service import run_to_completion


def _has_real_llm_credentials() -> bool:
    settings = get_settings()
    return bool(settings.anthropic_api_key or settings.openai_api_key)


def _init_fixture_repo(tmp_dir: str) -> str:
    subprocess.run(["git", "init", "-q"], cwd=tmp_dir, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=tmp_dir, check=True)
    Path(tmp_dir, "users.py").write_text(
        "def list_users(db):\n    return db.query('SELECT * FROM users').all()\n"
    )
    Path(tmp_dir, "test_users.py").write_text(
        "def test_list_users_returns_all_users():\n    pass  # placeholder fixture test\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=tmp_dir, check=True)
    return tmp_dir


async def _print_new_events(run_id: str, seen: set[str]) -> None:
    async with async_session_factory() as session:
        events = await AgentMessageRepository(session).list_by_run(run_id)
    for event in events:
        if event.id in seen:
            continue
        seen.add(event.id)
        ts = event.created_at.strftime("%H:%M:%S")
        print(f"{ts}  {event.from_agent} -> {event.to_agent}  {event.type}")


async def run_full_demo() -> int:
    if not _has_real_llm_credentials():
        print(
            "Integration unavailable. Configure ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "to enable this feature.",
            file=sys.stderr,
        )
        return 1

    with tempfile.TemporaryDirectory(prefix="agentforge-demo-") as tmp_dir:
        repo_path = _init_fixture_repo(tmp_dir)

        async with async_session_factory() as session:
            project = await ProjectRepository(session).create(
                name="demo-add-pagination", repo_path=repo_path, description=None
            )
            task = await TaskRepository(session).create(
                project_id=project.id,
                title="Add pagination",
                requirement_text="Add pagination to the users endpoint.",
            )
            run = await RunRepository(session).create(task_id=task.id)
            await session.commit()
            run_id = run.id

        print(f"AgentForge Demo — run {run_id}\n")

        seen: set[str] = set()

        async def poll_events() -> None:
            while True:
                await _print_new_events(run_id, seen)
                await asyncio.sleep(1.0)

        poller = asyncio.create_task(poll_events())
        try:
            await run_to_completion(run_id)
        finally:
            poller.cancel()
            try:
                await poller
            except asyncio.CancelledError:
                pass
        await _print_new_events(run_id, seen)

        async with async_session_factory() as session:
            final_run = await RunRepository(session).get(run_id)
        assert final_run is not None

        print(f"\nFinal status: {final_run.status}")
        print(f"Final decision: {final_run.final_decision}")
        print(
            f"Tokens: {final_run.total_input_tokens} in / "
            f"{final_run.total_output_tokens} out — "
            f"${final_run.estimated_cost_usd:.4f}"
        )

    return 0


def main() -> None:
    exit_code = asyncio.run(run_full_demo())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
