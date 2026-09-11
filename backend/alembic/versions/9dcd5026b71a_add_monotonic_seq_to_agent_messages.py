"""add monotonic seq to agent_messages

Revision ID: 9dcd5026b71a
Revises: c51a76433958
Create Date: 2026-09-11 23:34:11.464422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '9dcd5026b71a'
down_revision: Union[str, None] = 'c51a76433958'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Note: autogenerate also proposed dropping checkpoint_blobs/checkpoint_writes/
# checkpoints/checkpoint_migrations. Those tables belong to
# langgraph-checkpoint-postgres (created by AsyncPostgresSaver.setup(), see
# app/orchestration/graph.py), not to our SQLAlchemy metadata — they are
# intentionally omitted here so Alembic never drops the checkpointer's own
# storage.


def upgrade() -> None:
    op.add_column(
        'agent_messages',
        sa.Column('seq', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    )
    op.create_unique_constraint(None, 'agent_messages', ['seq'])


def downgrade() -> None:
    op.drop_constraint(None, 'agent_messages', type_='unique')
    op.drop_column('agent_messages', 'seq')
