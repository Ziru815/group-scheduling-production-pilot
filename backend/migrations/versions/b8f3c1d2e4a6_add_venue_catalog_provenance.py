"""add venue catalogue provenance and verification state

Revision ID: b8f3c1d2e4a6
Revises: 7c1d2e3f4a5b
Create Date: 2026-10-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8f3c1d2e4a6"
down_revision: Union[str, None] = "7c1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


venue_verification_status = sa.Enum(
    "DEMO",
    "UNVERIFIED",
    "VERIFIED_PUBLIC",
    name="venueverificationstatus",
    native_enum=False,
)


def upgrade() -> None:
    op.add_column("venues", sa.Column("postal_code", sa.String(length=6), nullable=True))
    op.add_column("venues", sa.Column("source_key", sa.String(length=64), nullable=True))
    op.add_column(
        "venues",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("venues", sa.Column("is_active", sa.Boolean(), nullable=True))
    op.add_column(
        "venues",
        sa.Column("verification_status", venue_verification_status, nullable=True),
    )

    # Every pre-migration row came from the prototype catalogue. Keep it for
    # historical references, but make its demo provenance explicit.
    op.execute(
        sa.text(
            "UPDATE venues "
            "SET is_active = true, verification_status = 'DEMO'"
        )
    )
    with op.batch_alter_table("venues") as batch_op:
        batch_op.alter_column(
            "is_active",
            nullable=False,
            server_default=sa.true(),
        )
        batch_op.alter_column(
            "verification_status",
            existing_type=venue_verification_status,
            nullable=False,
            server_default=sa.text("'UNVERIFIED'"),
        )
        batch_op.create_unique_constraint(
            "uq_venues_data_source_source_key",
            ["data_source", "source_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("venues") as batch_op:
        batch_op.drop_constraint(
            "uq_venues_data_source_source_key",
            type_="unique",
        )
    op.drop_column("venues", "verification_status")
    op.drop_column("venues", "is_active")
    op.drop_column("venues", "last_synced_at")
    op.drop_column("venues", "source_key")
    op.drop_column("venues", "postal_code")
