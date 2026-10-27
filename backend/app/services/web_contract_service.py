"""Privacy-safe projections and mutations for the React API contract."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import (
    ActivityType,
    AttendanceStatus,
    AvailabilityInterval,
    AvailabilityRecord,
    CalendarConnection,
    CalendarEvent,
    CandidateTimeslot,
    Combination,
    CombinationStatus,
    ConnectionStatus,
    EventStatus,
    EventType,
    FeasibilityStatus,
    GeocodeStatus,
    IntervalSource,
    IntervalType,
    Participant,
    ParticipantRole,
    RecordStatus,
    ResponseStatus,
    RoutingStatus,
    SchedulingSession,
    SessionStatus,
    SubmissionSource,
    TimeslotAttendance,
    TravelEstimate,
    UserAccount,
    Venue,
)
from app.repositories import AvailabilityRepository, ParticipantRepository, SessionRepository
from app.schemas.web import SaveResponseRequest
from app.services.application_services import _bump_revision, _ensure_active, _get_session_or_404, _utcnow
from app.services.authorization_service import require_member, require_organiser


def session_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, "Unknown timezone") from exc


def local_datetime(value: datetime, timezone_name: str) -> datetime:
    zone = session_zone(timezone_name)
    return value.replace(tzinfo=zone) if value.tzinfo is None else value.astimezone(zone)


def activity_categories(db: Session) -> list[dict]:
    activities = list(db.exec(select(ActivityType).where(ActivityType.is_active == True).order_by(ActivityType.category, ActivityType.name)).all())  # noqa: E712
    grouped: dict[str, list[dict]] = {}
    for activity in activities:
        grouped.setdefault(activity.category.title(), []).append({"id": activity.activity_type_id, "name": activity.name})
    return [{"category": category, "types": values} for category, values in grouped.items()]


def session_detail(db: Session, user: UserAccount, item: SchedulingSession) -> dict:
    member = require_member(db, item.session_id, user)
    activity = db.get(ActivityType, item.activity_type_id)
    organiser = db.get(Participant, item.organiser_participant_id)
    has_recommendations = item.recommendations_generated_at is not None
    stale = has_recommendations and item.recommendations_source_revision != item.source_revision
    start = local_datetime(item.date_range_start, item.timezone)
    end = local_datetime(item.date_range_end, item.timezone)
    deadline = local_datetime(item.response_deadline, item.timezone)
    return {
        "id": item.session_id,
        "name": item.name,
        "activityType": {"id": activity.activity_type_id, "name": activity.name, "category": activity.category.title()},
        "organiserName": organiser.display_name,
        "status": item.status.value,
        "myRole": member.role.value,
        "myResponseStatus": member.response_status.value,
        "startDate": start.date().isoformat(),
        "endDate": end.date().isoformat(),
        "dailyStartTime": start.strftime("%H:%M"),
        "dailyEndTime": end.strftime("%H:%M"),
        "timezone": item.timezone,
        "durationMinutes": item.duration_minutes,
        "responseDeadline": deadline,
        "minimumAttendees": item.minimum_attendee_threshold,
        "travelObjective": item.travel_objective.value,
        "attendanceWeightPercent": item.attendance_weight_percent,
        "isClosed": item.status != SessionStatus.ACTIVE or _utcnow() > _as_utc(deadline),
        "recommendationsStale": stale,
        "hasRecommendations": has_recommendations,
        "confirmed": confirmed_plan(db, item),
    }


def session_list(db: Session, user: UserAccount) -> list[dict]:
    result = []
    for item in SessionRepository(db).for_user(user.account_id):
        detail = session_detail(db, user, item)
        participants = ParticipantRepository(db).for_session(item.session_id)
        submitted = sum(p.response_status == ResponseStatus.SUBMITTED for p in participants)
        confirmed = detail["confirmed"]
        result.append(
            {
                "id": item.session_id,
                "name": item.name,
                "activityTypeName": detail["activityType"]["name"],
                "organiserName": detail["organiserName"],
                "status": detail["status"],
                "myRole": detail["myRole"],
                "myResponseStatus": detail["myResponseStatus"],
                "responseDeadline": detail["responseDeadline"],
                "timezone": item.timezone,
                "submittedCount": submitted,
                "participantCount": len(participants),
                "confirmed": None if confirmed is None else {
                    "venueName": confirmed["venue"]["name"],
                    "start": confirmed["start"],
                    "end": confirmed["end"],
                },
            }
        )
    return result


def invitation_preview(db: Session, user: UserAccount, token: str) -> dict:
    item = SessionRepository(db).by_token(token)
    if item is None:
        raise HTTPException(404, "Invitation is invalid")
    organiser = db.get(Participant, item.organiser_participant_id)
    activity = db.get(ActivityType, item.activity_type_id)
    start = local_datetime(item.date_range_start, item.timezone)
    end = local_datetime(item.date_range_end, item.timezone)
    deadline = local_datetime(item.response_deadline, item.timezone)
    existing = ParticipantRepository(db).membership(item.session_id, user.account_id)
    return {
        "sessionId": item.session_id,
        "name": item.name,
        "activityTypeName": activity.name,
        "organiserName": organiser.display_name,
        "status": item.status.value,
        "startDate": start.date().isoformat(),
        "endDate": end.date().isoformat(),
        "timezone": item.timezone,
        "responseDeadline": deadline,
        "isClosed": item.status != SessionStatus.ACTIVE or _utcnow() > _as_utc(deadline),
        "alreadyJoined": existing is not None,
    }


def my_response(db: Session, user: UserAccount, session_id: UUID) -> dict:
    participant = require_member(db, session_id, user)
    repo = AvailabilityRepository(db)
    record = repo.current(participant.participant_id)
    if record is None:
        return {"participantId": participant.participant_id, "responseStatus": participant.response_status.value, "record": None}
    return _response_projection(participant, record, repo.intervals(record.record_id))


def save_response(db: Session, user: UserAccount, session_id: UUID, data: SaveResponseRequest, location: dict | None) -> dict:
    participant = require_member(db, session_id, user)
    item = _get_session_or_404(db, session_id, lock=True)
    _ensure_active(item)
    if _utcnow() > _as_utc(local_datetime(item.response_deadline, item.timezone)):
        raise HTTPException(409, "Response deadline has passed")
    repo = AvailabilityRepository(db)
    previous = repo.current(participant.participant_id)
    if location is None and previous is None:
        raise HTTPException(422, "A starting location is required")

    intervals = sorted(data.intervals, key=lambda row: row.start)
    for row in intervals:
        if _as_utc(row.start) < _as_utc(local_datetime(item.date_range_start, item.timezone)) or _as_utc(row.end) > _as_utc(local_datetime(item.date_range_end, item.timezone)):
            raise HTTPException(422, "Availability must be inside the Session date range")
    for before, after in zip(intervals, intervals[1:]):
        if after.start < before.end:
            raise HTTPException(422, "Availability intervals cannot overlap")
    if intervals and not any(
        (row.end - row.start).total_seconds() >= item.duration_minutes * 60
        for row in intervals
    ):
        raise HTTPException(
            422,
            f"Select at least one continuous {item.duration_minutes}-minute block so this activity can fit",
        )

    next_revision = previous.source_revision + 1 if previous else 1
    if previous is not None:
        previous.record_status = RecordStatus.WITHDRAWN
        previous.withdrawn_at = _utcnow()
        db.add(previous)
    location_input_type = location["input_type"] if location else previous.location_input_type
    location_input = location["input"] if location else previous.location_input
    latitude = location["latitude"] if location else previous.latitude
    longitude = location["longitude"] if location else previous.longitude
    record = AvailabilityRecord(
        participant_id=participant.participant_id,
        location_input_type=location_input_type,
        location_input=location_input,
        latitude=latitude,
        longitude=longitude,
        geocode_status=GeocodeStatus.VALID,
        transport_mode=data.transport_mode,
        submission_source=SubmissionSource.CALENDAR_ASSISTED if data.calendar_assisted else SubmissionSource.MANUAL,
        record_status=RecordStatus.ACTIVE,
        source_revision=next_revision,
        submitted_at=_utcnow(),
    )
    db.add(record)
    db.flush()
    interval_rows = [
        AvailabilityInterval(
            availability_record_id=record.record_id,
            start_date_time=row.start,
            end_date_time=row.end,
            interval_type=IntervalType.AVAILABLE,
            interval_source=IntervalSource.MANUAL,
        )
        for row in intervals
    ]
    db.add_all(interval_rows)
    participant.response_status = ResponseStatus.SUBMITTED
    _bump_revision(item)
    db.add(participant)
    db.add(item)
    db.commit()
    return _response_projection(participant, record, interval_rows)


def withdraw_response(db: Session, user: UserAccount, session_id: UUID) -> dict:
    participant = require_member(db, session_id, user)
    item = _get_session_or_404(db, session_id, lock=True)
    _ensure_active(item)
    if _utcnow() > _as_utc(local_datetime(item.response_deadline, item.timezone)):
        raise HTTPException(409, "Response deadline has passed")
    record = AvailabilityRepository(db).current(participant.participant_id)
    if record is None:
        raise HTTPException(404, "No active response")
    record.record_status = RecordStatus.WITHDRAWN
    record.withdrawn_at = _utcnow()
    participant.response_status = ResponseStatus.WITHDRAWN
    _bump_revision(item)
    db.add(record)
    db.add(participant)
    db.add(item)
    db.commit()
    return {"participantId": participant.participant_id, "responseStatus": participant.response_status.value, "record": None}


def response_status(db: Session, user: UserAccount, session_id: UUID) -> dict:
    require_organiser(db, session_id, user)
    repo = AvailabilityRepository(db)
    rows = []
    counts = Counter()
    for participant in ParticipantRepository(db).for_session(session_id):
        record = repo.current(participant.participant_id)
        updated = record.submitted_at if record else None
        rows.append(
            {
                "participantId": participant.participant_id,
                "displayName": participant.display_name,
                "role": participant.role.value,
                "responseStatus": participant.response_status.value,
                "updatedAt": updated,
            }
        )
        counts[participant.response_status.value] += 1
    return {
        "participants": rows,
        "counts": {status.value: counts[status.value] for status in ResponseStatus},
        "refreshedAt": _utcnow(),
    }


def recommendation_set(db: Session, user: UserAccount, session_id: UUID) -> dict:
    require_member(db, session_id, user)
    item = _get_session_or_404(db, session_id)
    if item.recommendations_generated_at is None or item.recommendations_source_revision is None:
        raise HTTPException(404, "Recommendations have not been generated")
    revision = item.recommendations_source_revision
    combinations = list(
        db.exec(
            select(Combination)
            .where(Combination.session_id == session_id, Combination.source_revision == revision)
            .order_by(col(Combination.rank).asc())
        ).all()
    )
    visible = [c for c in combinations if c.feasibility_status in {FeasibilityStatus.FEASIBLE, FeasibilityStatus.DATA_UNAVAILABLE}]
    visible.sort(key=lambda c: (c.feasibility_status != FeasibilityStatus.FEASIBLE, c.rank or 10**9, str(c.combination_id)))
    excluded = Counter(c.exclusion_reason for c in combinations if c.feasibility_status == FeasibilityStatus.EXCLUDED and c.exclusion_reason)
    projected = [_combination_projection(db, combo, index + 1) for index, combo in enumerate(visible)]
    return {
        "sessionId": session_id,
        "generatedAt": _aware_utc(item.recommendations_generated_at),
        "stale": revision != item.source_revision,
        "travelObjective": item.travel_objective.value,
        "attendanceWeightPercent": item.attendance_weight_percent,
        "minimumAttendees": item.minimum_attendee_threshold,
        "isNearMatch": item.recommendations_run_status == "BEST_AVAILABLE_BELOW_THRESHOLD",
        "combinations": projected,
        "excludedCounts": dict(excluded),
    }


def confirmed_plan(db: Session, item: SchedulingSession) -> dict | None:
    if item.confirmed_combination_id is None:
        return None
    combo = db.get(Combination, item.confirmed_combination_id)
    if combo is None:
        return None
    slot = db.get(CandidateTimeslot, combo.candidate_timeslot_id)
    venue = db.get(Venue, combo.venue_id)
    attendees = []
    attendance = list(db.exec(select(TimeslotAttendance).where(TimeslotAttendance.candidate_timeslot_id == slot.timeslot_id, TimeslotAttendance.attendance_status == AttendanceStatus.AVAILABLE)).all())
    for row in attendance:
        participant = db.get(Participant, row.participant_id)
        attendees.append({"participantId": participant.participant_id, "displayName": participant.display_name})
    return {
        "combinationId": combo.combination_id,
        "venue": _venue(venue),
        "start": local_datetime(slot.start_date_time, item.timezone),
        "end": local_datetime(slot.end_date_time, item.timezone),
        "attendees": attendees,
        "confirmedAt": _aware_utc(item.confirmed_at or item.updated_at),
    }


def confirm_plan(db: Session, user: UserAccount, session_id: UUID, combination_id: UUID) -> dict:
    require_organiser(db, session_id, user)
    item = _get_session_or_404(db, session_id, lock=True)
    _ensure_active(item)
    if item.recommendations_source_revision != item.source_revision:
        raise HTTPException(409, "Recommendations are stale")
    combo = db.get(Combination, combination_id)
    if combo is None or combo.session_id != session_id:
        raise HTTPException(404, "Combination not found")
    if combo.source_revision != item.source_revision:
        raise HTTPException(409, "Recommendations are stale")
    if combo.feasibility_status != FeasibilityStatus.FEASIBLE:
        raise HTTPException(409, "Only a feasible Combination can be confirmed")
    combo.status = CombinationStatus.CONFIRMED
    item.confirmed_combination_id = combo.combination_id
    item.confirmed_at = _utcnow()
    item.updated_at = item.confirmed_at
    item.status = SessionStatus.CONFIRMED
    db.add(combo)
    db.add(item)
    _sync_confirmed_calendar_events(db, item, combo)
    db.commit()
    return session_detail(db, user, item)


def _sync_confirmed_calendar_events(db: Session, item: SchedulingSession, combo: Combination) -> None:
    holds = list(db.exec(select(CalendarEvent).where(CalendarEvent.session_id == item.session_id, CalendarEvent.event_type == EventType.TENTATIVE_HOLD)).all())
    for hold in holds:
        hold.event_status = EventStatus.DELETED
        db.add(hold)
    attendance = list(db.exec(select(TimeslotAttendance).where(TimeslotAttendance.candidate_timeslot_id == combo.candidate_timeslot_id, TimeslotAttendance.attendance_status == AttendanceStatus.AVAILABLE)).all())
    for attendee in attendance:
        connection = db.exec(select(CalendarConnection).where(CalendarConnection.participant_id == attendee.participant_id, CalendarConnection.connection_status == ConnectionStatus.CONNECTED)).first()
        if connection is None:
            continue
        db.add(
            CalendarEvent(
                calendar_connection_id=connection.connection_id,
                session_id=item.session_id,
                candidate_timeslot_id=combo.candidate_timeslot_id,
                combination_id=combo.combination_id,
                event_type=EventType.CONFIRMED_EVENT,
                event_status=EventStatus.ACTIVE if settings.use_mock_providers else EventStatus.ERROR,
                provider_event_id=(f"demo-confirmed:{combo.combination_id}:{attendee.participant_id}" if settings.use_mock_providers else None),
                last_error=(None if settings.use_mock_providers else "Google Calendar provider is not configured"),
            )
        )


def _combination_projection(db: Session, combo: Combination, fallback_rank: int) -> dict:
    slot = db.get(CandidateTimeslot, combo.candidate_timeslot_id)
    session = db.get(SchedulingSession, combo.session_id)
    venue = db.get(Venue, combo.venue_id)
    attendance_rows = list(db.exec(select(TimeslotAttendance).where(TimeslotAttendance.candidate_timeslot_id == slot.timeslot_id)).all())
    estimates = {row.participant_id: row for row in db.exec(select(TravelEstimate).where(TravelEstimate.combination_id == combo.combination_id)).all()}
    attendees, absentees, travel_values = [], [], []
    for row in attendance_rows:
        participant = db.get(Participant, row.participant_id)
        if row.attendance_status == AttendanceStatus.AVAILABLE:
            estimate = estimates.get(row.participant_id)
            minutes = estimate.travel_duration_minutes if estimate else None
            routing_status = estimate.routing_status.value if estimate else RoutingStatus.UNAVAILABLE.value
            attendees.append(
                {
                    "participantId": participant.participant_id,
                    "displayName": participant.display_name,
                    "transportMode": (estimate.transport_mode.value if estimate else _participant_mode(db, participant.participant_id)),
                    "travelMinutes": minutes,
                    "routingStatus": routing_status,
                }
            )
            if minutes is not None:
                travel_values.append(minutes)
        else:
            absentees.append(
                {
                    "participantId": participant.participant_id,
                    "displayName": participant.display_name,
                    "attendanceStatus": row.attendance_status.value,
                }
            )
    complete = len(travel_values) == len(attendees) and bool(attendees)
    total = sum(travel_values) if complete else None
    maximum = max(travel_values) if complete else None
    average = total / len(travel_values) if complete else None
    explanation = (
        f"{combo.attendee_count} attending; "
        + (f"longest journey {maximum} min" if session.travel_objective.value == "MIN_MAX_INDIVIDUAL" and maximum is not None else f"total travel {total} min" if total is not None else "some travel times unavailable")
        + f"; attendance weighted {session.attendance_weight_percent}%"
    )
    return {
        "combinationId": combo.combination_id,
        "rank": combo.rank or fallback_rank,
        "venue": _venue(venue),
        "start": local_datetime(slot.start_date_time, session.timezone),
        "end": local_datetime(slot.end_date_time, session.timezone),
        "feasibilityStatus": combo.feasibility_status.value,
        "attendeeCount": combo.attendee_count,
        "meetsRequestedMinimum": combo.attendee_count >= session.minimum_attendee_threshold,
        "combinedScore": round((combo.combined_score or 0) * 100, 1),
        "attendanceScore": round((combo.attendance_score or 0) * 100, 1),
        "travelScore": round((combo.travel_score or 0) * 100, 1),
        "totalTravelMinutes": total,
        "averageTravelMinutes": average,
        "maxTravelMinutes": maximum,
        "explanation": explanation,
        "attendees": attendees,
        "absentees": absentees,
    }


def _response_projection(participant: Participant, record: AvailabilityRecord, intervals: list[AvailabilityInterval]) -> dict:
    return {
        "participantId": participant.participant_id,
        "responseStatus": participant.response_status.value,
        "record": {
            "recordStatus": record.record_status.value,
            "submissionSource": record.submission_source.value,
            "transportMode": record.transport_mode.value,
            "location": {
                "inputType": record.location_input_type.value,
                "input": record.location_input,
                "label": record.location_input,
                "geocodeStatus": record.geocode_status.value,
            },
            "intervals": [
                {
                    "start": row.start_date_time,
                    "end": row.end_date_time,
                    "type": row.interval_type.value,
                    "source": row.interval_source.value,
                }
                for row in intervals
            ],
            "submittedAt": _aware_utc(record.submitted_at),
            "withdrawnAt": _aware_utc(record.withdrawn_at) if record.withdrawn_at else None,
        },
    }


def _participant_mode(db: Session, participant_id: UUID) -> str:
    record = AvailabilityRepository(db).current(participant_id)
    return record.transport_mode.value if record else "PUBLIC_TRANSPORT"


def _venue(venue: Venue) -> dict:
    source_label = (
        "Sport Singapore via data.gov.sg"
        if venue.data_source == "DATA_GOV_SG_SPORT_FACILITIES"
        else "Demo catalogue"
        if venue.data_source == "DEMO"
        else venue.data_source
    )
    return {
        "id": venue.venue_id,
        "name": venue.name,
        "category": venue.category.value,
        "address": venue.address,
        "latitude": venue.latitude,
        "longitude": venue.longitude,
        "dataSource": source_label,
        "lastUpdated": (
            _aware_utc(venue.last_synced_at) if venue.last_synced_at else None
        ),
    }


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

