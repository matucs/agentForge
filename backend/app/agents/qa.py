"""QA agent — deterministic, no LLM. Spec §5.6: "QA must use actual test
execution." Detects a runnable test command for the target repo and
actually executes it via subprocess; nothing here is a guess about whether
tests would pass.
"""

import os
import re
import subprocess
import time
from dataclasses import dataclass

_TIMEOUT_SECONDS = 120

_PYTEST_SUMMARY = re.compile(
    r"(?P<passed>\d+) passed"
    r"(?:, (?P<failed>\d+) failed)?"
    r"|(?P<failed_only>\d+) failed"
)


@dataclass(frozen=True)
class QAResult:
    suite: str
    passed: bool
    total: int
    failed: int
    duration_seconds: float
    output: str


def _detect_command(repo_path: str) -> list[str] | None:
    has_pyproject = os.path.exists(os.path.join(repo_path, "pyproject.toml"))
    has_setup_py = os.path.exists(os.path.join(repo_path, "setup.py"))
    has_tests_dir = os.path.isdir(os.path.join(repo_path, "tests"))
    has_test_files = any(
        f.startswith("test_") and f.endswith(".py")
        for f in os.listdir(repo_path)
        if os.path.isfile(os.path.join(repo_path, f))
    )
    if has_pyproject or has_setup_py or has_tests_dir or has_test_files:
        return ["python3", "-m", "pytest", "-q"]

    if os.path.exists(os.path.join(repo_path, "package.json")):
        return ["npm", "test", "--silent"]

    return None


def _parse_pytest_summary(output: str) -> tuple[int, int]:
    """Returns (total, failed) from pytest's summary line, best-effort. Falls
    back to (0, 0) if the summary can't be parsed — the real exit code still
    drives `passed`, so a parse miss never flips the actual verdict."""
    match = _PYTEST_SUMMARY.search(output)
    if not match:
        return 0, 0
    passed = int(match.group("passed") or 0)
    failed = int(match.group("failed") or match.group("failed_only") or 0)
    return passed + failed, failed


def run_qa(repo_path: str) -> QAResult:
    command = _detect_command(repo_path)
    if command is None:
        return QAResult(
            suite="none",
            passed=False,
            total=0,
            failed=0,
            duration_seconds=0.0,
            output="No test runner detected (no pyproject.toml, setup.py, tests/, "
            "test_*.py, or package.json found in the repository).",
        )

    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
        output = (result.stdout or "") + (result.stderr or "")
        passed = result.returncode == 0
    except subprocess.TimeoutExpired as exc:
        output = f"Test command timed out after {_TIMEOUT_SECONDS}s: {exc}"
        passed = False
    duration = time.monotonic() - started

    total, failed = _parse_pytest_summary(output) if command[1:3] == ["-m", "pytest"] else (0, 0)

    return QAResult(
        suite=" ".join(command),
        passed=passed,
        total=total,
        failed=failed,
        duration_seconds=duration,
        output=output[-10_000:],  # cap stored output size
    )
