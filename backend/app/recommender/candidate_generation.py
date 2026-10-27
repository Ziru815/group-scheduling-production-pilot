"""Candidate Generation (SRS Section 4.3, FR-C1 to FR-C6)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, time, timedelta

from app.recommender.config import RecommenderConfig
from app.recommender.geo import centroid, haversine_km
from app.recommender.types import (
    AttendanceStatus,
    CandidateTimeslot,
    Coordinates,
    Interval,
    IntervalType,
    ParticipantInput,
    RecordStatus,
    SessionInput,
    ShortlistEntry,
    VenueInput,
)

# --------------------------------------------------------------------------
# FR-C1  Timeslot enumeration
# --------------------------------------------------------------------------


def validate_session(session: SessionInput, config: RecommenderConfig) -> None:
    """Reject Session parameters the engine cannot work with (FR-A1.1, B.3.2)."""
    if session.date_range_start.tzinfo is None or session.date_range_end.tzinfo is None:
        raise ValueError("Session date range must be timezone-aware (SRS Section 6)")
    if not session.date_range_start < session.date_range_end:
        raise ValueError("DateRangeStart must be earlier than DateRangeEnd")
    if not (config.min_duration_minutes <= session.duration_minutes <= config.max_duration_minutes):
        raise ValueError(
            f"duration must be {config.min_duration_minutes} to "
            f"{config.max_duration_minutes} minutes (FR-A1.1)"
        )
    if session.minimum_attendee_threshold is not None and session.minimum_attendee_threshold < 1:
        raise ValueError("Minimum-Attendee Threshold must be positive")
    if not 0 <= session.attendance_weight_percent <= 100:
        raise ValueError("attendance weight must be between 0 and 100")


def enumerate_timeslots(
    start: datetime,
    end: datetime,
    duration_minutes: int,
    step_minutes: int,
) -> list[tuple[datetime, datetime]]:
    """Every (start, end) of the given duration that fits inside [start, end] (FR-C1).

    Start times are ``start``, ``start + step``, ``start + 2*step`` and so on;
    a slot is kept only if it ends no later than ``end``.
    """
    duration = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=step_minutes)
    slots: list[tuple[datetime, datetime]] = []

    # The integrated frontend captures a date range plus a daily start/end
    # window.  Those values are stored as the first day's start and the last
    # day's end.  Enumerating each daily window avoids creating overnight
    # candidates between those two boundaries.
    if start.date() != end.date() and (end.hour, end.minute, end.second) > (start.hour, start.minute, start.second):
        day = start.date()
        start_wall = time(start.hour, start.minute, start.second, tzinfo=start.tzinfo)
        end_wall = time(end.hour, end.minute, end.second, tzinfo=end.tzinfo)
        while day <= end.date():
            window_start = datetime.combine(day, start_wall)
            window_end = datetime.combine(day, end_wall)
            t = window_start
            while t + duration <= window_end:
                slots.append((t, t + duration))
                t += step
            day += timedelta(days=1)
        return slots

    t = start
    while t + duration <= end:
        slots.append((t, t + duration))
        t += step
    return slots


# --------------------------------------------------------------------------
# FR-C2  Attendance per Timeslot
# --------------------------------------------------------------------------


def _merge(intervals: Iterable[Interval]) -> list[tuple[datetime, datetime]]:
    """Merge overlapping or touching intervals into disjoint blocks."""
    spans = sorted((i.start, i.end) for i in intervals)
    merged: list[tuple[datetime, datetime]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            if e > merged[-1][1]:
                merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


class _ParticipantAvailability:
    """Pre-merged AVAILABLE and BUSY blocks for one Participant."""

    def __init__(self, participant: ParticipantInput) -> None:
        self.participant = participant
        self.available = _merge(i for i in participant.intervals if i.type is IntervalType.AVAILABLE)
        self.busy = _merge(i for i in participant.intervals if i.type is IntervalType.BUSY)

    def status_for(self, start: datetime, end: datetime) -> AttendanceStatus:
        p = self.participant
        if p.record_status is None:
            return AttendanceStatus.NO_RESPONSE
        if p.record_status is RecordStatus.WITHDRAWN:
            return AttendanceStatus.WITHDRAWN
        # A BUSY block (e.g. imported from Google Calendar, FR-B8) that overlaps
        # any part of the slot makes the Participant unavailable for it.
        if any(bs < end and start < be for bs, be in self.busy):
            return AttendanceStatus.UNAVAILABLE
        # The slot must lie wholly inside one merged AVAILABLE block.
        if any(as_ <= start and end <= ae for as_, ae in self.available):
            return AttendanceStatus.AVAILABLE
        return AttendanceStatus.UNAVAILABLE


def compute_attendance(
    slots: Sequence[tuple[datetime, datetime]],
    participants: Sequence[ParticipantInput],
) -> list[CandidateTimeslot]:
    """Attendance status of every Participant for every Timeslot (FR-C2, B.3.10).

    NO_RESPONSE and WITHDRAWN are kept distinct from UNAVAILABLE (SRS 5.5).
    """
    prepared = [_ParticipantAvailability(p) for p in participants]
    result: list[CandidateTimeslot] = []
    for index, (start, end) in enumerate(slots):
        attendance = {pa.participant.participant_id: pa.status_for(start, end) for pa in prepared}
        result.append(CandidateTimeslot(index=index, start=start, end=end, attendance=attendance))
    return result


# --------------------------------------------------------------------------
# FR-C3  Venue filtering by activity type
# --------------------------------------------------------------------------


def filter_venues(venues: Iterable[VenueInput], activity_type_id: str) -> list[VenueInput]:
    """Venues that support the Session's Activity Type (FR-C3)."""
    return [v for v in venues if activity_type_id in v.supported_activity_type_ids]


# --------------------------------------------------------------------------
# FR-C4  Centroid and nearest-N shortlist
# --------------------------------------------------------------------------


def participant_centroid(participants: Iterable[ParticipantInput]) -> Coordinates | None:
    """Centroid of valid starting locations on active Availability Records (B.4)."""
    points = [p.location for p in participants if p.is_active and p.has_valid_location]
    return centroid(points)  # type: ignore[arg-type]


def shortlist_venues(
    venues: Sequence[VenueInput],
    centre: Coordinates,
    n: int,
) -> list[ShortlistEntry]:
    """The ``n`` Venues nearest ``centre`` by straight-line distance (FR-C4, C8).

    Ties on distance are broken by VenueID so the shortlist is deterministic.
    The Venue Category tag (FR-C5) and group-size / booking-window data
    (FR-C6) travel with each VenueInput.
    """
    ranked = sorted(venues, key=lambda v: (haversine_km(centre, v.location), v.venue_id))
    return [
        ShortlistEntry(venue=v, straight_line_distance_km=haversine_km(centre, v.location), rank=i + 1)
        for i, v in enumerate(ranked[:n])
    ]
