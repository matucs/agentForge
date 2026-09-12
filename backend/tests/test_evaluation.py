import os
import subprocess
import sys

import pytest

from app.evaluation.loader import EvalTaskLoadError, load_tasks
from app.evaluation.runner import _TASKS_DIR


def test_load_tasks_loads_all_real_spec_example_tasks() -> None:
    tasks = load_tasks(str(_TASKS_DIR))
    names = {t.name for t in tasks}
    assert names == {
        "pagination",
        "authentication",
        "websocket-reconnect",
        "database-index",
        "api-validation",
    }
    for task in tasks:
        assert task.requirement.strip()
        assert task.expected_behavior.strip()
        assert task.acceptance_criteria


def test_load_tasks_rejects_a_malformed_task_file(tmp_path) -> None:
    (tmp_path / "broken.yaml").write_text("requirement: missing the name field\n")
    with pytest.raises(EvalTaskLoadError):
        load_tasks(str(tmp_path))


def test_load_tasks_returns_empty_list_for_a_dir_with_no_yaml_files(tmp_path) -> None:
    (tmp_path / "README.md").write_text("not a task\n")
    assert load_tasks(str(tmp_path)) == []


def test_make_eval_reports_unavailable_without_credentials() -> None:
    """Real, always-on: runs the actual eval entrypoint as a subprocess with
    no LLM credentials in its environment and asserts the exact spec §35
    behavior — a clear "unavailable" message and a non-zero exit, never a
    fabricated report."""
    excluded = {"ANTHROPIC_API_KEY", "OPENAI_API_KEY"}
    env = {k: v for k, v in os.environ.items() if k not in excluded}
    result = subprocess.run(
        [sys.executable, "-m", "app.evaluation.runner"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "Integration unavailable" in result.stderr
    assert "ANTHROPIC_API_KEY" in result.stderr
    assert "AgentForge Evaluation" not in result.stdout  # no fabricated report
