"""fix created_at server_default to real now()

Revision ID: 0debfa0f3ecc
Revises: 9dcd5026b71a
Create Date: 2026-09-12 00:14:59.784760

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0debfa0f3ecc'
down_revision: Union[str, None] = '9dcd5026b71a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every table using TimestampMixin. The original migration passed a bare
# Python string `server_default="now()"` to `mapped_column`, which SQLAlchemy
# binds as a literal *parameter* rather than raw SQL — Postgres ended up with
# `DEFAULT '<the exact instant that CREATE TABLE ran>'`, not `DEFAULT now()`.
# Every row inserted since without an explicit created_at got that one frozen
# timestamp (confirmed via information_schema.columns.column_default and by
# observing identical created_at across unrelated rows). This corrects the
# column default going forward; it intentionally does not rewrite historical
# rows, since the wrong values they hold cannot be reconstructed.
_TABLES = [
    "projects",
    "tasks",
    "runs",
    "agents",
    "agent_messages",
    "artifacts",
    "decisions",
    "reviews",
    "test_results",
    "security_findings",
    "verification_results",
    "approvals",
    "evaluations",
    "evaluation_runs",
    "tool_calls",
    "audit_events",
]


def upgrade() -> None:
    for table in _TABLES:
        op.alter_column(
            table,
            "created_at",
            server_default=sa.text("now()"),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.alter_column(
            table,
            "created_at",
            server_default=sa.text("'1970-01-01T00:00:00+00'::timestamptz"),
        )
