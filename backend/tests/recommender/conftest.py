"""Shared fixtures and builders for the recommender tests.

Run from the ``backend`` folder:  python -m pytest tests/recommender
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.recommender.types import (  # noqa: E402
    Coordinates,
    GeocodeStatus,
    Interval,
    IntervalType,
    ParticipantInput,
    RecommendationRequest,
    RecordStatus,
    SessionInput,
    TransportMode,
    TravelObjective,
    VenueCategory,
    VenueInput,
)

SGT = ZoneInfo("Asia/Singapore")
DAY = datetime(2026, 11, 7, tzinfo=SGT)  # a Saturday
NOW = datetime(2026, 10, 25, 10, 0, tzinfo=SGT)

BISHAN = Coordinates(1.3510, 103.8485)
TOA_PAYOH = Coordinates(1.3326, 103.8474)
AMK = Coordinates(1.3700, 103.8496)
TAMPINES = Coordinates(1.3534, 103.9452)
JURONG = Coordinates(1.3332, 103.7423)


def at(hour: float, day: datetime = DAY) -> datetime:
    return day + timedelta(hours=hour)


def person(
    pid: str,
    *spans: tuple[float, float],
    busy: tuple[tuple[float, float], ...] = (),
    status: RecordStatus | None = RecordStatus.ACTIVE,
    location: Coordinates | None = BISHAN,
    geocode: GeocodeStatus = GeocodeStatus.VALID,
    mode: TransportMode = TransportMode.PUBLIC_TRANSPORT,
) -> ParticipantInput:
    intervals = tuple(Interval(at(s), at(e), IntervalType.AVAILABLE) for s, e in spans) + tuple(
        Interval(at(s), at(e), IntervalType.BUSY) for s, e in busy
    )
    return ParticipantInput(
        participant_id=pid,
        display_name=pid,
        record_status=status,
        intervals=intervals,
        location=location,
        geocode_status=geocode,
        transport_mode=mode,
    )


def venue(
    vid: str,
    location: Coordinates,
    *,
    category: VenueCategory = VenueCategory.PARK,
    activities: tuple[str, ...] = ("football",),
    min_group: int | None = None,
    lead_minutes: int | None = None,
) -> VenueInput:
    return VenueInput(
        venue_id=vid,
        name=vid,
        category=category,
        location=location,
        supported_activity_type_ids=frozenset(activities),
        min_group_size=min_group,
        advance_booking_lead_minutes=lead_minutes,
    )


def session(
    *,
    start: float = 8,
    end: float = 14,
    duration: int = 120,
    threshold: int | None = 2,
    objective: TravelObjective = TravelObjective.MIN_TOTAL,
    weight: int = 50,
    activity: str = "football",
) -> SessionInput:
    return SessionInput(
        session_id="s-test",
        activity_type_id=activity,
        date_range_start=at(start),
        date_range_end=at(end),
        duration_minutes=duration,
        minimum_attendee_threshold=threshold,
        travel_objective=objective,
        attendance_weight_percent=weight,
    )


def request(sess: SessionInput, participants, venues, now: datetime = NOW) -> RecommendationRequest:
    return RecommendationRequest(
        session=sess, participants=tuple(participants), venues=tuple(venues), now=now
    )


@pytest.fixture
def run():
    """Run a coroutine to completion (avoids a pytest-asyncio dependency)."""
    import asyncio

    return asyncio.run
