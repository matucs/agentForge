"""seed agent registry

Revision ID: c51a76433958
Revises: 48e9c8aaec9f
Create Date: 2026-09-11 21:50:36.468983

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c51a76433958'
down_revision: Union[str, None] = '48e9c8aaec9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


agents_table = sa.table(
    "agents",
    sa.column("id", sa.String),
    sa.column("name", sa.String),
    sa.column("role", sa.String),
    sa.column("responsibilities", sa.Text),
    sa.column("allowed_tools", sa.JSON),
)

# Registry + permission model from spec §5 and §24: each agent's allowed
# tools are the ceiling on what it may do, enforced elsewhere by the tool
# layer (Phase 5) — this seed just makes the registry itself real, queryable
# data instead of something only described in docs.
AGENTS = [
    {
        "name": "planner",
        "role": "Planner",
        "responsibilities": (
            "Interpret user requirements, identify ambiguities, break work into "
            "subtasks, define acceptance criteria, identify dependencies and risks."
        ),
        "allowed_tools": ["read_repository"],
    },
    {
        "name": "architect",
        "role": "Architect",
        "responsibilities": (
            "Inspect existing architecture, identify affected components, propose "
            "implementation architecture, write ADRs, challenge the Planner when "
            "the plan conflicts with the existing system."
        ),
        "allowed_tools": ["read_repository"],
    },
    {
        "name": "researcher",
        "role": "Researcher",
        "responsibilities": (
            "Search the repository and documentation for reusable code and prior "
            "art, and provide evidence-backed findings to other agents. Must not "
            "invent facts not grounded in what it actually found."
        ),
        "allowed_tools": ["read_repository", "search_documentation"],
    },
    {
        "name": "developer",
        "role": "Developer",
        "responsibilities": (
            "Implement the approved plan against a real Git working tree, write "
            "tests, run relevant tools, and report changed files and decisions."
        ),
        "allowed_tools": ["read_repository", "modify_files", "run_tests"],
    },
    {
        "name": "reviewer",
        "role": "Reviewer",
        "responsibilities": (
            "Inspect the actual diff against requirements, produce structured "
            "findings (severity, file, line, reason, recommendation). Must not "
            "rubber-stamp — findings are an input to the verification gate, not "
            "the final decision."
        ),
        "allowed_tools": ["read_repository", "inspect_diff"],
    },
    {
        "name": "qa",
        "role": "QA",
        "responsibilities": (
            "Determine and execute appropriate tests, analyze failures, identify "
            "missing coverage, and verify acceptance criteria via real test runs."
        ),
        "allowed_tools": ["read_repository", "run_tests"],
    },
    {
        "name": "security",
        "role": "Security",
        "responsibilities": (
            "Run dependency vulnerability checks, secret detection, and unsafe "
            "configuration/injection-risk analysis; produce actionable, "
            "severity-ranked findings."
        ),
        "allowed_tools": ["read_repository", "run_scanners"],
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for agent in AGENTS:
        conn.execute(
            agents_table.insert().values(
                id=str(uuid.uuid4()),
                name=agent["name"],
                role=agent["role"],
                responsibilities=agent["responsibilities"],
                allowed_tools=agent["allowed_tools"],
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    names = [a["name"] for a in AGENTS]
    conn.execute(agents_table.delete().where(agents_table.c.name.in_(names)))
