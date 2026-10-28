"""add encrypted Google Calendar credential storage

Revision ID: c9d4e5f6a7b8
Revises: b8f3c1d2e4a6
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d4e5f6a7b8"
down_revision: Union[str, None] = "b8f3c1d2e4a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


connection_status = sa.Enum(
    "CONNECTED",
    "DISCONNECTED",
    "DECLINED",
    "EXPIRED",
    "ERROR",
    name="connectionstatus",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table("calendar_credentials",
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("user_account_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("google_calendar_id", sa.String(length=500), nullable=True),
        sa.Column("granted_scopes", sa.String(length=1000), nullable=False),
        sa.Column("status", connection_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_account_id"], ["user_accounts.account_id"]),
        sa.PrimaryKeyConstraint("credential_id"),
        sa.UniqueConstraint("user_account_id"),
    )
    op.create_index(
        op.f("ix_calendar_credentials_user_account_id"),
        "calendar_credentials",
        ["user_account_id"],
        unique=True,
    )
    target_columns = [
        "calendar_connection_id",
        "session_id",
        "candidate_timeslot_id",
        "event_type",
    ]
    legacy_constraint = next(
        (
            constraint.get("name")
            for constraint in sa.inspect(op.get_bind()).get_unique_constraints("calendar_events")
            if constraint.get("column_names") == target_columns
            and constraint.get("name") != "uq_calendar_event_owned_slot_type"
        ),
        None,
    )
    naming_convention = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
    if legacy_constraint is None and op.get_bind().dialect.name == "sqlite":
        legacy_constraint = "uq_calendar_events_calendar_connection_id"
    with op.batch_alter_table(
        "calendar_events",
        naming_convention=naming_convention,
    ) as batch_op:
        if legacy_constraint:
            batch_op.drop_constraint(legacy_constraint, type_="unique")
        batch_op.alter_column("candidate_timeslot_id", nullable=True)
        batch_op.create_unique_constraint(
            "uq_calendar_event_owned_slot_type",
            ["calendar_connection_id", "session_id", "candidate_timeslot_id", "event_type"],
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM calendar_events WHERE candidate_timeslot_id IS NULL"
        )
    )
    with op.batch_alter_table("calendar_events") as batch_op:
        batch_op.drop_constraint("uq_calendar_event_owned_slot_type", type_="unique")
        batch_op.alter_column("candidate_timeslot_id", nullable=False)
        batch_op.create_unique_constraint(
            "uq_calendar_events_calendar_connection_id",
            ["calendar_connection_id", "session_id", "candidate_timeslot_id", "event_type"],
        )
    op.drop_index(op.f("ix_calendar_credentials_user_account_id"), table_name="calendar_credentials")
    op.drop_table("calendar_credentials")
