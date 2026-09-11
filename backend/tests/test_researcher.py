from app.agents.researcher import _extract_keywords, filter_grounded_findings
from app.agents.schemas import ResearchFinding


def test_filter_grounded_findings_keeps_real_files_and_drops_invented_ones() -> None:
    findings = [
        ResearchFinding(
            summary="pagination helper exists",
            file_path="src/users.py",
            evidence_quote="def paginate(users):",
        ),
        ResearchFinding(
            summary="invented file the model hallucinated",
            file_path="src/does_not_exist.py",
            evidence_quote="this was never actually scanned",
        ),
    ]
    scanned = {"src/users.py", "README.md"}

    grounded, discarded = filter_grounded_findings(findings, scanned)

    assert [f.file_path for f in grounded] == ["src/users.py"]
    assert [f.file_path for f in discarded] == ["src/does_not_exist.py"]


def test_filter_grounded_findings_with_no_findings_returns_empty_both() -> None:
    grounded, discarded = filter_grounded_findings([], {"README.md"})
    assert grounded == []
    assert discarded == []


def test_extract_keywords_ignores_stopwords_and_short_words() -> None:
    keywords = _extract_keywords("Add pagination to the users endpoint when filters are applied")
    assert "pagination" in keywords
    assert "users" in keywords
    assert "endpoint" in keywords
    assert "the" not in keywords
    assert "add" not in keywords  # stopword despite being requirement-relevant


def test_extract_keywords_caps_at_max_keywords() -> None:
    text = "alpha bravo charlie delta echo foxtrot golf hotel"
    assert len(_extract_keywords(text, max_keywords=3)) == 3
