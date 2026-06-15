"""add_exec_command_to_test_definitions

Revision ID: 49b4bae7abe8
Revises: 9dd873fe2bd5
Create Date: 2026-06-15 17:49:39.091953

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '49b4bae7abe8'
down_revision: str | Sequence[str] | None = '9dd873fe2bd5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'test_definitions',
        sa.Column('exec_command', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('test_definitions', 'exec_command')
