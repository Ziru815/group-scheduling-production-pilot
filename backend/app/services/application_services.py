"""Transactional application services for the main use cases."""
from datetime import datetime, timezone
from secrets import token_urlsafe
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import (
    ActivityType, AttendanceSource, AttendanceStatus, AvailabilityInterval,
    AvailabilityRecord, CandidateTimeslot, Combination, CombinationStatus,
    FeasibilityStatus, GenerationStatus, GeocodeStatus, IntervalSource,
    IntervalType, Participant, ParticipantRole, RecordStatus, ResponseStatus,
    SchedulingSession, SessionStatus, ShortlistStatus, TimeslotAttendance,
    TravelEstimate, UserAccount, Venue, VenueShortlistEntry,
)
from app.repositories import AvailabilityRepository, ParticipantRepository, RecommendationRepository, SessionRepository, VenueRepository
from app.schemas import AvailabilityIntervalInput, AvailabilityOwn, AvailabilitySubmit, GenerateResult, RankedCombination, SessionCreate, SessionUpdate
from app.services.authorization_service import require_member, require_organiser
from app.services.domain_rules import attendance_score, combined_score, enumerate_timeslots, haversine_km, interval_covers, travel_score


def _utcnow(): return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """SQLite drops timezone metadata; PostgreSQL preserves it."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _get_session_or_404(db: Session, session_id: UUID, lock: bool = False) -> SchedulingSession:
    item = db.exec(select(SchedulingSession).where(SchedulingSession.session_id == session_id).with_for_update()).first() if lock else db.get(SchedulingSession, session_id)
    if item is None: raise HTTPException(404, "Session not found")
    return item


def _ensure_active(item: SchedulingSession) -> None:
    if item.status != SessionStatus.ACTIVE: raise HTTPException(409, "Session is not active")


def _bump_revision(item: SchedulingSession) -> None:
    item.source_revision += 1
    item.updated_at = _utcnow()


class SessionService:
    @staticmethod
    def create(db: Session, user: UserAccount, data: SessionCreate) -> SchedulingSession:
        if db.get(ActivityType, data.activity_type_id) is None: raise HTTPException(422, "Unknown activity type")
        item = SchedulingSession(**data.model_dump(), invitation_token=token_urlsafe(24))
        participant = Participant(user_account_id=user.account_id, session_id=item.session_id, display_name=user.display_name, role=ParticipantRole.ORGANISER)
        item.organiser_participant_id = participant.participant_id
        db.add(item); db.add(participant)
        try: db.commit()
        except IntegrityError as exc: db.rollback(); raise HTTPException(409, "Could not create session") from exc
        db.refresh(item)
        return item

    @staticmethod
    def list_for_user(db: Session, user: UserAccount): return SessionRepository(db).for_user(user.account_id)

    @staticmethod
    def get(db: Session, user: UserAccount, session_id: UUID): require_member(db, session_id, user); return _get_session_or_404(db, session_id)

    @staticmethod
    def join(db: Session, user: UserAccount, invitation_token: str) -> Participant:
        item = SessionRepository(db).by_token(invitation_token)
        if item is None: raise HTTPException(404, "Invitation is invalid")
        _ensure_active(item)
        existing = ParticipantRepository(db).membership(item.session_id, user.account_id)
        if existing: return existing
        count = len(ParticipantRepository(db).for_session(item.session_id))
        if count >= settings.default_participant_limit: raise HTTPException(409, "Participant limit reached")
        participant = Participant(user_account_id=user.account_id, session_id=item.session_id, display_name=user.display_name)
        db.add(participant)
        try: db.commit()
        except IntegrityError:
            db.rollback()
            return ParticipantRepository(db).membership(item.session_id, user.account_id)
        db.refresh(participant); return participant

    @staticmethod
    def update(db: Session, user: UserAccount, session_id: UUID, data: SessionUpdate):
        require_organiser(db, session_id, user); item = _get_session_or_404(db, session_id, lock=True); _ensure_active(item)
        values = data.model_dump(exclude_none=True)
        for key, value in values.items(): setattr(item, key, value)
        if item.date_range_start >= item.date_range_end or item.response_deadline >= item.date_range_start:
            raise HTTPException(422, "Invalid date range or response deadline")
        _bump_revision(item); RecommendationRepository(db).invalidate(session_id)
        db.add(item); db.commit(); db.refresh(item); return item

    @staticmethod
    def cancel(db: Session, user: UserAccount, session_id: UUID):
        require_organiser(db, session_id, user); item = _get_session_or_404(db, session_id, lock=True)
        if item.status == SessionStatus.CONFIRMED: raise HTTPException(409, "Confirmed session cannot be cancelled without an explicit change workflow")
        item.status = SessionStatus.CANCELLED; _bump_revision(item); db.add(item); db.commit(); return item


class AvailabilityService:
    @staticmethod
    def _validate_intervals(item: SchedulingSession, intervals: list[AvailabilityIntervalInput]):
        ordered = sorted(intervals, key=lambda value: value.start_date_time)
        for interval in ordered:
            if _as_utc(interval.start_date_time) < _as_utc(item.date_range_start) or _as_utc(interval.end_date_time) > _as_utc(item.date_range_end):
                raise HTTPException(422, "Availability must be inside the session date range")
        for previous, current in zip(ordered, ordered[1:]):
            if current.start_date_time < previous.end_date_time: raise HTTPException(422, "Availability intervals cannot overlap")
        return ordered

    @classmethod
    def submit(cls, db: Session, user: UserAccount, session_id: UUID, data: AvailabilitySubmit) -> AvailabilityOwn:
        participant = require_member(db, session_id, user); item = _get_session_or_404(db, session_id, lock=True); _ensure_active(item)
        if _utcnow() > _as_utc(item.response_deadline): raise HTTPException(409, "Response deadline has passed")
        intervals = cls._validate_intervals(item, data.intervals)
        repo = AvailabilityRepository(db); previous = repo.current(participant.participant_id)
        next_revision = (previous.source_revision + 1) if previous else 1
        if previous:
            previous.record_status = RecordStatus.WITHDRAWN; previous.withdrawn_at = _utcnow(); db.add(previous)
        record = AvailabilityRecord(participant_id=participant.participant_id, **data.model_dump(exclude={"intervals"}), geocode_status=GeocodeStatus.PENDING, submitted_at=_utcnow(), source_revision=next_revision)
        db.add(record); db.flush()
        rows = [AvailabilityInterval(availability_record_id=record.record_id, start_date_time=i.start_date_time, end_date_time=i.end_date_time, interval_type=IntervalType.AVAILABLE, interval_source=IntervalSource.MANUAL) for i in intervals]
        db.add_all(rows); participant.response_status = ResponseStatus.SUBMITTED; _bump_revision(item); RecommendationRepository(db).invalidate(session_id)
        db.add(participant); db.add(item); db.commit(); db.refresh(record)
        return AvailabilityOwn.model_validate({**record.model_dump(), "intervals": intervals})

    @staticmethod
    def get_own(db: Session, user: UserAccount, session_id: UUID) -> AvailabilityOwn:
        participant = require_member(db, session_id, user); repo = AvailabilityRepository(db); record = repo.current(participant.participant_id)
        if record is None: raise HTTPException(404, "No active response")
        intervals = [AvailabilityIntervalInput(start_date_time=i.start_date_time, end_date_time=i.end_date_time) for i in repo.intervals(record.record_id)]
        return AvailabilityOwn.model_validate({**record.model_dump(), "intervals": intervals})

    @staticmethod
    def withdraw(db: Session, user: UserAccount, session_id: UUID):
        participant = require_member(db, session_id, user); item = _get_session_or_404(db, session_id, lock=True); _ensure_active(item)
        record = AvailabilityRepository(db).current(participant.participant_id)
        if record is None: raise HTTPException(404, "No active response")
        record.record_status = RecordStatus.WITHDRAWN; record.withdrawn_at = _utcnow(); participant.response_status = ResponseStatus.WITHDRAWN
        _bump_revision(item); RecommendationRepository(db).invalidate(session_id)
        db.add(record); db.add(participant); db.add(item); db.commit()


class RecommendationService:
    @staticmethod
    def generate(db: Session, user: UserAccount, session_id: UUID) -> GenerateResult:
        require_organiser(db, session_id, user); item = _get_session_or_404(db, session_id, lock=True); _ensure_active(item)
        snapshot_revision = item.source_revision
        repo = RecommendationRepository(db); repo.delete_revision(session_id, snapshot_revision)
        participants = ParticipantRepository(db).for_session(session_id)
        availability_repo = AvailabilityRepository(db)
        records = {record.participant_id: record for record in availability_repo.active_for_session(session_id)}
        interval_map = {pid: availability_repo.intervals(record.record_id) for pid, record in records.items()}
        slots, attendance_rows = [], []
        for start, end in enumerate_timeslots(item.date_range_start, item.date_range_end, item.duration_minutes, settings.default_timeslot_step_minutes):
            slot = CandidateTimeslot(session_id=session_id, start_date_time=start, end_date_time=end, source_revision=snapshot_revision)
            for participant in participants:
                if participant.response_status == ResponseStatus.WITHDRAWN: status, source = AttendanceStatus.WITHDRAWN, AttendanceSource.NONE
                elif participant.response_status == ResponseStatus.NOT_SUBMITTED: status, source = AttendanceStatus.NO_RESPONSE, AttendanceSource.NONE
                else:
                    available = any(interval_covers(interval.start_date_time, interval.end_date_time, start, end) for interval in interval_map.get(participant.participant_id, []))
                    status, source = (AttendanceStatus.AVAILABLE if available else AttendanceStatus.UNAVAILABLE), AttendanceSource.MANUAL
                if status == AttendanceStatus.AVAILABLE: slot.available_count += 1
                attendance_rows.append(TimeslotAttendance(candidate_timeslot_id=slot.timeslot_id, participant_id=participant.participant_id, attendance_status=status, source=source))
            slots.append(slot)
        valid_origins = [(r.latitude, r.longitude) for r in records.values() if r.geocode_status == GeocodeStatus.VALID and r.latitude is not None and r.longitude is not None]
        shortlist = []
        if valid_origins:
            centre_lat = sum(v[0] for v in valid_origins) / len(valid_origins); centre_lon = sum(v[1] for v in valid_origins) / len(valid_origins)
            venues = VenueRepository(db).supported_for_activity(item.activity_type_id)
            ranked_venues = sorted(venues, key=lambda v: (haversine_km(centre_lat, centre_lon, v.latitude, v.longitude), str(v.venue_id)))[:settings.default_shortlist_size]
            for rank, venue in enumerate(ranked_venues, 1):
                shortlist.append(VenueShortlistEntry(session_id=session_id, venue_id=venue.venue_id, centroid_latitude=centre_lat, centroid_longitude=centre_lon, straight_line_distance_km=haversine_km(centre_lat, centre_lon, venue.latitude, venue.longitude), shortlist_rank=rank, source_revision=snapshot_revision))
        combinations = []
        venue_by_id = {venue.venue_id: venue for venue in VenueRepository(db).supported_for_activity(item.activity_type_id)}
        for slot in slots:
            if slot.available_count < item.minimum_attendee_threshold: continue
            for entry in shortlist:
                venue = venue_by_id[entry.venue_id]
                feasibility, reason = FeasibilityStatus.DATA_UNAVAILABLE, "ROUTING_NOT_CALCULATED"
                if venue.minimum_group_size is None or venue.advance_booking_lead_minutes is None:
                    reason = "VENUE_CONSTRAINTS_UNKNOWN"
                elif slot.available_count < venue.minimum_group_size:
                    feasibility, reason = FeasibilityStatus.EXCLUDED, "MINIMUM_GROUP_SIZE"
                elif (_as_utc(slot.start_date_time) - _utcnow()).total_seconds() / 60 < venue.advance_booking_lead_minutes:
                    feasibility, reason = FeasibilityStatus.EXCLUDED, "INSUFFICIENT_BOOKING_LEAD"
                combinations.append(Combination(session_id=session_id, candidate_timeslot_id=slot.timeslot_id, venue_id=entry.venue_id, attendee_count=slot.available_count, feasibility_status=feasibility, exclusion_reason=reason, status=CombinationStatus.EXCLUDED if feasibility == FeasibilityStatus.EXCLUDED else CombinationStatus.CANDIDATE, source_revision=snapshot_revision))
        if item.source_revision != snapshot_revision: raise HTTPException(409, "Session changed during generation; retry")
        repo.add_all([*slots, *attendance_rows, *shortlist, *combinations]); db.commit()
        return GenerateResult(source_revision=snapshot_revision, timeslots_created=len(slots), shortlist_created=len(shortlist), combinations_created=len(combinations), data_unavailable_count=len(combinations))

    @staticmethod
    def rescore(db: Session, user: UserAccount, session_id: UUID):
        require_organiser(db, session_id, user); item = _get_session_or_404(db, session_id, lock=True); _ensure_active(item)
        participants_count = len(ParticipantRepository(db).for_session(session_id))
        combos = list(db.exec(select(Combination).where(Combination.session_id == session_id, Combination.source_revision == item.source_revision)).all())
        raw_burden, slot_start = {}, {}
        for combo in combos:
            estimates = list(db.exec(select(TravelEstimate).where(TravelEstimate.combination_id == combo.combination_id, TravelEstimate.source_revision == item.source_revision)).all())
            values = [e.travel_duration_minutes for e in estimates if e.routing_status == "AVAILABLE" and e.travel_duration_minutes is not None]
            a_score = attendance_score(combo.attendee_count, participants_count)
            t_score = travel_score(values, combo.attendee_count, settings.default_journey_cap_minutes, item.travel_objective)
            if len(values) == combo.attendee_count and any(value > settings.default_journey_cap_minutes for value in values):
                combo.feasibility_status = FeasibilityStatus.EXCLUDED; combo.status = CombinationStatus.EXCLUDED; combo.exclusion_reason = "JOURNEY_LIMIT_EXCEEDED"; combo.attendance_score = a_score; combo.travel_score = None; combo.combined_score = None
            elif t_score is None:
                combo.feasibility_status = FeasibilityStatus.DATA_UNAVAILABLE; combo.exclusion_reason = "ROUTING_INCOMPLETE"; combo.attendance_score = a_score; combo.travel_score = None; combo.combined_score = None
            else:
                combo.attendance_score = a_score; combo.travel_score = t_score; combo.combined_score = combined_score(a_score, t_score, item.attendance_weight_percent, item.travel_weight_percent); combo.feasibility_status = FeasibilityStatus.FEASIBLE; combo.exclusion_reason = None
                raw_burden[combo.combination_id] = sum(values) if item.travel_objective == "MIN_TOTAL" else max(values)
            slot_start[combo.combination_id] = db.get(CandidateTimeslot, combo.candidate_timeslot_id).start_date_time
            db.add(combo)
        feasible = [c for c in combos if c.feasibility_status == FeasibilityStatus.FEASIBLE]
        feasible.sort(key=lambda c: (-(c.combined_score or 0), raw_burden[c.combination_id], -c.attendee_count, slot_start[c.combination_id], str(c.venue_id)))
        for rank, combo in enumerate(feasible, 1): combo.rank = rank; db.add(combo)
        db.commit(); return len(feasible)

    @staticmethod
    def list_ranked(db: Session, user: UserAccount, session_id: UUID) -> list[RankedCombination]:
        require_member(db, session_id, user); item = _get_session_or_404(db, session_id)
        rows = db.exec(select(Combination, CandidateTimeslot, Venue).join(CandidateTimeslot, CandidateTimeslot.timeslot_id == Combination.candidate_timeslot_id).join(Venue, Venue.venue_id == Combination.venue_id).where(Combination.session_id == session_id).order_by(col(Combination.source_revision).desc(), col(Combination.rank).asc())).all()
        return [RankedCombination(combination_id=c.combination_id, start_date_time=t.start_date_time, end_date_time=t.end_date_time, venue_id=v.venue_id, venue_name=v.name, venue_address=v.address, attendee_count=c.attendee_count, feasibility_status=c.feasibility_status, exclusion_reason=c.exclusion_reason, attendance_score=c.attendance_score, travel_score=c.travel_score, combined_score=c.combined_score, rank=c.rank, outdated=c.source_revision != item.source_revision) for c, t, v in rows]

    @staticmethod
    def confirm(db: Session, user: UserAccount, session_id: UUID, combination_id: UUID, expected_revision: int):
        require_organiser(db, session_id, user); item = _get_session_or_404(db, session_id, lock=True); _ensure_active(item)
        if item.source_revision != expected_revision: raise HTTPException(409, "Recommendations are stale; regenerate before confirming")
        combo = db.get(Combination, combination_id)
        if combo is None or combo.session_id != session_id: raise HTTPException(404, "Combination not found")
        if combo.source_revision != item.source_revision or combo.feasibility_status != FeasibilityStatus.FEASIBLE: raise HTTPException(409, "Only a current feasible combination can be confirmed")
        combo.status = CombinationStatus.CONFIRMED; item.confirmed_combination_id = combo.combination_id; item.status = SessionStatus.CONFIRMED
        db.add(combo); db.add(item); db.commit(); return combo

