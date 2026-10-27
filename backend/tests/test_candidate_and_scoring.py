from datetime import datetime, timezone

import pytest

from app.models.enums import TravelObjective
from app.services.domain_rules import attendance_score, combined_score, enumerate_timeslots, travel_score


def test_enumerates_overlapping_candidate_slots():
    start = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
    end = datetime(2026, 10, 20, 11, tzinfo=timezone.utc)
    slots = enumerate_timeslots(start, end, duration_minutes=60, step_minutes=30)
    assert len(slots) == 3
    assert slots[-1][1] == end


def test_tbd_scoring_formulas_are_explicit_and_configurable():
    assert attendance_score(3, 4) == 75
    assert travel_score([10, 20], 2, 60, TravelObjective.MIN_TOTAL) == 75
    assert travel_score([10, 20], 2, 60, TravelObjective.MIN_MAX_INDIVIDUAL) == pytest.approx(66.6667)
    assert combined_score(75, 50, 60, 40) == 65


def test_missing_or_over_cap_route_is_not_zero():
    assert travel_score([10], 2, 60, TravelObjective.MIN_TOTAL) is None
    assert travel_score([61], 1, 60, TravelObjective.MIN_MAX_INDIVIDUAL) is None

