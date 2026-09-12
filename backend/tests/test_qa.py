from app.agents.qa import run_qa


def test_qa_reports_pass_when_the_real_test_suite_passes(tmp_path) -> None:
    (tmp_path / "test_sample.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n"
    )
    result = run_qa(str(tmp_path))
    assert result.passed is True
    assert result.suite.endswith("pytest -q")
    assert "1 passed" in result.output


def test_qa_reports_failure_when_the_real_test_suite_fails(tmp_path) -> None:
    (tmp_path / "test_sample.py").write_text(
        "def test_broken():\n    assert 1 == 2\n"
    )
    result = run_qa(str(tmp_path))
    assert result.passed is False
    assert result.failed >= 1


def test_qa_reports_no_test_runner_detected_for_an_empty_repo(tmp_path) -> None:
    (tmp_path / "README.md").write_text("nothing here\n")
    result = run_qa(str(tmp_path))
    assert result.passed is False
    assert result.suite == "none"
    assert "No test runner detected" in result.output


def test_qa_detects_tests_directory_even_without_pyproject(tmp_path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_x.py").write_text("def test_x():\n    assert True\n")
    result = run_qa(str(tmp_path))
    assert result.passed is True
