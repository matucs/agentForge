from app.verification.checks import run_lint, run_typecheck


def _write_pyproject(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"sample\"\nversion = \"0.1\"\n")


def test_typecheck_reports_not_applicable_for_a_non_python_non_node_repo(tmp_path) -> None:
    (tmp_path / "README.md").write_text("nothing here\n")
    result = run_typecheck(str(tmp_path))
    assert result.applicable is False
    assert result.passed is True


def test_typecheck_passes_on_a_clean_python_file(tmp_path) -> None:
    _write_pyproject(tmp_path)
    (tmp_path / "clean.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    result = run_typecheck(str(tmp_path))
    assert result.applicable is True
    assert result.passed is True


def test_typecheck_fails_on_a_real_type_error(tmp_path) -> None:
    _write_pyproject(tmp_path)
    (tmp_path / "broken.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n\nadd('x', 'y')\n"
    )
    result = run_typecheck(str(tmp_path))
    assert result.applicable is True
    assert result.passed is False
    assert "error" in result.output.lower()


def test_lint_reports_not_applicable_without_python_or_node_markers(tmp_path) -> None:
    (tmp_path / "README.md").write_text("nothing here\n")
    result = run_lint(str(tmp_path))
    assert result.applicable is False
    assert result.passed is True


def test_lint_passes_on_a_clean_python_file(tmp_path) -> None:
    _write_pyproject(tmp_path)
    (tmp_path / "clean.py").write_text("def add(a, b):\n    return a + b\n")
    result = run_lint(str(tmp_path))
    assert result.applicable is True
    assert result.passed is True


def test_lint_fails_on_a_real_lint_violation(tmp_path) -> None:
    _write_pyproject(tmp_path)
    (tmp_path / "messy.py").write_text("import os\n\n\ndef f():\n    pass\n")
    result = run_lint(str(tmp_path))
    assert result.applicable is True
    assert result.passed is False  # unused import 'os'
