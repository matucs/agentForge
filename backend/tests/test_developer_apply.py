import subprocess

import pytest

from app.agents.developer import apply_developer_output, branch_name_for_task
from app.agents.schemas import DeveloperFile, DeveloperOutput
from app.git_integration.git_ops import GitOperationError, get_current_branch


@pytest.fixture
def git_repo(tmp_path) -> str:
    repo_path = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=repo_path, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=repo_path, check=True)
    (tmp_path / "README.md").write_text("# Sample\n")
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=repo_path, check=True)
    return repo_path


def test_apply_developer_output_creates_branch_writes_and_commits_for_real(
    git_repo: str,
) -> None:
    output = DeveloperOutput(
        files=[DeveloperFile(path="src/pagination.py", content="def paginate(x):\n    return x\n")],
        test_files=[
            DeveloperFile(path="test_pagination.py", content="def test_paginate():\n    pass\n")
        ],
        summary="Add pagination helper",
    )

    branch, commit_sha = apply_developer_output(git_repo, "task-1", output, base_ref="main")

    assert branch == branch_name_for_task("task-1")
    assert get_current_branch(git_repo) == branch
    assert len(commit_sha) == 40

    with open(f"{git_repo}/src/pagination.py") as f:
        assert "def paginate" in f.read()
    with open(f"{git_repo}/test_pagination.py") as f:
        assert "def test_paginate" in f.read()


def test_apply_developer_output_raises_when_llm_proposed_no_files(git_repo: str) -> None:
    output = DeveloperOutput(files=[], test_files=[], summary="nothing to do")
    with pytest.raises(GitOperationError):
        apply_developer_output(git_repo, "task-1", output, base_ref="main")
