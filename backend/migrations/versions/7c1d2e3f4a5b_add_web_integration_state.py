"""add recommendation and confirmation state used by the web application

Revision ID: 7c1d2e3f4a5b
Revises: 01e3ac4ec64e
Create Date: 2026-10-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c1d2e3f4a5b"
down_revision: Union[str, None] = "01e3ac4ec64e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("recommendations_source_revision", sa.Integer(), nullable=True))
    op.add_column("sessions", sa.Column("recommendations_run_status", sa.String(length=80), nullable=True))
    op.add_column("sessions", sa.Column("recommendations_generated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sessions", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "confirmed_at")
    op.drop_column("sessions", "recommendations_generated_at")
    op.drop_column("sessions", "recommendations_run_status")
    op.drop_column("sessions", "recommendations_source_revision")
