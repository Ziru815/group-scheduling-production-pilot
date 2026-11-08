from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import CalendarConnection, CalendarCredential, ConnectionStatus, ActivityType, Participant, UserAccount
from app.schemas import AvailabilityIntervalInput, SessionCreate
from app.services.application_services import SessionService


def test_session_rejects_deadline_after_start_and_invalid_weights():
    start = datetime.now(timezone.utc) + timedelta(days=3)
    with pytest.raises(ValidationError):
        SessionCreate(name="Bad", activity_type_id="00000000-0000-0000-0000-000000000001", date_range_start=start, date_range_end=start + timedelta(hours=2), response_deadline=start, attendance_weight_percent=50, travel_weight_percent=40)


def test_interval_requires_positive_duration():
    instant = datetime.now(timezone.utc)
    with pytest.raises(ValidationError): AvailabilityIntervalInput(start_date_time=instant, end_date_time=instant)

def test_create_session_respects_foreign_keys_when_linking_organiser(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'session-fk.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    start = datetime.now(timezone.utc) + timedelta(days=3)

    with Session(engine) as db:
        user = UserAccount(
            email="organiser@example.com",
            display_name="Organiser",
            provider_user_id="google-organiser",
        )
        activity = ActivityType(category="SPORTS", name="Badminton FK test")
        db.add(user)
        db.add(activity)
        db.commit()

        created = SessionService.create(
            db,
            user,
            SessionCreate(
                name="Foreign-key-safe session",
                activity_type_id=activity.activity_type_id,
                date_range_start=start,
                date_range_end=start + timedelta(hours=2),
                response_deadline=start - timedelta(days=1),
                minimum_attendee_threshold=2,
            ),
        )

        organiser = db.get(Participant, created.organiser_participant_id)
        assert organiser is not None
        assert organiser.session_id == created.session_id


def test_connected_calendar_propagates_to_sessions_created_or_joined_later(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'future-calendar.db'}")
    SQLModel.metadata.create_all(engine)
    start = datetime.now(timezone.utc) + timedelta(days=3)

    with Session(engine) as db:
        organiser = UserAccount(
            email="connected-organiser@example.com",
            display_name="Connected organiser",
            provider_user_id="google-connected-organiser",
        )
        joiner = UserAccount(
            email="connected-joiner@example.com",
            display_name="Connected joiner",
            provider_user_id="google-connected-joiner",
        )
        activity = ActivityType(category="SPORTS", name="Future Calendar propagation")
        db.add_all([organiser, joiner, activity])
        db.flush()
        credentials = [
            CalendarCredential(
                user_account_id=user.account_id,
                encrypted_refresh_token=f"encrypted-{index}",
                granted_scopes="calendar.freebusy calendar.app.created",
                status=ConnectionStatus.CONNECTED,
            )
            for index, user in enumerate([organiser, joiner])
        ]
        db.add_all(credentials)
        db.commit()

        created = SessionService.create(
            db,
            organiser,
            SessionCreate(
                name="Created after Calendar connect",
                activity_type_id=activity.activity_type_id,
                date_range_start=start,
                date_range_end=start + timedelta(hours=2),
                response_deadline=start - timedelta(days=1),
            ),
        )
        joined = SessionService.join(db, joiner, created.invitation_token)

        connections = list(db.exec(select(CalendarConnection)).all())
        by_participant = {row.participant_id: row for row in connections}
        assert by_participant[created.organiser_participant_id].credential_reference == f"db:{credentials[0].credential_id}"
        assert by_participant[joined.participant_id].credential_reference == f"db:{credentials[1].credential_id}"
        assert all(row.connection_status == ConnectionStatus.CONNECTED for row in connections)
