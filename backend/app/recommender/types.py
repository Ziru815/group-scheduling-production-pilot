"""Input and output types for the recommendation engine.

These are plain dataclasses, deliberately independent of the SQLModel
entities in ``app/models`` (Person 2). The service layer maps database rows
onto ``RecommendationRequest`` before a run and maps ``RecommendationResult``
back onto CandidateTimeslot / TimeslotAttendance / VenueShortlistEntry /
Combination / TravelEstimate rows afterwards (SRS Appendix B.3.9 to B.3.13).

Keeping the engine free of database and HTTP code is what lets it be tested
in isolation and lets either side change without touching the other
(SRS C6, C7, NFR-15, NFR-16).

Enum values match the permitted values in SRS Appendix B.3 exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# --------------------------------------------------------------------------
# Enumerations (SRS Appendix B.3)
# --------------------------------------------------------------------------


class TransportMode(str, Enum):
    WALK = "WALK"
    DRIVE = "DRIVE"
    PUBLIC_TRANSPORT = "PUBLIC_TRANSPORT"


class TravelObjective(str, Enum):
    MIN_TOTAL = "MIN_TOTAL"
    MIN_MAX_INDIVIDUAL = "MIN_MAX_INDIVIDUAL"


class VenueCategory(str, Enum):
    SPORTS_FACILITY = "SPORTS_FACILITY"
    PARK = "PARK"
    MALL = "MALL"


class IntervalType(str, Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"


class RecordStatus(str, Enum):
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"


class GeocodeStatus(str, Enum):
    PENDING = "PENDING"
    VALID = "VALID"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"


class AttendanceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NO_RESPONSE = "NO_RESPONSE"
    WITHDRAWN = "WITHDRAWN"


class FeasibilityStatus(str, Enum):
    FEASIBLE = "FEASIBLE"
    EXCLUDED = "EXCLUDED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"


class ExclusionReason(str, Enum):
    BELOW_THRESHOLD = "BELOW_THRESHOLD"  # FR-D1
    JOURNEY_LIMIT = "JOURNEY_LIMIT"  # FR-D3
    GROUP_SIZE = "GROUP_SIZE"  # FR-D4
    BOOKING_LEAD_TIME = "BOOKING_LEAD_TIME"  # FR-D5


class RoutingStatus(str, Enum):
    AVAILABLE = "AVAILABLE"  # routing succeeded
    UNAVAILABLE = "UNAVAILABLE"  # provider unreachable or no route (NFR-3)
    ERROR = "ERROR"  # provider answered with something unusable


class RunStatus(str, Enum):
    """Overall outcome of one Generate Recommendations run (UC-09)."""

    OK = "OK"
    BEST_AVAILABLE_BELOW_THRESHOLD = "BEST_AVAILABLE_BELOW_THRESHOLD"
    NO_TIMESLOT_MEETS_THRESHOLD = "NO_TIMESLOT_MEETS_THRESHOLD"  # UC-09 alt flow
    NO_VALID_LOCATIONS = "NO_VALID_LOCATIONS"  # no centroid can be computed
    NO_SUPPORTING_VENUES = "NO_SUPPORTING_VENUES"  # FR-C3 found nothing


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Coordinates:
    lat: float
    lng: float

    def __post_init__(self) -> None:
        if not (-90.0 <= self.lat <= 90.0 and -180.0 <= self.lng <= 180.0):
            raise ValueError(f"coordinates out of range: {self.lat}, {self.lng}")


@dataclass(frozen=True)
class Interval:
    """One AvailabilityInterval (SRS B.3.6). ``start`` and ``end`` must be timezone-aware."""

    start: datetime
    end: datetime
    type: IntervalType = IntervalType.AVAILABLE

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("interval datetimes must be timezone-aware")
        if not self.start < self.end:
            raise ValueError("interval start must be earlier than end")


@dataclass(frozen=True)
class ParticipantInput:
    """A Participant together with their current AvailabilityRecord, if any.

    ``record_status`` is ``None`` when the Participant has joined but has no
    Availability Record yet (attendance NO_RESPONSE).
    """

    participant_id: str
    display_name: str
    record_status: RecordStatus | None
    intervals: tuple[Interval, ...] = ()
    location: Coordinates | None = None
    geocode_status: GeocodeStatus = GeocodeStatus.PENDING
    transport_mode: TransportMode = TransportMode.PUBLIC_TRANSPORT

    @property
    def is_active(self) -> bool:
        return self.record_status is RecordStatus.ACTIVE

    @property
    def has_valid_location(self) -> bool:
        return self.location is not None and self.geocode_status is GeocodeStatus.VALID


@dataclass(frozen=True)
class VenueInput:
    """A Venue plus the Activity Types it supports (SRS B.3.7, B.3.8)."""

    venue_id: str
    name: str
    category: VenueCategory
    location: Coordinates
    supported_activity_type_ids: frozenset[str]
    address: str = ""
    min_group_size: int | None = None
    optimal_group_size: int | None = None  # scoring effect is TBD-4; not used yet
    advance_booking_lead_minutes: int | None = None


@dataclass(frozen=True)
class SessionInput:
    """The Session fields the engine needs (SRS B.3.2)."""

    session_id: str
    activity_type_id: str
    date_range_start: datetime
    date_range_end: datetime
    duration_minutes: int
    minimum_attendee_threshold: int | None
    travel_objective: TravelObjective = TravelObjective.MIN_TOTAL
    attendance_weight_percent: int = 50
    timezone: str = "Asia/Singapore"


@dataclass(frozen=True)
class RecommendationRequest:
    """A consistent snapshot of one Session, taken inside one transaction.

    The engine is a pure function of this snapshot. Running it on a snapshot
    is how a withdrawal that completes before the snapshot is guaranteed not
    to be reflected in the scores (NFR-11); see README for the service-side
    revision check.
    """

    session: SessionInput
    participants: tuple[ParticipantInput, ...]
    venues: tuple[VenueInput, ...]
    now: datetime


# --------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------


@dataclass
class CandidateTimeslot:
    """SRS B.3.9 plus its TimeslotAttendance rows (B.3.10)."""

    index: int
    start: datetime
    end: datetime
    attendance: dict[str, AttendanceStatus] = field(default_factory=dict)

    @property
    def available_ids(self) -> tuple[str, ...]:
        return tuple(
            pid for pid, status in self.attendance.items() if status is AttendanceStatus.AVAILABLE
        )

    @property
    def available_count(self) -> int:
        return len(self.available_ids)


@dataclass(frozen=True)
class ShortlistEntry:
    """SRS B.3.11."""

    venue: VenueInput
    straight_line_distance_km: float
    rank: int


@dataclass(frozen=True)
class TravelEstimate:
    """SRS B.3.13. ``minutes`` is ``None`` unless ``status`` is AVAILABLE."""

    participant_id: str
    venue_id: str
    transport_mode: TransportMode
    minutes: int | None
    status: RoutingStatus
    journey_limit_exceeded: bool | None = None


@dataclass
class Combination:
    """SRS B.3.12. Scores and rank are ``None`` unless the Combination is FEASIBLE."""

    timeslot: CandidateTimeslot
    shortlist_entry: ShortlistEntry
    attendee_ids: tuple[str, ...]
    feasibility: FeasibilityStatus = FeasibilityStatus.FEASIBLE
    exclusion_reason: ExclusionReason | None = None
    travel: tuple[TravelEstimate, ...] = ()
    attendance_score: float | None = None
    travel_score: float | None = None
    combined_score: float | None = None
    rank: int | None = None

    @property
    def venue(self) -> VenueInput:
        return self.shortlist_entry.venue

    @property
    def attendee_count(self) -> int:
        return len(self.attendee_ids)

    def _minutes(self) -> list[int]:
        return [t.minutes for t in self.travel if t.minutes is not None]

    @property
    def total_travel_minutes(self) -> int | None:
        m = self._minutes()
        return sum(m) if m and len(m) == len(self.travel) else None

    @property
    def max_travel_minutes(self) -> int | None:
        m = self._minutes()
        return max(m) if m and len(m) == len(self.travel) else None

    @property
    def mean_travel_minutes(self) -> float | None:
        total = self.total_travel_minutes
        return total / len(self.travel) if total is not None and self.travel else None


@dataclass
class RecommendationResult:
    session_id: str
    status: RunStatus
    generated_at: datetime
    centroid: Coordinates | None = None
    timeslots: list[CandidateTimeslot] = field(default_factory=list)
    shortlist: list[ShortlistEntry] = field(default_factory=list)
    combinations: list[Combination] = field(default_factory=list)
    active_respondents: int = 0
    minimum_attendee_threshold: int = 0
    travel_objective: TravelObjective = TravelObjective.MIN_TOTAL
    attendance_weight_percent: int = 50
    routing_calls: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def ranked(self) -> list[Combination]:
        """Feasible Combinations, highest Combined Score first (FR-D10, FR-E1)."""
        feasible = [c for c in self.combinations if c.rank is not None]
        return sorted(feasible, key=lambda c: c.rank)  # type: ignore[arg-type, return-value]

    def top(self, k: int) -> list[Combination]:
        return self.ranked[:k]
