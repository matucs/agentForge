"""Evaluation harness (spec §14/§32). Executes each task in evals/tasks/
against a real disposable git fixture repo through the actual orchestration
service — the same code path a live run takes, not a separate simulation.

No LLM credentials configured -> prints spec §35's exact pattern and exits
non-zero. Never a fabricated report.
"""

import asyncio
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from app.config import get_settings
from app.db.repositories import (
    EvaluationRepository,
    EvaluationRunRepository,
    ProjectRepository,
    RunRepository,
    TaskRepository,
)
from app.db.session import async_session_factory
from app.evaluation.loader import load_tasks
from app.evaluation.schemas import EvalTask
from app.orchestration.service import run_to_completion

_TASKS_DIR = Path(__file__).resolve().parents[3] / "evals" / "tasks"

_TERMINAL_SUCCESS = {"completed", "awaiting_approval"}
_TERMINAL_STATUSES = _TERMINAL_SUCCESS | {
    "failed",
    "blocked",
    "rejected",
    "stopped_by_timeout",
    "stopped_by_budget",
    "cancelled",
}


def _has_real_llm_credentials() -> bool:
    settings = get_settings()
    return bool(settings.anthropic_api_key or settings.openai_api_key)


def _init_fixture_repo(tmp_dir: str) -> str:
    subprocess.run(["git", "init", "-q"], cwd=tmp_dir, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=tmp_dir, check=True)
    Path(tmp_dir, "app.py").write_text("def add(a, b):\n    return a + b\n")
    Path(tmp_dir, "test_app.py").write_text(
        "from app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=tmp_dir, check=True)
    return tmp_dir


async def _run_one_task(task: EvalTask) -> dict:
    with tempfile.TemporaryDirectory(prefix="agentforge-eval-") as tmp_dir:
        repo_path = _init_fixture_repo(tmp_dir)

        async with async_session_factory() as session:
            project = await ProjectRepository(session).create(
                name=f"eval-{task.name}", repo_path=repo_path, description=None
            )
            db_task = await TaskRepository(session).create(
                project_id=project.id, title=task.name, requirement_text=task.requirement
            )
            run = await RunRepository(session).create(task_id=db_task.id)
            await session.commit()
            run_id = run.id

        started = time.monotonic()
        await run_to_completion(run_id)
        duration = time.monotonic() - started

        async with async_session_factory() as session:
            final_run = await RunRepository(session).get(run_id)
            assert final_run is not None

        return {
            "task_name": task.name,
            "run_id": run_id,
            "status": final_run.status,
            "success": final_run.status in _TERMINAL_SUCCESS,
            "duration_seconds": duration,
            "estimated_cost_usd": final_run.estimated_cost_usd,
        }


async def run_evaluation() -> int:
    if not _has_real_llm_credentials():
        print(
            "Integration unavailable. Configure ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "to enable this feature.",
            file=sys.stderr,
        )
        return 1

    tasks = load_tasks(str(_TASKS_DIR))
    if not tasks:
        print(f"No eval tasks found in {_TASKS_DIR}.", file=sys.stderr)
        return 1

    results = []
    for task in tasks:
        result = await _run_one_task(task)
        results.append(result)

        async with async_session_factory() as session:
            evaluation = await EvaluationRepository(session).get_or_create(
                name=task.name, task_file=f"{task.name}.yaml"
            )
            await EvaluationRunRepository(session).create(
                evaluation_id=evaluation.id,
                run_id=result["run_id"],
                success=result["success"],
                duration_seconds=result["duration_seconds"],
                estimated_cost_usd=result["estimated_cost_usd"],
                # reviewer_correct/qa_detected/security_detected are left
                # unset (None = not measured) — computing them honestly
                # requires the Phase 10 failure-injection harness (a task
                # with a *known* injected bug to check detection against).
                # Never fabricated here.
            )
            await session.commit()

    completed = sum(1 for r in results if r["success"])
    failed = len(results) - completed
    avg_duration = sum(r["duration_seconds"] for r in results) / len(results)
    avg_cost = sum(r["estimated_cost_usd"] for r in results) / len(results)

    print("\nAgentForge Evaluation\n")
    print(f"Tasks:                 {len(results)}")
    print(f"Completed:             {completed}")
    print(f"Failed:                {failed}")
    print()
    print("Reviewer/QA/Security detection rate: not measured (requires the Phase 10")
    print("failure-injection harness — a task with a known injected bug to check")
    print("detection against; not fabricated here).")
    print()
    print(f"Average duration:      {avg_duration:.1f}s")
    print(f"Average estimated cost: ${avg_cost:.4f}")
    print()
    print("Regression status: no prior baseline in this environment")

    return 0 if failed == 0 else 1


def main() -> None:
    exit_code = asyncio.run(run_evaluation())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
