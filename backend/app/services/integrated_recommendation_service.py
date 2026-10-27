"""Bridge the standalone recommendation engine to SQLModel persistence.

The engine remains free of HTTP and database code.  This service takes a
consistent database snapshot, runs the engine through a provider port, checks
the Session revision again (NFR-11), and only then persists the derived rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.adapters.mock import MockRouter
from app.adapters.onemap import OneMapAdapter as EngineOneMapAdapter
from app.core.config import settings
from app.models import (
    AttendanceSource,
    AvailabilityRecord,
    CalendarConnection,
    CalendarEvent,
    CandidateTimeslot,
    Combination,
    CombinationStatus,
    ConnectionStatus,
    EventStatus,
    EventType,
    GenerationStatus,
    IntervalSource,
    Participant,
    RecordStatus,
    ResponseStatus,
    RoutingStatus,
    SchedulingSession,
    ShortlistStatus,
    TimeslotAttendance,
    TravelEstimate,
    UserAccount,
    VenueActivity,
    VenueShortlistEntry,
)
from app.repositories import AvailabilityRepository, ParticipantRepository, RecommendationRepository, VenueRepository
from app.recommender.config import RecommenderConfig
from app.recommender.engine import RecommendationEngine
from app.recommender.types import (
    Coordinates,
    GeocodeStatus as EngineGeocodeStatus,
    Interval,
    IntervalType as EngineIntervalType,
    ParticipantInput,
    RecommendationRequest,
    RecordStatus as EngineRecordStatus,
    RoutingStatus as EngineRoutingStatus,
    SessionInput,
    TransportMode as EngineTransportMode,
    TravelObjective as EngineTravelObjective,
    VenueCategory as EngineVenueCategory,
    VenueInput,
)
from app.services.application_services import _as_utc, _ensure_active, _get_session_or_404
from app.services.authorization_service import require_organiser


def _engine_config() -> RecommenderConfig:
    return RecommenderConfig(
        max_journey_minutes=settings.default_journey_cap_minutes,
        shortlist_size=settings.default_shortlist_size,
        default_minimum_attendee_threshold=settings.default_minimum_attendees,
        timeslot_step_minutes=settings.default_timeslot_step_minutes,
    )


def _provider():
    if settings.use_mock_providers:
        return MockRouter()
    base_url = settings.onemap_base_url.rstrip("/")
    if base_url.endswith("/api"):
        base_url = base_url[:-4]
    return EngineOneMapAdapter(
        email=settings.onemap_email,
        password=settings.onemap_password,
        token=settings.onemap_token,
        base_url=base_url,
    )


class IntegratedRecommendationService:
    @staticmethod
    async def generate(db: Session, user: UserAccount, session_id: UUID):
        require_organiser(db, session_id, user)
        item = _get_session_or_404(db, session_id)
        _ensure_active(item)
        snapshot_revision = item.source_revision
        request = _build_request(db, item)
        provider = _provider()
        engine = RecommendationEngine(provider, _engine_config())
        try:
            result = await engine.generate(request)
        finally:
            close = getattr(provider, "aclose", None)
            if close is not None:
                await close()

        # External routing calls may take time.  Re-read the Session after they
        # finish so a completed withdrawal or edit invalidates this run.
        db.expire_all()
        item = _get_session_or_404(db, session_id)
        if item.source_revision != snapshot_revision:
            db.rollback()
            raise HTTPException(409, "Recommendations became stale while they were generated")

        _persist_result(db, item, result)
        item.recommendations_source_revision = snapshot_revision
        item.recommendations_run_status = result.status.value
        item.recommendations_generated_at = result.generated_at
        db.add(item)
        db.commit()
        return result


def _build_request(db: Session, item: SchedulingSession) -> RecommendationRequest:
    participants = ParticipantRepository(db).for_session(item.session_id)
    availability = AvailabilityRepository(db)
    participant_inputs: list[ParticipantInput] = []
    for participant in participants:
        record = availability.current(participant.participant_id)
        if participant.response_status == ResponseStatus.WITHDRAWN:
            record_status = EngineRecordStatus.WITHDRAWN
        elif record is None:
            record_status = None
        else:
            record_status = EngineRecordStatus.ACTIVE
        intervals: tuple[Interval, ...] = ()
        location = None
        geocode = EngineGeocodeStatus.PENDING
        mode = EngineTransportMode.PUBLIC_TRANSPORT
        if record is not None:
            intervals = tuple(
                Interval(
                    start=_aware(row.start_date_time),
                    end=_aware(row.end_date_time),
                    type=EngineIntervalType(row.interval_type.value),
                )
                for row in availability.intervals(record.record_id)
            )
            if record.latitude is not None and record.longitude is not None:
                location = Coordinates(record.latitude, record.longitude)
            geocode = EngineGeocodeStatus(record.geocode_status.value)
            mode = EngineTransportMode(record.transport_mode.value)
        participant_inputs.append(
            ParticipantInput(
                participant_id=str(participant.participant_id),
                display_name=participant.display_name,
                record_status=record_status,
                intervals=intervals,
                location=location,
                geocode_status=geocode,
                transport_mode=mode,
            )
        )

    venues = VenueRepository(db).supported_for_activity(
        item.activity_type_id,
        require_verified=not settings.use_mock_providers,
    )
    venue_inputs = tuple(
        VenueInput(
            venue_id=str(venue.venue_id),
            name=venue.name,
            category=EngineVenueCategory(venue.category.value),
            location=Coordinates(venue.latitude, venue.longitude),
            supported_activity_type_ids=frozenset({str(item.activity_type_id)}),
            address=venue.address,
            min_group_size=venue.minimum_group_size,
            optimal_group_size=venue.optimal_group_size,
            advance_booking_lead_minutes=venue.advance_booking_lead_minutes,
        )
        for venue in venues
    )
    return RecommendationRequest(
        session=SessionInput(
            session_id=str(item.session_id),
            activity_type_id=str(item.activity_type_id),
            date_range_start=_aware(item.date_range_start),
            date_range_end=_aware(item.date_range_end),
            duration_minutes=item.duration_minutes,
            minimum_attendee_threshold=item.minimum_attendee_threshold,
            travel_objective=EngineTravelObjective(item.travel_objective.value),
            attendance_weight_percent=item.attendance_weight_percent,
            timezone=item.timezone,
        ),
        participants=tuple(participant_inputs),
        venues=venue_inputs,
        now=datetime.now(timezone.utc),
    )


def _persist_result(db: Session, item: SchedulingSession, result) -> None:
    repo = RecommendationRepository(db)
    # Candidate Timeslots are unique by Session and time window. Replace the
    # previous recommendation snapshot as one unit before persisting a new
    # revision; otherwise a legitimate re-run collides with the old slots.
    repo.delete_all(item.session_id)

    participant_ids = {
        str(row.participant_id): row.participant_id
        for row in ParticipantRepository(db).for_session(item.session_id)
    }
    slot_rows: dict[int, CandidateTimeslot] = {}
    rows: list[object] = []
    for slot in result.timeslots:
        slot_row = CandidateTimeslot(
            session_id=item.session_id,
            start_date_time=slot.start,
            end_date_time=slot.end,
            generation_status=GenerationStatus.GENERATED,
            available_count=slot.available_count,
            source_revision=item.source_revision,
        )
        slot_rows[slot.index] = slot_row
        rows.append(slot_row)
        rows.extend(
            TimeslotAttendance(
                candidate_timeslot_id=slot_row.timeslot_id,
                participant_id=participant_ids[participant_id],
                attendance_status=status.value,
                source=AttendanceSource.NONE if status.value in {"NO_RESPONSE", "WITHDRAWN"} else AttendanceSource.MANUAL,
            )
            for participant_id, status in slot.attendance.items()
        )

    for entry in result.shortlist:
        rows.append(
            VenueShortlistEntry(
                session_id=item.session_id,
                venue_id=UUID(entry.venue.venue_id),
                centroid_latitude=result.centroid.lat,
                centroid_longitude=result.centroid.lng,
                straight_line_distance_km=entry.straight_line_distance_km,
                shortlist_rank=entry.rank,
                shortlist_status=ShortlistStatus.CURRENT,
                source_revision=item.source_revision,
            )
        )
    repo.add_all(rows)

    persisted_combinations: list[tuple[object, Combination]] = []
    for combo in result.combinations:
        row = Combination(
            session_id=item.session_id,
            candidate_timeslot_id=slot_rows[combo.timeslot.index].timeslot_id,
            venue_id=UUID(combo.venue.venue_id),
            attendee_count=combo.attendee_count,
            feasibility_status=combo.feasibility.value,
            exclusion_reason=combo.exclusion_reason.value if combo.exclusion_reason else None,
            attendance_score=combo.attendance_score,
            travel_score=combo.travel_score,
            combined_score=combo.combined_score,
            rank=combo.rank,
            status=(CombinationStatus.EXCLUDED if combo.exclusion_reason else CombinationStatus.CANDIDATE),
            source_revision=item.source_revision,
        )
        db.add(row)
        persisted_combinations.append((combo, row))
    db.flush()

    for combo, row in persisted_combinations:
        for estimate in combo.travel:
            db.add(
                TravelEstimate(
                    combination_id=row.combination_id,
                    participant_id=participant_ids[estimate.participant_id],
                    transport_mode=estimate.transport_mode.value,
                    travel_duration_minutes=estimate.minutes,
                    routing_status=estimate.status.value,
                    journey_limit_exceeded=estimate.journey_limit_exceeded,
                    provider="DEMO_DISTANCE" if settings.use_mock_providers else "OneMap",
                    request_time=result.generated_at,
                    source_revision=item.source_revision,
                )
            )

    _replace_tentative_holds(db, item, result, slot_rows)


def _replace_tentative_holds(db: Session, item: SchedulingSession, result, slot_rows) -> None:
    old_holds = list(
        db.exec(
            select(CalendarEvent).where(
                CalendarEvent.session_id == item.session_id,
                CalendarEvent.event_type == EventType.TENTATIVE_HOLD,
                CalendarEvent.event_status.in_([EventStatus.PENDING, EventStatus.ACTIVE]),
            )
        ).all()
    )
    for event in old_holds:
        event.event_status = EventStatus.DELETED
        db.add(event)

    eligible_indexes = {
        combo.timeslot.index
        for combo in result.combinations
        if combo.exclusion_reason is None
    }
    connections = list(
        db.exec(
            select(CalendarConnection)
            .join(Participant, Participant.participant_id == CalendarConnection.participant_id)
            .where(
                Participant.session_id == item.session_id,
                CalendarConnection.connection_status == ConnectionStatus.CONNECTED,
            )
        ).all()
    )
    for connection in connections:
        for index in eligible_indexes:
            slot = slot_rows[index]
            db.add(
                CalendarEvent(
                    calendar_connection_id=connection.connection_id,
                    session_id=item.session_id,
                    candidate_timeslot_id=slot.timeslot_id,
                    event_type=EventType.TENTATIVE_HOLD,
                    event_status=EventStatus.ACTIVE if settings.use_mock_providers else EventStatus.ERROR,
                    provider_event_id=(f"demo-hold:{item.session_id}:{slot.timeslot_id}" if settings.use_mock_providers else None),
                    last_error=(None if settings.use_mock_providers else "Google Calendar provider is not configured"),
                )
            )


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

