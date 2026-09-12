"""Risk-based policy engine (spec §11, ADR-004). Pure, deterministic
classification — no LLM, no UI-only enforcement. `classify_risk` and
`decide_policy` are the backend enforcement ADR-004 requires: the frontend
cannot bypass a HIGH/CRITICAL classification by simply not rendering an
approval prompt, because the classification happens here regardless of what
any client does.
"""

import re
from typing import Literal

RiskLevel = Literal["low", "medium", "high", "critical"]
PolicyDecision = Literal[
    "AUTO_APPROVED", "PENDING_HUMAN_APPROVAL", "BLOCKED_BY_POLICY", "BLOCKED_BY_VERIFICATION"
]

_MIGRATION_PATH_PATTERNS = (re.compile(r"(^|/)alembic/versions/"), re.compile(r"(^|/)migrations/"))
_DEPLOY_CONFIG_PATTERNS = (
    re.compile(r"(^|/)\.github/workflows/"),
    re.compile(r"(^|/)Dockerfile$"),
    re.compile(r"(^|/)docker-compose\.ya?ml$"),
    re.compile(r"(^|/)k8s/"),
)
_DEPENDENCY_MANIFEST_NAMES = {
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "poetry.lock",
}
_API_PATH_PATTERNS = (re.compile(r"(^|/)api/"), re.compile(r"(^|/)routes/"), re.compile(r"schema"))
_DANGEROUS_SQL_PATTERN = re.compile(
    r"(?i)\b(drop\s+table|delete\s+from)\b(?!.*\bwhere\b)"
)


def _is_docs_or_test_or_frontend_only(files: list[str]) -> bool:
    def _low_risk(path: str) -> bool:
        return (
            path.endswith(".md")
            or path.startswith("tests/")
            or path.split("/")[-1].startswith("test_")
            or path.startswith("frontend/")
            or path.endswith((".tsx", ".jsx", ".css"))
        )

    return len(files) > 0 and all(_low_risk(f) for f in files)


def classify_risk(changed_files: list[str], diff_content: str) -> RiskLevel:
    is_migration_change = any(
        p.search(f) for f in changed_files for p in _MIGRATION_PATH_PATTERNS
    )
    if is_migration_change and _DANGEROUS_SQL_PATTERN.search(diff_content):
        return "critical"

    if is_migration_change:
        return "high"
    if any(p.search(f) for f in changed_files for p in _DEPLOY_CONFIG_PATTERNS):
        return "high"

    if _is_docs_or_test_or_frontend_only(changed_files):
        return "low"

    if any(f.split("/")[-1] in _DEPENDENCY_MANIFEST_NAMES for f in changed_files):
        return "medium"
    if any(p.search(f) for f in changed_files for p in _API_PATH_PATTERNS):
        return "medium"

    return "medium"  # sensible default for general source changes (see docs/limitations.md)


def decide_policy(risk: RiskLevel, verification_passed: bool) -> PolicyDecision:
    if not verification_passed:
        return "BLOCKED_BY_VERIFICATION"
    if risk in ("low", "medium"):
        return "AUTO_APPROVED"
    if risk == "high":
        return "PENDING_HUMAN_APPROVAL"
    return "BLOCKED_BY_POLICY"  # critical
