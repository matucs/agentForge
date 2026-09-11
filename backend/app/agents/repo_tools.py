"""Deterministic, read-only repository inspection tools.

These are the Researcher's real evidence-gathering step: plain filesystem
code, no LLM involved. The Researcher agent (researcher.py) feeds their
output into its prompt and is required to ground every finding in what
these functions actually returned — never in what the model imagines might
be there (spec §5.3: "Do not allow the researcher to invent facts").
"""

import os
from dataclasses import dataclass

_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
}
_MAX_FILE_BYTES = 200_000  # skip anything larger — likely not source text worth grepping


def list_files(repo_path: str, max_files: int = 200) -> list[str]:
    """Relative paths of files under `repo_path`, skipping VCS/dependency/
    build directories. Truncated at `max_files` (repos can be huge; this is
    meant to ground an LLM prompt, not enumerate everything)."""
    results: list[str] = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(root, name), repo_path)
            results.append(rel)
            if len(results) >= max_files:
                return results
    return results


@dataclass(frozen=True)
class KeywordMatch:
    file: str
    line: int
    snippet: str


def search_keyword(repo_path: str, keyword: str, max_matches: int = 20) -> list[KeywordMatch]:
    """Case-insensitive grep for `keyword` across text files under
    `repo_path`. Binary/oversized files are skipped rather than raising —
    this is best-effort evidence gathering, not a required index."""
    matches: list[KeywordMatch] = []
    needle = keyword.lower()

    for rel_path in list_files(repo_path, max_files=2000):
        if len(matches) >= max_matches:
            break
        full_path = os.path.join(repo_path, rel_path)
        try:
            if os.path.getsize(full_path) > _MAX_FILE_BYTES:
                continue
            with open(full_path, encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    if needle in line.lower():
                        matches.append(
                            KeywordMatch(file=rel_path, line=line_no, snippet=line.strip()[:300])
                        )
                        if len(matches) >= max_matches:
                            break
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable — skip, don't fail the whole scan

    return matches
