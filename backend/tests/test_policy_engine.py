import pytest

from app.policy.engine import classify_risk, decide_policy


@pytest.mark.parametrize(
    "changed_files,expected",
    [
        (["README.md"], "low"),
        (["docs/architecture.md", "docs/limitations.md"], "low"),
        (["tests/test_users.py"], "low"),
        (["test_users.py"], "low"),
        (["frontend/src/app/page.tsx"], "low"),
        (["frontend/src/components/button.css"], "low"),
        (["requirements.txt"], "medium"),
        (["backend/pyproject.toml"], "medium"),
        (["package.json"], "medium"),
        (["backend/app/api/users.py"], "medium"),
        (["backend/app/routes/orders.py"], "medium"),
        (["backend/app/db/schema_migration_helper.py"], "medium"),
        (["backend/app/core/logic.py"], "medium"),  # sensible default
        (["backend/alembic/versions/0001_add_users.py"], "high"),
        (["migrations/0001_init.sql"], "high"),
        ([".github/workflows/deploy.yml"], "high"),
        (["Dockerfile"], "high"),
        (["docker-compose.yml"], "high"),
        (["k8s/deployment.yaml"], "high"),
    ],
)
def test_classify_risk_by_path(changed_files: list[str], expected: str) -> None:
    assert classify_risk(changed_files, diff_content="") == expected


def test_classify_risk_critical_for_unguarded_drop_table_in_migration() -> None:
    files = ["backend/alembic/versions/0002_drop_legacy.py"]
    diff = "+op.execute('DROP TABLE legacy_users')\n"
    assert classify_risk(files, diff) == "critical"


def test_classify_risk_high_not_critical_for_guarded_delete_in_migration() -> None:
    files = ["backend/alembic/versions/0003_cleanup.py"]
    diff = "+op.execute(\"DELETE FROM sessions WHERE expired = true\")\n"
    assert classify_risk(files, diff) == "high"  # has a WHERE clause — not flagged critical


def test_classify_risk_critical_requires_migration_path_not_just_dangerous_sql() -> None:
    # Dangerous SQL text in a non-migration file (e.g. a test fixture) should
    # not itself trigger "critical" — only real migration changes do.
    files = ["tests/test_fixtures.py"]
    diff = "+# example: DROP TABLE users\n"
    assert classify_risk(files, diff) == "low"


@pytest.mark.parametrize(
    "risk,verification_passed,expected",
    [
        ("low", True, "AUTO_APPROVED"),
        ("medium", True, "AUTO_APPROVED"),
        ("high", True, "PENDING_HUMAN_APPROVAL"),
        ("critical", True, "BLOCKED_BY_POLICY"),
        ("low", False, "BLOCKED_BY_VERIFICATION"),
        ("critical", False, "BLOCKED_BY_VERIFICATION"),  # verification failure always wins
    ],
)
def test_decide_policy(risk: str, verification_passed: bool, expected: str) -> None:
    assert decide_policy(risk, verification_passed) == expected  # type: ignore[arg-type]
