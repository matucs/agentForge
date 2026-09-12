"""Deterministic static security scan — no LLM. Regex-based secret and
risky-construct detection over real file content. This is explicitly a
pattern scan, not a CVE/dependency-database lookup (see docs/limitations.md)
— it catches obvious, common footguns, not every vulnerability class.
"""

import re
from dataclasses import dataclass

_SECRET_PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key_header", re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    (
        "hardcoded_api_key_assignment",
        re.compile(
            r"""(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*["'][A-Za-z0-9_\-/+=]{16,}["']"""
        ),
    ),
]

_RISKY_PATTERNS = [
    ("eval_usage", re.compile(r"\beval\s*\(")),
    ("exec_usage", re.compile(r"\bexec\s*\(")),
    ("shell_true", re.compile(r"shell\s*=\s*True")),
    ("pickle_loads", re.compile(r"\bpickle\.loads?\s*\(")),
]


@dataclass(frozen=True)
class SecurityFindingDraft:
    severity: str  # "high" | "medium"
    category: str
    file: str
    line: int
    detail: str
    blocking: bool


def scan_file(file_path: str, content: str) -> list[SecurityFindingDraft]:
    findings: list[SecurityFindingDraft] = []

    for line_no, line in enumerate(content.splitlines(), start=1):
        for category, pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(
                    SecurityFindingDraft(
                        severity="high",
                        category=category,
                        file=file_path,
                        line=line_no,
                        detail=(
                            f"Secret-shaped string matching '{category}' found "
                            f"in {file_path}:{line_no}"
                        ),
                        blocking=True,
                    )
                )
        for category, pattern in _RISKY_PATTERNS:
            if pattern.search(line):
                findings.append(
                    SecurityFindingDraft(
                        severity="medium",
                        category=category,
                        file=file_path,
                        line=line_no,
                        detail=f"Risky construct '{category}' found in {file_path}:{line_no}",
                        blocking=False,
                    )
                )

    return findings


def scan_files(files: dict[str, str]) -> list[SecurityFindingDraft]:
    findings: list[SecurityFindingDraft] = []
    for file_path, content in files.items():
        findings.extend(scan_file(file_path, content))
    return findings
