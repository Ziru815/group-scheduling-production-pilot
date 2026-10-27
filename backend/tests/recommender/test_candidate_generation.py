"""FR-C1 to FR-C4."""

from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from app.recommender.candidate_generation import (
    compute_attendance,
    enumerate_timeslots,
    filter_venues,
    participant_centroid,
    shortlist_venues,
    validate_session,
)
from app.recommender.config import RecommenderConfig
from app.recommender.geo import centroid, haversine_km
from app.recommender.types import (
    AttendanceStatus,
    Coordinates,
    GeocodeStatus,
    RecordStatus,
)

from .conftest import AMK, BISHAN, JURONG, TAMPINES, TOA_PAYOH, at, person, session, venue

# ---------------------------------------------------------------- FR-C1


def test_timeslots_step_and_end_boundary():
    slots = enumerate_timeslots(at(8), at(12), duration_minutes=120, step_minutes=30)
    starts = [s.hour + s.minute / 60 for s, _ in slots]
    assert starts == [8, 8.5, 9, 9.5, 10]  # 10:00-12:00 is the last that fits
    assert all((e - s).total_seconds() == 7200 for s, e in slots)


def test_timeslots_none_when_range_shorter_than_duration():
    assert enumerate_timeslots(at(8), at(9), duration_minutes=120, step_minutes=30) == []


def test_validate_rejects_naive_datetimes_and_bad_duration():
    cfg = RecommenderConfig()
    naive = dataclasses.replace(session(), date_range_start=datetime(2026, 11, 7, 8))
    with pytest.raises(ValueError, match="timezone-aware"):
        validate_session(naive, cfg)
    with pytest.raises(ValueError, match="FR-A1.1"):
        validate_session(session(duration=10), cfg)
    with pytest.raises(ValueError, match="FR-A1.1"):
        validate_session(session(duration=481), cfg)
    validate_session(session(duration=15), cfg)
    validate_session(session(duration=480, end=24 + 8), cfg)


# ---------------------------------------------------------------- FR-C2


def _status(p, start, end):
    [slot] = compute_attendance([(at(start), at(end))], [p])
    return slot.attendance[p.participant_id]


def test_attendance_requires_full_coverage_across_adjacent_intervals():
    p = person("a", (8, 9), (9, 10.5))  # touching blocks merge
    assert _status(p, 8, 10) is AttendanceStatus.AVAILABLE
    assert _status(p, 9.5, 11.5) is AttendanceStatus.UNAVAILABLE  # runs past 10:30


def test_busy_block_overrides_available():
    p = person("a", (8, 14), busy=((11, 12),))
    assert _status(p, 9, 11) is AttendanceStatus.AVAILABLE  # ends exactly when busy starts
    assert _status(p, 10, 12) is AttendanceStatus.UNAVAILABLE


def test_no_response_and_withdrawn_stay_distinct_from_unavailable():
    assert _status(person("a", status=None), 8, 10) is AttendanceStatus.NO_RESPONSE
    assert _status(person("a", (8, 14), status=RecordStatus.WITHDRAWN), 8, 10) is AttendanceStatus.WITHDRAWN
    assert _status(person("a"), 8, 10) is AttendanceStatus.UNAVAILABLE  # active but no time marked


def test_available_count_per_timeslot():
    people = [person("a", (8, 12)), person("b", (9, 12)), person("c", (8, 12), status=RecordStatus.WITHDRAWN)]
    slots = compute_attendance(enumerate_timeslots(at(8), at(12), 120, 60), people)
    assert [s.available_count for s in slots] == [1, 2, 2]


# ---------------------------------------------------------------- FR-C3, FR-C4


def test_filter_venues_by_activity():
    vs = [venue("f", BISHAN, activities=("football",)), venue("p", BISHAN, activities=("picnic",))]
    assert [v.venue_id for v in filter_venues(vs, "football")] == ["f"]


def test_centroid_uses_only_active_valid_locations():
    people = [
        person("a", location=BISHAN),
        person("b", location=TOA_PAYOH),
        person("w", location=JURONG, status=RecordStatus.WITHDRAWN),
        person("x", location=TAMPINES, geocode=GeocodeStatus.UNAVAILABLE),
        person("n", location=None, status=None),
    ]
    c = participant_centroid(people)
    assert c == centroid([BISHAN, TOA_PAYOH])
    assert haversine_km(c, Coordinates(1.3418, 103.84795)) < 0.01


def test_centroid_none_without_locations():
    assert participant_centroid([person("a", location=None, geocode=GeocodeStatus.PENDING)]) is None


def test_shortlist_keeps_nearest_n_in_order():
    vs = [venue("far", JURONG), venue("mid", AMK), venue("near", TOA_PAYOH), venue("east", TAMPINES)]
    entries = shortlist_venues(vs, BISHAN, 2)
    assert [e.venue.venue_id for e in entries] == ["near", "mid"]
    assert [e.rank for e in entries] == [1, 2]
    assert entries[0].straight_line_distance_km < entries[1].straight_line_distance_km


def test_haversine_known_distance():
    # Bishan MRT to Toa Payoh MRT is roughly 2 km apart.
    assert 1.9 < haversine_km(BISHAN, TOA_PAYOH) < 2.2
