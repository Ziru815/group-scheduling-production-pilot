"""Lab 4 black-box tests for the recommendation control boundary.

These tests exercise only ``RecommendationEngine.generate`` inputs and public
outputs.  The case identifiers match the submitted testing report.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.adapters.ports import RouteResult
from app.recommender.engine import RecommendationEngine
from app.recommender.types import (
    Coordinates,
    ExclusionReason,
    FeasibilityStatus,
    GeocodeStatus,
    Interval,
    ParticipantInput,
    RecommendationRequest,
    RecordStatus,
    RoutingStatus,
    RunStatus,
    SessionInput,
    TransportMode,
    TravelObjective,
    VenueCategory,
    VenueInput,
)


SGT = ZoneInfo("Asia/Singapore")
DAY = datetime(2026, 11, 7, 8, 0, tzinfo=SGT)
NOW = datetime(2026, 11, 1, 10, 0, tzinfo=SGT)
BISHAN = Coordinates(1.3510, 103.8485)
TOA_PAYOH = Coordinates(1.3326, 103.8474)


class FixedRouter:
    """Deterministic substitute for the external routing provider boundary."""

    def __init__(
        self,
        *,
        minutes: int | None = 20,
        status: RoutingStatus = RoutingStatus.AVAILABLE,
        raises: bool = False,
    ) -> None:
        self.minutes = minutes
        self.status = status
        self.raises = raises
        self.calls = 0

    async def route(self, origin, destination, mode, depart_at) -> RouteResult:
        self.calls += 1
        if self.raises:
            raise RuntimeError("controlled provider failure")
        return RouteResult(status=self.status, minutes=self.minutes)


def _session(
    *,
    duration: int = 120,
    threshold: int | None = 2,
    weight: int = 50,
    activity: str = "badminton",
    start: datetime = DAY,
    end: datetime = DAY + timedelta(hours=10),
) -> SessionInput:
    return SessionInput(
        session_id="lab4-session",
        activity_type_id=activity,
        date_range_start=start,
        date_range_end=end,
        duration_minutes=duration,
        minimum_attendee_threshold=threshold,
        travel_objective=TravelObjective.MIN_TOTAL,
        attendance_weight_percent=weight,
    )


def _participant(
    participant_id: str,
    *available: tuple[float, float],
    location: Coordinates | None = BISHAN,
    geocode_status: GeocodeStatus = GeocodeStatus.VALID,
) -> ParticipantInput:
    return ParticipantInput(
        participant_id=participant_id,
        display_name=participant_id,
        record_status=RecordStatus.ACTIVE,
        intervals=tuple(
            Interval(DAY + timedelta(hours=start), DAY + timedelta(hours=end))
            for start, end in available
        ),
        location=location,
        geocode_status=geocode_status,
        transport_mode=TransportMode.PUBLIC_TRANSPORT,
    )


def _venue(*, activity: str = "badminton") -> VenueInput:
    return VenueInput(
        venue_id="venue-1",
        name="Public Sports Hall",
        category=VenueCategory.PARK,
        location=TOA_PAYOH,
        supported_activity_type_ids=frozenset({activity}),
        address="Singapore",
    )


def _request(
    session: SessionInput | None = None,
    participants: tuple[ParticipantInput, ...] | None = None,
    venues: tuple[VenueInput, ...] | None = None,
) -> RecommendationRequest:
    return RecommendationRequest(
        session=session or _session(),
        participants=participants
        or (
            _participant("p1", (0, 10)),
            _participant("p2", (0, 10)),
        ),
        venues=venues or (_venue(),),
        now=NOW,
    )


def _generate(request: RecommendationRequest, router: FixedRouter | None = None):
    return asyncio.run(RecommendationEngine(router or FixedRouter()).generate(request))


def test_bb_dur_01_rejects_duration_14_below_minimum() -> None:
    with pytest.raises(ValueError, match="duration must be 15 to 480 minutes"):
        _generate(_request(session=_session(duration=14)))


def test_bb_dur_02_accepts_duration_15_at_minimum() -> None:
    result = _generate(_request(session=_session(duration=15)))
    assert result.status is RunStatus.OK
    assert result.ranked


def test_bb_dur_03_accepts_duration_480_at_maximum() -> None:
    result = _generate(_request(session=_session(duration=480)))
    assert result.status is RunStatus.OK
    assert result.ranked


def test_bb_dur_04_rejects_duration_481_above_maximum() -> None:
    with pytest.raises(ValueError, match="duration must be 15 to 480 minutes"):
        _generate(_request(session=_session(duration=481)))


def test_bb_thr_01_returns_ok_when_threshold_is_met() -> None:
    result = _generate(_request(session=_session(threshold=2)))
    assert result.status is RunStatus.OK
    assert result.ranked
    assert all(option.attendee_count == 2 for option in result.ranked)


def test_bb_thr_02_returns_best_available_when_requested_threshold_is_narrowly_missed() -> None:
    participants = (
        _participant("p1", (0, 2)),
        _participant("p2", (0, 2)),
        _participant("p3", (3, 5)),
    )
    result = _generate(_request(session=_session(threshold=3), participants=participants))
    assert result.status is RunStatus.BEST_AVAILABLE_BELOW_THRESHOLD
    assert result.ranked
    assert all(option.attendee_count == 2 for option in result.ranked)
    assert any("requested minimum of 3" in warning for warning in result.warnings)


def test_bb_thr_03_returns_no_timeslot_when_two_person_group_cannot_form() -> None:
    participants = (
        _participant("p1", (0, 2)),
        _participant("p2", (3, 5)),
    )
    router = FixedRouter()
    result = _generate(
        _request(session=_session(threshold=2), participants=participants),
        router,
    )
    assert result.status is RunStatus.NO_TIMESLOT_MEETS_THRESHOLD
    assert result.ranked == []
    assert result.combinations == []
    assert router.calls == 0


def test_bb_ven_01_returns_no_supporting_venues_for_wrong_activity_partition() -> None:
    result = _generate(
        _request(
            session=_session(activity="badminton"),
            venues=(_venue(activity="football"),),
        )
    )
    assert result.status is RunStatus.NO_SUPPORTING_VENUES
    assert result.ranked == []


def test_bb_loc_01_returns_no_valid_locations_when_centroid_cannot_be_computed() -> None:
    participants = (
        _participant("p1", (0, 10), location=None, geocode_status=GeocodeStatus.INVALID),
        _participant("p2", (0, 10), location=None, geocode_status=GeocodeStatus.UNAVAILABLE),
    )
    router = FixedRouter()
    result = _generate(_request(participants=participants), router)
    assert result.status is RunStatus.NO_VALID_LOCATIONS
    assert result.ranked == []
    assert router.calls == 0


def test_bb_rte_01_marks_unavailable_provider_data_without_fabricating_a_journey() -> None:
    result = _generate(
        _request(),
        FixedRouter(minutes=None, status=RoutingStatus.UNAVAILABLE),
    )
    assert result.combinations
    assert result.ranked == []
    assert all(option.feasibility is FeasibilityStatus.DATA_UNAVAILABLE for option in result.combinations)
    assert all(estimate.minutes is None for option in result.combinations for estimate in option.travel)


def test_bb_rte_02_contains_provider_exception_as_error_status() -> None:
    result = _generate(_request(), FixedRouter(raises=True))
    assert result.combinations
    assert result.ranked == []
    assert all(option.feasibility is FeasibilityStatus.DATA_UNAVAILABLE for option in result.combinations)
    assert all(
        estimate.status is RoutingStatus.ERROR
        for option in result.combinations
        for estimate in option.travel
    )


def test_bb_jrn_01_keeps_journey_at_60_minute_limit() -> None:
    result = _generate(_request(), FixedRouter(minutes=60))
    assert result.status is RunStatus.OK
    assert result.ranked
    assert all(option.feasibility is FeasibilityStatus.FEASIBLE for option in result.ranked)
    assert all(
        estimate.journey_limit_exceeded is False
        for option in result.ranked
        for estimate in option.travel
    )


def test_bb_jrn_02_excludes_journey_one_minute_above_limit() -> None:
    result = _generate(_request(), FixedRouter(minutes=61))
    assert result.status is RunStatus.OK
    assert result.ranked == []
    assert result.combinations
    assert all(option.exclusion_reason is ExclusionReason.JOURNEY_LIMIT for option in result.combinations)


def test_bb_wgt_01_accepts_zero_percent_attendance_weight() -> None:
    result = _generate(_request(session=_session(weight=0)))
    assert result.status is RunStatus.OK
    assert result.attendance_weight_percent == 0
    assert result.ranked


def test_bb_wgt_02_accepts_100_percent_attendance_weight() -> None:
    result = _generate(_request(session=_session(weight=100)))
    assert result.status is RunStatus.OK
    assert result.attendance_weight_percent == 100
    assert result.ranked


def test_bb_wgt_03_rejects_weight_minus_one_below_minimum() -> None:
    with pytest.raises(ValueError, match="attendance weight must be between 0 and 100"):
        _generate(_request(session=_session(weight=-1)))


def test_bb_wgt_04_rejects_weight_101_above_maximum() -> None:
    with pytest.raises(ValueError, match="attendance weight must be between 0 and 100"):
        _generate(_request(session=_session(weight=101)))
