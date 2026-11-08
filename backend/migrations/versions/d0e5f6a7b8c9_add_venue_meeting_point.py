"""add nullable venue meeting point

Revision ID: d0e5f6a7b8c9
Revises: c9d4e5f6a7b8
Create Date: 2026-10-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e5f6a7b8c9"
down_revision: Union[str, None] = "c9d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "venues",
        sa.Column("meeting_point", sa.String(length=180), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("venues", "meeting_point")
