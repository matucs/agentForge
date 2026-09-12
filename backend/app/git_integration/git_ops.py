"""Real Git working-tree operations, shelling out to the `git` CLI.

Every function here does the real thing — creates a real branch, writes
real files, makes a real commit — against `repo_path` on disk. Nothing is
simulated. Never pushes to a remote; that's Phase 7 (GitHub PR creation).
"""

import os
import subprocess


class GitOperationError(RuntimeError):
    pass


def _run_git(repo_path: str, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise GitOperationError(
            f"git {' '.join(args)} failed in {repo_path}: {result.stderr.strip()}"
        )
    return result.stdout


def ensure_branch(repo_path: str, branch_name: str, *, base_ref: str = "main") -> None:
    """Checks out `branch_name`, creating it from `base_ref` if it doesn't
    exist yet. If it already exists (e.g. a retry re-entering Developer),
    `base_ref` is ignored and the existing branch — with its prior commits —
    is checked out as-is, never recreated."""
    existing = _run_git(repo_path, "branch", "--list", branch_name)
    if existing.strip():
        _run_git(repo_path, "checkout", branch_name)
        return

    try:
        _run_git(repo_path, "checkout", base_ref)
    except GitOperationError:
        pass  # base_ref doesn't exist — branch from whatever is currently checked out
    _run_git(repo_path, "checkout", "-b", branch_name)


def write_files(repo_path: str, files: dict[str, str]) -> None:
    """Writes each {relative_path: content} to disk under repo_path."""
    for rel_path, content in files.items():
        full_path = os.path.join(repo_path, rel_path)
        os.makedirs(os.path.dirname(full_path) or repo_path, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)


def commit_all(repo_path: str, message: str) -> str:
    """Stages every change and commits. Returns the new commit SHA. Raises
    if there is nothing to commit — callers should not claim a change was
    made when the working tree was already clean."""
    _run_git(repo_path, "add", "-A")
    status = _run_git(repo_path, "status", "--porcelain")
    if not status.strip():
        raise GitOperationError("nothing to commit — working tree is clean")
    _run_git(repo_path, "commit", "-m", message)
    return _run_git(repo_path, "rev-parse", "HEAD").strip()


def get_diff(repo_path: str, base_ref: str) -> str:
    """Unified diff of the current branch against `base_ref`. Falls back to
    the diff of the most recent commit if `base_ref` doesn't resolve (e.g. a
    single-commit repo with no separate base branch)."""
    try:
        return _run_git(repo_path, "diff", f"{base_ref}...HEAD")
    except GitOperationError:
        return _run_git(repo_path, "diff", "HEAD~1..HEAD")


def get_current_branch(repo_path: str) -> str:
    return _run_git(repo_path, "rev-parse", "--abbrev-ref", "HEAD").strip()


def changed_files(repo_path: str, base_ref: str) -> list[str]:
    """Relative paths changed on the current branch vs. base_ref."""
    try:
        output = _run_git(repo_path, "diff", "--name-only", f"{base_ref}...HEAD")
    except GitOperationError:
        output = _run_git(repo_path, "diff", "--name-only", "HEAD~1..HEAD")
    return [line for line in output.splitlines() if line.strip()]
