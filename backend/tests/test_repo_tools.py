import os

import pytest

from app.agents.repo_tools import list_files, search_keyword


@pytest.fixture
def sample_repo(tmp_path) -> str:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "users.py").write_text(
        "def paginate(users):\n    return users[:10]\n"
    )
    (tmp_path / "README.md").write_text("# Sample\n\nHandles pagination for users.\n")

    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("should not be scanned")

    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("should not be scanned either")

    return str(tmp_path)


def test_list_files_finds_real_files_and_skips_dependency_dirs(sample_repo: str) -> None:
    files = list_files(sample_repo)
    assert os.path.join("src", "users.py") in files
    assert "README.md" in files
    assert not any("node_modules" in f for f in files)
    assert not any(f.startswith(".git") for f in files)


def test_list_files_respects_max_files(sample_repo: str) -> None:
    files = list_files(sample_repo, max_files=1)
    assert len(files) == 1


def test_search_keyword_finds_real_matches_with_location(sample_repo: str) -> None:
    matches = search_keyword(sample_repo, "pagination")
    assert matches
    assert any(m.file == "README.md" for m in matches)
    assert all(m.line >= 1 for m in matches)


def test_search_keyword_returns_empty_for_absent_term(sample_repo: str) -> None:
    assert search_keyword(sample_repo, "quantumflux") == []


def test_list_files_on_nonexistent_path_returns_empty_not_an_error() -> None:
    assert list_files("/no/such/path/exists") == []
