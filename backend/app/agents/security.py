"""Security agent (spec §5.7) — deterministic, no LLM. Reads the real
content of files the Developer actually changed and runs the static scan
(security_scan.py) over them."""

import os

from app.agents.security_scan import SecurityFindingDraft, scan_files


def run_security_scan(repo_path: str, changed_files: list[str]) -> list[SecurityFindingDraft]:
    contents: dict[str, str] = {}
    for rel_path in changed_files:
        full_path = os.path.join(repo_path, rel_path)
        try:
            with open(full_path, encoding="utf-8") as f:
                contents[rel_path] = f.read()
        except (OSError, UnicodeDecodeError):
            continue  # binary/unreadable/deleted file — nothing to scan

    return scan_files(contents)
