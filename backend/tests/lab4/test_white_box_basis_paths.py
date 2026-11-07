"""Lab 4 white-box basis-path tests.

The case identifiers correspond to the independent paths documented in the
submitted control-flow graphs and PDF report.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.recommender.candidate_generation import _ParticipantAvailability
from app.recommender.feasibility import pre_routing_exclusion
from app.recommender.types import (
    AttendanceStatus,
    CandidateTimeslot,
    Combination,
    Coordinates,
    ExclusionReason,
    GeocodeStatus,
    Interval,
    IntervalType,
    ParticipantInput,
    RecordStatus,
    ShortlistEntry,
    TransportMode,
    VenueCategory,
    VenueInput,
)


SGT = ZoneInfo("Asia/Singapore")
SLOT_START = datetime(2026, 11, 14, 10, 0, tzinfo=SGT)
SLOT_END = SLOT_START + timedelta(hours=2)
BISHAN = Coordinates(1.3510, 103.8485)


def _combination(
    attendee_count: int,
    *,
    category: VenueCategory,
    minimum_group_size: int | None = None,
    lead_minutes: int | None = None,
) -> Combination:
    venue = VenueInput(
        venue_id="basis-path-venue",
        name="Basis Path Venue",
        category=category,
        location=BISHAN,
        supported_activity_type_ids=frozenset({"badminton"}),
        min_group_size=minimum_group_size,
        advance_booking_lead_minutes=lead_minutes,
    )
    return Combination(
        timeslot=CandidateTimeslot(index=0, start=SLOT_START, end=SLOT_END),
        shortlist_entry=ShortlistEntry(
            venue=venue,
            straight_line_distance_km=1.0,
            rank=1,
        ),
        attendee_ids=tuple(f"p{index}" for index in range(attendee_count)),
    )


def _participant(
    *,
    status: RecordStatus | None = RecordStatus.ACTIVE,
    available: tuple[tuple[datetime, datetime], ...] = (),
    busy: tuple[tuple[datetime, datetime], ...] = (),
) -> ParticipantInput:
    intervals = tuple(Interval(start, end, IntervalType.AVAILABLE) for start, end in available)
    intervals += tuple(Interval(start, end, IntervalType.BUSY) for start, end in busy)
    return ParticipantInput(
        participant_id="participant-1",
        display_name="Participant 1",
        record_status=status,
        intervals=intervals,
        location=BISHAN,
        geocode_status=GeocodeStatus.VALID,
        transport_mode=TransportMode.PUBLIC_TRANSPORT,
    )


def test_wb_pr_01_path_below_session_threshold() -> None:
    combo = _combination(
        2,
        category=VenueCategory.SPORTS_FACILITY,
        minimum_group_size=6,
        lead_minutes=1440,
    )
    assert pre_routing_exclusion(combo, 3, SLOT_START - timedelta(days=7)) is ExclusionReason.BELOW_THRESHOLD


def test_wb_pr_02_path_non_sports_skips_sports_constraints() -> None:
    combo = _combination(
        3,
        category=VenueCategory.PARK,
        minimum_group_size=99,
        lead_minutes=999999,
    )
    assert pre_routing_exclusion(combo, 3, SLOT_START) is None


def test_wb_pr_03_path_sports_group_size_failure() -> None:
    combo = _combination(
        3,
        category=VenueCategory.SPORTS_FACILITY,
        minimum_group_size=4,
    )
    assert pre_routing_exclusion(combo, 2, SLOT_START - timedelta(days=7)) is ExclusionReason.GROUP_SIZE


def test_wb_pr_04_path_sports_has_no_group_or_lead_constraint() -> None:
    combo = _combination(
        3,
        category=VenueCategory.SPORTS_FACILITY,
        minimum_group_size=None,
        lead_minutes=None,
    )
    assert pre_routing_exclusion(combo, 2, SLOT_START - timedelta(days=7)) is None


def test_wb_pr_05_path_sports_meets_group_size_without_lead_constraint() -> None:
    combo = _combination(
        4,
        category=VenueCategory.SPORTS_FACILITY,
        minimum_group_size=4,
        lead_minutes=None,
    )
    assert pre_routing_exclusion(combo, 2, SLOT_START - timedelta(days=7)) is None


def test_wb_pr_06_path_sports_booking_lead_failure() -> None:
    combo = _combination(
        4,
        category=VenueCategory.SPORTS_FACILITY,
        minimum_group_size=4,
        lead_minutes=1440,
    )
    now = SLOT_START - timedelta(hours=23)
    assert pre_routing_exclusion(combo, 2, now) is ExclusionReason.BOOKING_LEAD_TIME


def test_wb_pr_07_path_sports_exactly_meets_booking_lead_boundary() -> None:
    combo = _combination(
        4,
        category=VenueCategory.SPORTS_FACILITY,
        minimum_group_size=4,
        lead_minutes=1440,
    )
    now = SLOT_START - timedelta(hours=24)
    assert pre_routing_exclusion(combo, 2, now) is None


def test_wb_pa_01_path_no_response() -> None:
    availability = _ParticipantAvailability(_participant(status=None))
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.NO_RESPONSE


def test_wb_pa_02_path_withdrawn() -> None:
    availability = _ParticipantAvailability(
        _participant(
            status=RecordStatus.WITHDRAWN,
            available=((SLOT_START - timedelta(hours=2), SLOT_END + timedelta(hours=2)),),
        )
    )
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.WITHDRAWN


def test_wb_pa_03_path_busy_overlap_overrides_available_time() -> None:
    availability = _ParticipantAvailability(
        _participant(
            available=((SLOT_START - timedelta(hours=2), SLOT_END + timedelta(hours=2)),),
            busy=((SLOT_START + timedelta(minutes=30), SLOT_START + timedelta(hours=1)),),
        )
    )
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.UNAVAILABLE


def test_wb_pa_04_path_slot_is_fully_covered_by_available_time() -> None:
    availability = _ParticipantAvailability(
        _participant(
            available=((SLOT_START - timedelta(hours=1), SLOT_END + timedelta(hours=1)),),
        )
    )
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.AVAILABLE


def test_wb_pa_05_path_partial_coverage_is_unavailable() -> None:
    availability = _ParticipantAvailability(
        _participant(
            available=((SLOT_START, SLOT_END - timedelta(minutes=1)),),
        )
    )
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.UNAVAILABLE

