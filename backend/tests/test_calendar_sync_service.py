from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from app.adapters.google_calendar_adapter import CalendarProviderUnavailable
from app.models import (
    ActivityType,
    AttendanceSource,
    AttendanceStatus,
    CalendarConnection,
    CalendarEvent,
    CandidateTimeslot,
    Combination,
    CombinationStatus,
    ConnectionStatus,
    EventStatus,
    EventType,
    FeasibilityStatus,
    Participant,
    ParticipantRole,
    SchedulingSession,
    SessionStatus,
    TimeslotAttendance,
    UserAccount,
    Venue,
    VenueCategory,
)
from app.core.config import settings
from app.services.calendar_service import CalendarService
from app.services.calendar_sync_service import CalendarSyncService


class RecordingCalendarAdapter:
    def __init__(self, *, fail_writes=False):
        self.deleted = []
        self.upserts = []
        self.fail_writes = fail_writes
        self.transaction_probe = None
        self.provider_transaction_states = []

    async def free_busy(self, credential_reference, start, end, timezone_name):
        if self.transaction_probe:
            self.provider_transaction_states.append(self.transaction_probe())
        return ()

    async def delete_event(self, credential_reference, provider_event_id):
        if self.transaction_probe:
            self.provider_transaction_states.append(self.transaction_probe())
        if self.fail_writes:
            raise CalendarProviderUnavailable("raw provider secret detail")
        self.deleted.append((credential_reference, provider_event_id))

    async def upsert_event(self, credential_reference, idempotency_key, event):
        if self.transaction_probe:
            self.provider_transaction_states.append(self.transaction_probe())
        if self.fail_writes:
            raise CalendarProviderUnavailable("raw provider secret detail")
        provider_id = sha256(idempotency_key.encode()).hexdigest()[:32]
        self.upserts.append((credential_reference, idempotency_key, event, provider_id))
        return provider_id


def _sync_fixture(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sync.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        activity = ActivityType(category="SPORTS", name="Sync badminton")
        db.add(activity)
        db.flush()
        session = SchedulingSession(
            name="Saturday badminton",
            activity_type_id=activity.activity_type_id,
            date_range_start=datetime(2030, 11, 7, 1, tzinfo=timezone.utc),
            date_range_end=datetime(2030, 11, 7, 5, tzinfo=timezone.utc),
            response_deadline=datetime(2030, 11, 1, 1, tzinfo=timezone.utc),
            invitation_token="sync-fixture",
        )
        db.add(session)
        db.flush()
        accounts = [
            UserAccount(email=f"sync-{index}@example.com", display_name=f"Person {index}", provider_user_id=f"google-{index}")
            for index in range(3)
        ]
        db.add_all(accounts)
        db.flush()
        participants = [
            Participant(user_account_id=account.account_id, session_id=session.session_id, display_name=account.display_name)
            for account in accounts
        ]
        db.add_all(participants)
        db.flush()
        connections = []
        for index, participant in enumerate(participants):
            connections.append(
                CalendarConnection(
                    participant_id=participant.participant_id,
                    connection_status=ConnectionStatus.CONNECTED if index < 2 else ConnectionStatus.DISCONNECTED,
                    credential_reference=f"db:00000000-0000-0000-0000-00000000000{index}" if index < 2 else None,
                    granted_scopes="calendar.freebusy calendar.app.created" if index < 2 else "",
                )
            )
        db.add_all(connections)
        slots = [
            CandidateTimeslot(
                session_id=session.session_id,
                start_date_time=session.date_range_start + timedelta(hours=index),
                end_date_time=session.date_range_start + timedelta(hours=index + 1),
                available_count=2,
            )
            for index in range(2)
        ]
        db.add_all(slots)
        db.commit()
        return engine, session.session_id, [slot.timeslot_id for slot in slots]


def _confirmed_sync_fixture(tmp_path):
    engine, session_id, slot_ids = _sync_fixture(tmp_path)
    with Session(engine) as db:
        item = db.get(SchedulingSession, session_id)
        participants = list(
            db.exec(select(Participant).where(Participant.session_id == session_id)).all()
        )
        participants[0].role = ParticipantRole.ORGANISER
        item.organiser_participant_id = participants[0].participant_id
        item.status = SessionStatus.CONFIRMED
        venue = Venue(
            name="Bishan Sports Hall",
            category=VenueCategory.SPORTS_FACILITY,
            address="5 Bishan Street 14, Singapore 579783",
            meeting_point="Main entrance",
            postal_code="579783",
            latitude=1.3547,
            longitude=103.8518,
            data_source="test",
            source_key="confirmed-sync-venue",
        )
        db.add(venue)
        db.flush()
        combination = Combination(
            session_id=session_id,
            candidate_timeslot_id=slot_ids[0],
            venue_id=venue.venue_id,
            attendee_count=2,
            feasibility_status=FeasibilityStatus.FEASIBLE,
            status=CombinationStatus.CONFIRMED,
        )
        db.add(combination)
        db.flush()
        item.confirmed_combination_id = combination.combination_id
        db.add(item)
        for index, participant in enumerate(participants):
            db.add(
                TimeslotAttendance(
                    candidate_timeslot_id=slot_ids[0],
                    participant_id=participant.participant_id,
                    attendance_status=(
                        AttendanceStatus.AVAILABLE if index < 2 else AttendanceStatus.UNAVAILABLE
                    ),
                    source=AttendanceSource.MANUAL,
                )
            )
        db.commit()
        return (
            engine,
            session_id,
            combination.combination_id,
            [participant.user_account_id for participant in participants],
            slot_ids,
        )


@pytest.mark.asyncio
async def test_delete_owned_event_requires_persisted_provider_id(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'owned-delete.db'}")
    SQLModel.metadata.create_all(engine)
    adapter = RecordingCalendarAdapter()

    with Session(engine) as db:
        connection = CalendarConnection(
            participant_id=uuid4(),
            credential_reference="db:11111111-1111-1111-1111-111111111111",
        )
        db.add(connection)
        db.flush()
        owned = CalendarEvent(
            calendar_connection_id=connection.connection_id,
            session_id=uuid4(),
            event_type=EventType.TENTATIVE_HOLD,
            event_status=EventStatus.ACTIVE,
            provider_event_id="owned-provider-event",
        )
        missing_provider = CalendarEvent(
            calendar_connection_id=connection.connection_id,
            session_id=uuid4(),
            event_type=EventType.TENTATIVE_HOLD,
            event_status=EventStatus.PENDING,
        )
        db.add_all([owned, missing_provider])
        db.commit()

        await CalendarService.delete_owned_event(db, adapter, owned.event_id)
        assert adapter.deleted == [(connection.credential_reference, "owned-provider-event")]
        assert db.get(CalendarEvent, owned.event_id).event_status == EventStatus.DELETED

        with pytest.raises(HTTPException) as absent:
            await CalendarService.delete_owned_event(db, adapter, UUID("00000000-0000-0000-0000-000000000000"))
        assert absent.value.status_code == 404

        with pytest.raises(HTTPException) as no_provider:
            await CalendarService.delete_owned_event(db, adapter, missing_provider.event_id)
        assert no_provider.value.status_code == 409
        assert len(adapter.deleted) == 1


@pytest.mark.asyncio
async def test_connect_and_busy_import_close_database_transaction_before_provider_call(tmp_path):
    engine, session_id, _slot_ids = _sync_fixture(tmp_path)
    adapter = RecordingCalendarAdapter()
    original_key = settings.google_calendar_credential_key
    settings.google_calendar_credential_key = "Y2FsZW5kYXItY3JlZGVudGlhbC10ZXN0LWtleS0zMmI="

    try:
        with Session(engine) as db:
            user = db.exec(select(UserAccount).order_by(UserAccount.email)).first()
            reference = CalendarService.connect_user(
                db,
                user,
                subject=user.provider_user_id,
                refresh_token="transaction-test-token",
                granted_scopes=["calendar.freebusy", "calendar.app.created"],
            )
            assert isinstance(reference, str)
            assert not db.in_transaction()

            adapter.transaction_probe = db.in_transaction
            await CalendarService.import_busy(db, user, session_id, adapter)

            assert adapter.provider_transaction_states == [False]
    finally:
        settings.google_calendar_credential_key = original_key


@pytest.mark.asyncio
async def test_reconcile_holds_is_idempotent_and_excludes_disconnected_participants(tmp_path):
    engine, session_id, slot_ids = _sync_fixture(tmp_path)
    adapter = RecordingCalendarAdapter()

    with Session(engine) as db:
        adapter.transaction_probe = db.in_transaction
        service = CalendarSyncService(adapter)
        first = await service.reconcile_holds(db, session_id, slot_ids)
        second = await service.reconcile_holds(db, session_id, slot_ids)
        rows = list(db.exec(select(CalendarEvent).where(CalendarEvent.session_id == session_id)).all())

        assert first.succeeded == 4
        assert first.failed == 0
        assert first.not_connected == 1
        assert second.succeeded == 4
        assert len(rows) == 4
        assert all(row.event_status == EventStatus.ACTIVE and row.provider_event_id for row in rows)
        assert all(call[2].transparency == "transparent" for call in adapter.upserts)
        assert all(call[2].private_metadata["event_type"] == "TENTATIVE_HOLD" for call in adapter.upserts)
        assert len({call[3] for call in adapter.upserts}) == 4
        assert adapter.provider_transaction_states
        assert not any(adapter.provider_transaction_states)


@pytest.mark.asyncio
async def test_reconcile_holds_deletes_obsolete_provider_events(tmp_path):
    engine, session_id, slot_ids = _sync_fixture(tmp_path)
    adapter = RecordingCalendarAdapter()

    with Session(engine) as db:
        service = CalendarSyncService(adapter)
        await service.reconcile_holds(db, session_id, slot_ids)
        summary = await service.reconcile_holds(db, session_id, [slot_ids[1]])
        rows = list(db.exec(select(CalendarEvent).where(CalendarEvent.session_id == session_id)).all())

        assert summary.succeeded == 4
        assert len(adapter.deleted) == 2
        assert sum(row.event_status == EventStatus.DELETED for row in rows) == 2
        assert sum(row.event_status == EventStatus.ACTIVE for row in rows) == 2


@pytest.mark.asyncio
async def test_reconcile_holds_records_sanitized_errors_without_failing_core_flow(tmp_path):
    engine, session_id, slot_ids = _sync_fixture(tmp_path)
    adapter = RecordingCalendarAdapter(fail_writes=True)

    with Session(engine) as db:
        summary = await CalendarSyncService(adapter).reconcile_holds(db, session_id, slot_ids)
        rows = list(db.exec(select(CalendarEvent).where(CalendarEvent.session_id == session_id)).all())

        assert summary.succeeded == 0
        assert summary.failed == 4
        assert len(rows) == 4
        assert all(row.event_status == EventStatus.ERROR for row in rows)
        assert all(row.last_error == "Google Calendar sync failed; retry later" for row in rows)
        assert all("raw provider secret detail" not in row.last_error for row in rows)


@pytest.mark.asyncio
async def test_sync_confirmed_creates_attendee_events_and_cleans_every_hold(tmp_path):
    engine, session_id, combination_id, account_ids, slot_ids = _confirmed_sync_fixture(tmp_path)
    adapter = RecordingCalendarAdapter()

    with Session(engine) as db:
        adapter.transaction_probe = db.in_transaction
        await CalendarSyncService(adapter).reconcile_holds(db, session_id, slot_ids)
        organiser = db.get(UserAccount, account_ids[0])
        summary = await CalendarSyncService(adapter).sync_confirmed(db, organiser, session_id)
        rows = list(db.exec(select(CalendarEvent).where(CalendarEvent.session_id == session_id)).all())
        confirmed = [row for row in rows if row.event_type == EventType.CONFIRMED_EVENT]
        holds = [row for row in rows if row.event_type == EventType.TENTATIVE_HOLD]

        assert summary.to_api() == {
            "succeeded": 2,
            "failed": 0,
            "notConnected": 1,
            "canRetry": False,
        }
        assert len(confirmed) == 2
        assert all(row.combination_id == combination_id for row in confirmed)
        assert all(row.event_status == EventStatus.ACTIVE for row in confirmed)
        assert all(row.event_status == EventStatus.DELETED for row in holds)
        opaque_calls = [call for call in adapter.upserts if call[2].transparency == "opaque"]
        assert len(opaque_calls) == 2
        assert all(call[2].location == "Main entrance, 5 Bishan Street 14, Singapore 579783" for call in opaque_calls)
        assert all(call[2].private_metadata["event_type"] == "CONFIRMED_EVENT" for call in opaque_calls)
        assert adapter.provider_transaction_states
        assert not any(adapter.provider_transaction_states)


@pytest.mark.asyncio
async def test_sync_confirmed_is_idempotent_and_participant_retry_is_own_only(tmp_path):
    engine, session_id, _combination_id, account_ids, _slot_ids = _confirmed_sync_fixture(tmp_path)
    adapter = RecordingCalendarAdapter()

    with Session(engine) as db:
        organiser = db.get(UserAccount, account_ids[0])
        participant = db.get(UserAccount, account_ids[1])
        first = await CalendarSyncService(adapter).sync_confirmed(db, organiser, session_id)
        second = await CalendarSyncService(adapter).sync_confirmed(db, participant, session_id, own_only=True)
        rows = list(
            db.exec(
                select(CalendarEvent).where(
                    CalendarEvent.session_id == session_id,
                    CalendarEvent.event_type == EventType.CONFIRMED_EVENT,
                )
            ).all()
        )

        assert first.succeeded == 2
        assert second.to_api() == {
            "succeeded": 1,
            "failed": 0,
            "notConnected": 0,
            "canRetry": False,
        }
        assert len(rows) == 2
        participant_connection = db.exec(
            select(CalendarConnection).join(
                Participant, Participant.participant_id == CalendarConnection.participant_id
            ).where(Participant.user_account_id == participant.account_id)
        ).one()
        participant_calls = [
            call for call in adapter.upserts if str(participant_connection.connection_id) in call[1]
        ]
        assert len(participant_calls) == 2


@pytest.mark.asyncio
async def test_sync_confirmed_sanitizes_partial_failures_for_retry(tmp_path):
    engine, session_id, _combination_id, account_ids, _slot_ids = _confirmed_sync_fixture(tmp_path)

    with Session(engine) as db:
        organiser = db.get(UserAccount, account_ids[0])
        summary = await CalendarSyncService(RecordingCalendarAdapter(fail_writes=True)).sync_confirmed(
            db, organiser, session_id
        )
        item = db.get(SchedulingSession, session_id)
        rows = list(
            db.exec(
                select(CalendarEvent).where(
                    CalendarEvent.session_id == session_id,
                    CalendarEvent.event_type == EventType.CONFIRMED_EVENT,
                )
            ).all()
        )

        assert item.status == SessionStatus.CONFIRMED
        assert summary.to_api() == {
            "succeeded": 0,
            "failed": 2,
            "notConnected": 1,
            "canRetry": True,
        }
        assert len(rows) == 2
        assert all(row.event_status == EventStatus.ERROR for row in rows)
        assert all(row.last_error == "Google Calendar sync failed; retry later" for row in rows)
