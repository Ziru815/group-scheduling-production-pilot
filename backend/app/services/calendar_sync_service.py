"""Best-effort, idempotent synchronization of app-owned Calendar events."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from app.adapters.google_calendar_adapter import CalendarAuthorizationExpired, CalendarProviderUnavailable
from app.adapters.ports import CalendarEventInput, CalendarPort
from app.models import (
    ActivityType,
    AttendanceStatus,
    CalendarConnection,
    CalendarEvent,
    CandidateTimeslot,
    Combination,
    ConnectionStatus,
    EventStatus,
    EventType,
    Participant,
    ParticipantRole,
    SchedulingSession,
    SessionStatus,
    TimeslotAttendance,
    UserAccount,
    Venue,
)
from app.services.authorization_service import require_member


SANITIZED_SYNC_ERROR = "Google Calendar sync failed; retry later"


@dataclass(frozen=True)
class CalendarSyncSummary:
    succeeded: int = 0
    failed: int = 0
    not_connected: int = 0
    can_retry: bool = False

    def to_api(self) -> dict[str, int | bool]:
        return {
            "succeeded": self.succeeded,
            "failed": self.failed,
            "notConnected": self.not_connected,
            "canRetry": self.can_retry,
        }


class CalendarSyncService:
    def __init__(self, adapter: CalendarPort) -> None:
        self.adapter = adapter

    async def reconcile_holds(
        self,
        db: Session,
        session_id: UUID,
        candidate_timeslot_ids: list[UUID],
    ) -> CalendarSyncSummary:
        item = db.get(SchedulingSession, session_id)
        if item is None:
            raise HTTPException(404, "Session not found")
        slots = {
            slot.timeslot_id: slot
            for slot in db.exec(
                select(CandidateTimeslot).where(
                    CandidateTimeslot.session_id == session_id,
                    CandidateTimeslot.timeslot_id.in_(candidate_timeslot_ids),
                )
            ).all()
        }
        connections = list(
            db.exec(
                select(CalendarConnection)
                .join(Participant, Participant.participant_id == CalendarConnection.participant_id)
                .where(
                    Participant.session_id == session_id,
                    CalendarConnection.connection_status == ConnectionStatus.CONNECTED,
                )
            ).all()
        )
        participants = list(db.exec(select(Participant).where(Participant.session_id == session_id)).all())
        connected_participant_ids = {connection.participant_id for connection in connections if connection.credential_reference}
        succeeded = 0
        failed = 0
        target_ids = set(slots)
        all_holds = list(
            db.exec(
                select(CalendarEvent).where(
                    CalendarEvent.session_id == session_id,
                    CalendarEvent.event_type == EventType.TENTATIVE_HOLD,
                )
            ).all()
        )

        for hold in all_holds:
            if hold.candidate_timeslot_id in target_ids or hold.event_status == EventStatus.DELETED:
                continue
            hold_id = hold.event_id
            provider_event_id = hold.provider_event_id
            connection = db.get(CalendarConnection, hold.calendar_connection_id)
            credential_reference = connection.credential_reference if connection is not None else None
            db.commit()
            try:
                if provider_event_id and credential_reference:
                    await self.adapter.delete_event(credential_reference, provider_event_id)
                current = db.get(CalendarEvent, hold_id)
                current.event_status = EventStatus.DELETED
                current.last_error = None
                succeeded += 1
            except (CalendarProviderUnavailable, CalendarAuthorizationExpired):
                db.rollback()
                current = db.get(CalendarEvent, hold_id)
                current.event_status = EventStatus.ERROR
                current.last_error = SANITIZED_SYNC_ERROR
                failed += 1
            db.add(current)
            db.commit()

        for connection in connections:
            if not connection.credential_reference:
                continue
            for slot in slots.values():
                hold = next(
                    (
                        row
                        for row in all_holds
                        if row.calendar_connection_id == connection.connection_id
                        and row.candidate_timeslot_id == slot.timeslot_id
                    ),
                    None,
                )
                if hold is None:
                    hold = CalendarEvent(
                        calendar_connection_id=connection.connection_id,
                        session_id=session_id,
                        candidate_timeslot_id=slot.timeslot_id,
                        event_type=EventType.TENTATIVE_HOLD,
                        event_status=EventStatus.PENDING,
                    )
                    db.add(hold)
                    db.flush()
                    all_holds.append(hold)
                event = CalendarEventInput(
                    title=f"Hold: {item.name}",
                    start=slot.start_date_time,
                    end=slot.end_date_time,
                    timezone=item.timezone,
                    transparency="transparent",
                    private_metadata={
                        "session_id": str(session_id),
                        "candidate_timeslot_id": str(slot.timeslot_id),
                        "event_type": EventType.TENTATIVE_HOLD.value,
                    },
                )
                key = (
                    f"{connection.connection_id}:{session_id}:"
                    f"{slot.start_date_time.isoformat()}:{slot.end_date_time.isoformat()}:hold"
                )
                hold_id = hold.event_id
                credential_reference = connection.credential_reference
                db.commit()
                try:
                    provider_event_id = await self.adapter.upsert_event(
                        credential_reference,
                        key,
                        event,
                    )
                    current = db.get(CalendarEvent, hold_id)
                    current.provider_event_id = provider_event_id
                    current.event_status = EventStatus.ACTIVE
                    current.last_error = None
                    succeeded += 1
                except (CalendarProviderUnavailable, CalendarAuthorizationExpired):
                    db.rollback()
                    current = db.get(CalendarEvent, hold_id)
                    current.event_status = EventStatus.ERROR
                    current.last_error = SANITIZED_SYNC_ERROR
                    failed += 1
                db.add(current)
                db.commit()
        not_connected = max(0, len(participants) - len(connected_participant_ids))
        return CalendarSyncSummary(
            succeeded=succeeded,
            failed=failed,
            not_connected=not_connected,
            can_retry=failed > 0,
        )

    async def sync_confirmed(
        self,
        db: Session,
        user: UserAccount,
        session_id: UUID,
        *,
        own_only: bool = False,
    ) -> CalendarSyncSummary:
        member = require_member(db, session_id, user)
        item = db.get(SchedulingSession, session_id)
        if item is None:
            raise HTTPException(404, "Session not found")
        if item.status != SessionStatus.CONFIRMED or item.confirmed_combination_id is None:
            raise HTTPException(409, "Session has not been confirmed")
        combination = db.get(Combination, item.confirmed_combination_id)
        if combination is None:
            raise HTTPException(409, "Confirmed Combination was not found")
        slot = db.get(CandidateTimeslot, combination.candidate_timeslot_id)
        venue = db.get(Venue, combination.venue_id)
        if slot is None or venue is None:
            raise HTTPException(409, "Confirmed plan is incomplete")
        activity = db.get(ActivityType, item.activity_type_id)
        if activity is None:
            raise HTTPException(409, "Confirmed activity was not found")

        participants = list(
            db.exec(select(Participant).where(Participant.session_id == session_id)).all()
        )
        if own_only or member.role != ParticipantRole.ORGANISER:
            participants = [participant for participant in participants if participant.participant_id == member.participant_id]
        attendee_ids = {
            row.participant_id
            for row in db.exec(
                select(TimeslotAttendance).where(
                    TimeslotAttendance.candidate_timeslot_id == slot.timeslot_id,
                    TimeslotAttendance.attendance_status == AttendanceStatus.AVAILABLE,
                )
            ).all()
        }
        connections = {
            connection.participant_id: connection
            for connection in db.exec(
                select(CalendarConnection)
                .join(Participant, Participant.participant_id == CalendarConnection.participant_id)
                .where(Participant.session_id == session_id)
            ).all()
        }
        events = list(
            db.exec(select(CalendarEvent).where(CalendarEvent.session_id == session_id)).all()
        )
        succeeded = 0
        failed = 0
        not_connected = 0

        for participant in participants:
            connection = connections.get(participant.participant_id)
            if (
                connection is None
                or connection.connection_status != ConnectionStatus.CONNECTED
                or not connection.credential_reference
            ):
                not_connected += 1
                continue
            participant_failed = False

            if participant.participant_id in attendee_ids:
                confirmed = next(
                    (
                        row
                        for row in events
                        if row.calendar_connection_id == connection.connection_id
                        and row.event_type == EventType.CONFIRMED_EVENT
                        and row.candidate_timeslot_id == slot.timeslot_id
                    ),
                    None,
                )
                if confirmed is None:
                    confirmed = CalendarEvent(
                        calendar_connection_id=connection.connection_id,
                        session_id=session_id,
                        candidate_timeslot_id=slot.timeslot_id,
                        combination_id=combination.combination_id,
                        event_type=EventType.CONFIRMED_EVENT,
                        event_status=EventStatus.PENDING,
                    )
                    db.add(confirmed)
                    db.flush()
                    events.append(confirmed)
                confirmed.combination_id = combination.combination_id
                event = CalendarEventInput(
                    title=f"Group activity: {activity.name}",
                    start=slot.start_date_time,
                    end=slot.end_date_time,
                    timezone=item.timezone,
                    transparency="opaque",
                    location=(
                        f"{venue.meeting_point}, {venue.address}"
                        if venue.meeting_point
                        else venue.address
                    ),
                    private_metadata={
                        "session_id": str(session_id),
                        "combination_id": str(combination.combination_id),
                        "candidate_timeslot_id": str(slot.timeslot_id),
                        "event_type": EventType.CONFIRMED_EVENT.value,
                    },
                )
                key = (
                    f"{connection.connection_id}:{session_id}:"
                    f"{combination.combination_id}:confirmed"
                )
                confirmed_id = confirmed.event_id
                credential_reference = connection.credential_reference
                db.commit()
                try:
                    provider_event_id = await self.adapter.upsert_event(
                        credential_reference,
                        key,
                        event,
                    )
                    current_confirmed = db.get(CalendarEvent, confirmed_id)
                    current_confirmed.provider_event_id = provider_event_id
                    current_confirmed.event_status = EventStatus.ACTIVE
                    current_confirmed.last_error = None
                except (CalendarProviderUnavailable, CalendarAuthorizationExpired):
                    db.rollback()
                    current_confirmed = db.get(CalendarEvent, confirmed_id)
                    current_confirmed.event_status = EventStatus.ERROR
                    current_confirmed.last_error = SANITIZED_SYNC_ERROR
                    participant_failed = True
                db.add(current_confirmed)
                db.commit()

            participant_holds = [
                row
                for row in events
                if row.calendar_connection_id == connection.connection_id
                and row.event_type == EventType.TENTATIVE_HOLD
                and row.event_status != EventStatus.DELETED
            ]
            for hold in participant_holds:
                hold_id = hold.event_id
                provider_event_id = hold.provider_event_id
                credential_reference = connection.credential_reference
                db.commit()
                try:
                    if provider_event_id:
                        await self.adapter.delete_event(
                            credential_reference,
                            provider_event_id,
                        )
                    current_hold = db.get(CalendarEvent, hold_id)
                    current_hold.event_status = EventStatus.DELETED
                    current_hold.last_error = None
                except (CalendarProviderUnavailable, CalendarAuthorizationExpired):
                    db.rollback()
                    current_hold = db.get(CalendarEvent, hold_id)
                    current_hold.event_status = EventStatus.ERROR
                    current_hold.last_error = SANITIZED_SYNC_ERROR
                    participant_failed = True
                db.add(current_hold)
                db.commit()

            if participant_failed:
                failed += 1
            else:
                succeeded += 1

        return CalendarSyncSummary(
            succeeded=succeeded,
            failed=failed,
            not_connected=not_connected,
            can_retry=failed > 0,
        )

    @staticmethod
    def confirmed_summary(
        db: Session,
        user: UserAccount,
        session_id: UUID,
    ) -> CalendarSyncSummary:
        member = require_member(db, session_id, user)
        item = db.get(SchedulingSession, session_id)
        if item is None or item.confirmed_combination_id is None:
            return CalendarSyncSummary()
        combination = db.get(Combination, item.confirmed_combination_id)
        if combination is None:
            return CalendarSyncSummary(failed=1, can_retry=True)
        participants = list(
            db.exec(select(Participant).where(Participant.session_id == session_id)).all()
        )
        if member.role != ParticipantRole.ORGANISER:
            participants = [participant for participant in participants if participant.participant_id == member.participant_id]
        attendee_ids = {
            row.participant_id
            for row in db.exec(
                select(TimeslotAttendance).where(
                    TimeslotAttendance.candidate_timeslot_id == combination.candidate_timeslot_id,
                    TimeslotAttendance.attendance_status == AttendanceStatus.AVAILABLE,
                )
            ).all()
        }
        connections = {
            connection.participant_id: connection
            for connection in db.exec(
                select(CalendarConnection)
                .join(Participant, Participant.participant_id == CalendarConnection.participant_id)
                .where(Participant.session_id == session_id)
            ).all()
        }
        events = list(
            db.exec(select(CalendarEvent).where(CalendarEvent.session_id == session_id)).all()
        )
        succeeded = 0
        failed = 0
        not_connected = 0
        for participant in participants:
            connection = connections.get(participant.participant_id)
            if (
                connection is None
                or connection.connection_status != ConnectionStatus.CONNECTED
                or not connection.credential_reference
            ):
                not_connected += 1
                continue
            owned = [row for row in events if row.calendar_connection_id == connection.connection_id]
            has_error = any(row.event_status == EventStatus.ERROR for row in owned)
            has_live_hold = any(
                row.event_type == EventType.TENTATIVE_HOLD
                and row.event_status != EventStatus.DELETED
                for row in owned
            )
            has_confirmed = any(
                row.event_type == EventType.CONFIRMED_EVENT
                and row.combination_id == combination.combination_id
                and row.event_status == EventStatus.ACTIVE
                for row in owned
            )
            complete = not has_error and not has_live_hold and (
                participant.participant_id not in attendee_ids or has_confirmed
            )
            if complete:
                succeeded += 1
            else:
                failed += 1
        return CalendarSyncSummary(
            succeeded=succeeded,
            failed=failed,
            not_connected=not_connected,
            can_retry=failed > 0,
        )
