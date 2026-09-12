"""Deterministic type-check and lint runners — same detect-then-subprocess
pattern as app/agents/qa.py. Neither tool being applicable to a given repo
is "not applicable," not a failure: absence of a type checker must never
itself count as a block (see gate.py's rules).
"""

import os
import subprocess
from dataclasses import dataclass

_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class CheckResult:
    tool: str
    applicable: bool
    passed: bool
    output: str


def _is_python_project(repo_path: str) -> bool:
    return os.path.exists(os.path.join(repo_path, "pyproject.toml")) or os.path.exists(
        os.path.join(repo_path, "setup.py")
    )


def _is_node_ts_project(repo_path: str) -> bool:
    return os.path.exists(os.path.join(repo_path, "package.json")) and os.path.exists(
        os.path.join(repo_path, "tsconfig.json")
    )


def _run(command: list[str], repo_path: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command, cwd=repo_path, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode == 0, output[-10_000:]
    except subprocess.TimeoutExpired as exc:
        return False, f"Command timed out after {_TIMEOUT_SECONDS}s: {exc}"
    except FileNotFoundError as exc:
        return False, f"Tool not installed: {exc}"


def run_typecheck(repo_path: str) -> CheckResult:
    if _is_python_project(repo_path):
        passed, output = _run(["python3", "-m", "mypy", "."], repo_path)
        return CheckResult(tool="mypy", applicable=True, passed=passed, output=output)
    if _is_node_ts_project(repo_path):
        passed, output = _run(["npx", "tsc", "--noEmit"], repo_path)
        return CheckResult(tool="tsc", applicable=True, passed=passed, output=output)
    return CheckResult(
        tool="none", applicable=False, passed=True, output="No type checker applicable."
    )


def run_lint(repo_path: str) -> CheckResult:
    if _is_python_project(repo_path):
        passed, output = _run(["python3", "-m", "ruff", "check", "."], repo_path)
        return CheckResult(tool="ruff", applicable=True, passed=passed, output=output)
    if os.path.exists(os.path.join(repo_path, "package.json")):
        passed, output = _run(["npx", "eslint", "."], repo_path)
        return CheckResult(tool="eslint", applicable=True, passed=passed, output=output)
    return CheckResult(tool="none", applicable=False, passed=True, output="No linter applicable.")
