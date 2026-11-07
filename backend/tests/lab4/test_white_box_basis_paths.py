"""Assessed Lab 4 white-box basis-path tests for two class methods.

``WB-IV-*`` covers ``AvailabilityService._validate_intervals`` (V(G)=6).
``WB-PA-*`` covers ``_ParticipantAvailability.status_for`` (V(G)=9).
The identifiers match the CFG/path tables in the submitted report.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app.models import SchedulingSession
from app.recommender.candidate_generation import _ParticipantAvailability
from app.recommender.types import (
    AttendanceStatus,
    Coordinates,
    GeocodeStatus,
    Interval,
    IntervalType,
    ParticipantInput,
    RecordStatus,
    TransportMode,
)
from app.schemas import AvailabilityIntervalInput
from app.services.application_services import AvailabilityService


SGT = ZoneInfo("Asia/Singapore")
SLOT_START = datetime(2026, 11, 14, 10, 0, tzinfo=SGT)
SLOT_END = SLOT_START + timedelta(hours=2)
BISHAN = Coordinates(1.3510, 103.8485)


def _session() -> SchedulingSession:
    return SchedulingSession(
        name="Lab 4 basis-path session",
        activity_type_id=uuid4(),
        date_range_start=SLOT_START,
        date_range_end=SLOT_END,
        response_deadline=SLOT_START - timedelta(days=1),
        invitation_token="lab4-basis-path-token",
    )


def _interval(start: datetime, end: datetime) -> AvailabilityIntervalInput:
    return AvailabilityIntervalInput(start_date_time=start, end_date_time=end)


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


# AvailabilityService._validate_intervals — six independent paths.


def test_wb_iv_01_path_empty_input_returns_empty_ordered_list() -> None:
    assert AvailabilityService._validate_intervals(_session(), []) == []


def test_wb_iv_02_path_start_one_minute_before_session_is_rejected() -> None:
    intervals = [_interval(SLOT_START - timedelta(minutes=1), SLOT_START + timedelta(minutes=30))]
    with pytest.raises(HTTPException) as caught:
        AvailabilityService._validate_intervals(_session(), intervals)
    assert caught.value.status_code == 422
    assert caught.value.detail == "Availability must be inside the session date range"


def test_wb_iv_03_path_end_one_minute_after_session_is_rejected() -> None:
    intervals = [_interval(SLOT_END - timedelta(minutes=30), SLOT_END + timedelta(minutes=1))]
    with pytest.raises(HTTPException) as caught:
        AvailabilityService._validate_intervals(_session(), intervals)
    assert caught.value.status_code == 422
    assert caught.value.detail == "Availability must be inside the session date range"


def test_wb_iv_04_path_exact_session_endpoints_are_accepted() -> None:
    interval = _interval(SLOT_START, SLOT_END)
    ordered = AvailabilityService._validate_intervals(_session(), [interval])
    assert [(item.start_date_time, item.end_date_time) for item in ordered] == [
        (SLOT_START, SLOT_END)
    ]


def test_wb_iv_05_path_one_minute_overlap_is_rejected() -> None:
    intervals = [
        _interval(SLOT_START, SLOT_START + timedelta(minutes=61)),
        _interval(SLOT_START + timedelta(minutes=60), SLOT_END),
    ]
    with pytest.raises(HTTPException) as caught:
        AvailabilityService._validate_intervals(_session(), intervals)
    assert caught.value.status_code == 422
    assert caught.value.detail == "Availability intervals cannot overlap"


def test_wb_iv_06_path_unsorted_touching_intervals_are_sorted_and_accepted() -> None:
    later = _interval(SLOT_START + timedelta(hours=1), SLOT_END)
    earlier = _interval(SLOT_START, SLOT_START + timedelta(hours=1))
    ordered = AvailabilityService._validate_intervals(_session(), [later, earlier])
    assert [(item.start_date_time, item.end_date_time) for item in ordered] == [
        (SLOT_START, SLOT_START + timedelta(hours=1)),
        (SLOT_START + timedelta(hours=1), SLOT_END),
    ]


# _ParticipantAvailability.status_for — nine logical basis paths after
# expanding each ``any`` generator and its two short-circuit comparisons.


def test_wb_pa_01_path_active_with_no_blocks_is_unavailable() -> None:
    availability = _ParticipantAvailability(_participant())
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.UNAVAILABLE


def test_wb_pa_02_path_no_response_returns_no_response() -> None:
    availability = _ParticipantAvailability(_participant(status=None))
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.NO_RESPONSE


def test_wb_pa_03_path_withdrawn_returns_withdrawn() -> None:
    availability = _ParticipantAvailability(
        _participant(
            status=RecordStatus.WITHDRAWN,
            available=((SLOT_START, SLOT_END),),
        )
    )
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.WITHDRAWN


def test_wb_pa_04_path_busy_starting_at_slot_end_does_not_overlap() -> None:
    availability = _ParticipantAvailability(
        _participant(busy=((SLOT_END, SLOT_END + timedelta(minutes=30)),))
    )
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.UNAVAILABLE


def test_wb_pa_05_path_busy_ending_at_slot_start_does_not_overlap() -> None:
    availability = _ParticipantAvailability(
        _participant(busy=((SLOT_START - timedelta(minutes=30), SLOT_START),))
    )
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.UNAVAILABLE


def test_wb_pa_06_path_one_minute_busy_overlap_overrides_full_availability() -> None:
    availability = _ParticipantAvailability(
        _participant(
            available=((SLOT_START, SLOT_END),),
            busy=(
                (SLOT_START - timedelta(minutes=30), SLOT_START),
                (SLOT_END - timedelta(minutes=1), SLOT_END + timedelta(minutes=30)),
            ),
        )
    )
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.UNAVAILABLE


def test_wb_pa_07_path_available_block_starting_one_minute_late_is_unavailable() -> None:
    availability = _ParticipantAvailability(
        _participant(available=((SLOT_START + timedelta(minutes=1), SLOT_END),))
    )
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.UNAVAILABLE


def test_wb_pa_08_path_available_block_ending_one_minute_early_is_unavailable() -> None:
    availability = _ParticipantAvailability(
        _participant(available=((SLOT_START, SLOT_END - timedelta(minutes=1)),))
    )
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.UNAVAILABLE


def test_wb_pa_09_path_exact_full_available_coverage_is_available() -> None:
    availability = _ParticipantAvailability(
        _participant(
            available=(
                (SLOT_START - timedelta(hours=1), SLOT_START - timedelta(minutes=30)),
                (SLOT_START, SLOT_END),
            )
        )
    )
    assert availability.status_for(SLOT_START, SLOT_END) is AttendanceStatus.AVAILABLE
