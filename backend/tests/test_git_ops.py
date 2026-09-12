import subprocess

import pytest

from app.git_integration.git_ops import (
    GitOperationError,
    changed_files,
    commit_all,
    ensure_branch,
    get_current_branch,
    get_diff,
    push_branch,
    write_files,
)


@pytest.fixture
def git_repo(tmp_path) -> str:
    repo_path = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=repo_path, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=repo_path, check=True)
    (tmp_path / "README.md").write_text("# Sample\n")
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=repo_path, check=True)
    return repo_path


def test_ensure_branch_creates_and_checks_out_new_branch(git_repo: str) -> None:
    ensure_branch(git_repo, "agentforge/task-1")
    assert get_current_branch(git_repo) == "agentforge/task-1"


def test_ensure_branch_checks_out_existing_branch_without_recreating(git_repo: str) -> None:
    ensure_branch(git_repo, "agentforge/task-1")
    write_files(git_repo, {"a.txt": "hello"})
    commit_all(git_repo, "add a.txt")

    ensure_branch(git_repo, "main")
    ensure_branch(git_repo, "agentforge/task-1")

    assert get_current_branch(git_repo) == "agentforge/task-1"
    with open(f"{git_repo}/a.txt") as f:
        assert f.read() == "hello"  # the earlier commit is still there, not recreated


def test_write_files_creates_nested_directories(git_repo: str) -> None:
    write_files(git_repo, {"src/pkg/mod.py": "x = 1\n"})
    with open(f"{git_repo}/src/pkg/mod.py") as f:
        assert f.read() == "x = 1\n"


def test_commit_all_returns_a_real_sha(git_repo: str) -> None:
    write_files(git_repo, {"a.txt": "content"})
    sha = commit_all(git_repo, "add a.txt")
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)


def test_commit_all_raises_when_nothing_changed(git_repo: str) -> None:
    with pytest.raises(GitOperationError):
        commit_all(git_repo, "empty commit attempt")


def test_get_diff_shows_real_content_change(git_repo: str) -> None:
    ensure_branch(git_repo, "agentforge/task-1")
    write_files(git_repo, {"a.txt": "new content\n"})
    commit_all(git_repo, "add a.txt")

    diff = get_diff(git_repo, "main")
    assert "a.txt" in diff
    assert "new content" in diff


def test_changed_files_lists_only_real_diff_paths(git_repo: str) -> None:
    ensure_branch(git_repo, "agentforge/task-1")
    write_files(git_repo, {"a.txt": "1", "b.txt": "2"})
    commit_all(git_repo, "add files")

    files = changed_files(git_repo, "main")
    assert set(files) == {"a.txt", "b.txt"}


def test_push_branch_pushes_to_a_real_remote(git_repo: str, tmp_path_factory) -> None:
    # A real local bare repo stands in for "GitHub" here — git itself treats
    # a filesystem path as a perfectly valid remote URL, so this exercises
    # real `git push` mechanics (refspec, remote resolution) without any
    # network dependency.
    remote_path = str(tmp_path_factory.mktemp("remote"))
    subprocess.run(["git", "init", "-q", "--bare", remote_path], check=True)

    ensure_branch(git_repo, "agentforge/task-1")
    write_files(git_repo, {"a.txt": "pushed content\n"})
    commit_all(git_repo, "add a.txt")

    push_branch(git_repo, "agentforge/task-1", remote_path)

    branch_list = subprocess.run(
        ["git", "branch", "--list", "agentforge/task-1"],
        cwd=remote_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "agentforge/task-1" in branch_list.stdout


def test_push_branch_raises_on_a_real_failure(git_repo: str) -> None:
    with pytest.raises(GitOperationError):
        push_branch(git_repo, "main", "/no/such/remote/path")
