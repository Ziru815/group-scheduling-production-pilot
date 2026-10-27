"""FR-D1, FR-D3 to FR-D10."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.recommender.feasibility import journey_exclusion, pre_routing_exclusion
from app.recommender.scoring import (
    attendance_score,
    combined_score,
    score_and_rank,
    snap_weight,
    travel_score,
)
from app.recommender.types import (
    CandidateTimeslot,
    Combination,
    ExclusionReason,
    FeasibilityStatus,
    RoutingStatus,
    ShortlistEntry,
    TransportMode,
    TravelEstimate,
    TravelObjective,
    VenueCategory,
)

from .conftest import BISHAN, NOW, at, venue


def combo(attendees=None, *, start=10.0, category=VenueCategory.SPORTS_FACILITY, min_group=None,
          lead=None, minutes=None, rank=1, vid="v"):
    """A Combination with ``attendees`` people; ``minutes`` gives each one's journey."""
    if attendees is None:
        attendees = len(minutes) if minutes else 3
    slot = CandidateTimeslot(index=0, start=at(start), end=at(start + 2))
    entry = ShortlistEntry(
        venue=venue(vid, BISHAN, category=category, min_group=min_group, lead_minutes=lead),
        straight_line_distance_km=1.0,
        rank=rank,
    )
    ids = tuple(f"p{i}" for i in range(attendees))
    c = Combination(timeslot=slot, shortlist_entry=entry, attendee_ids=ids)
    if minutes is not None:
        c.travel = tuple(
            TravelEstimate(pid, vid, TransportMode.WALK, m, RoutingStatus.AVAILABLE)
            for pid, m in zip(ids, minutes, strict=True)
        )
    return c


# ---------------------------------------------------------------- FR-D1, D4, D5


def test_below_threshold_is_excluded_first():
    assert pre_routing_exclusion(combo(2, min_group=6), 3, NOW) is ExclusionReason.BELOW_THRESHOLD
    assert pre_routing_exclusion(combo(3), 3, NOW) is None


def test_group_size_only_applies_to_sports_facilities():
    assert pre_routing_exclusion(combo(4, min_group=6), 2, NOW) is ExclusionReason.GROUP_SIZE
    park = combo(4, category=VenueCategory.PARK, min_group=6)
    assert pre_routing_exclusion(park, 2, NOW) is None


def test_booking_lead_time():
    slot_start = at(10)
    lead = 24 * 60
    too_soon = slot_start - timedelta(hours=23)
    in_time = slot_start - timedelta(hours=25)
    assert pre_routing_exclusion(combo(lead=lead), 1, too_soon) is ExclusionReason.BOOKING_LEAD_TIME
    assert pre_routing_exclusion(combo(lead=lead), 1, in_time) is None


# ---------------------------------------------------------------- FR-D3


def test_journey_limit_applies_to_any_single_attendee():
    assert journey_exclusion(combo(minutes=[10, 61]).travel, 60) is ExclusionReason.JOURNEY_LIMIT
    assert journey_exclusion(combo(minutes=[10, 60]).travel, 60) is None


# ---------------------------------------------------------------- FR-D7 to FR-D10


@pytest.mark.parametrize(
    "raw, snapped",
    [(0, 0), (4.9, 0), (5, 10), (44, 40), (45, 50), (99, 100), (-20, 0), (130, 100)],
)
def test_weight_snaps_to_10_percent(raw, snapped):
    assert snap_weight(raw) == snapped


def test_score_components_are_bounded():
    assert attendance_score(3, 4) == 0.75
    assert attendance_score(0, 0) == 0.0
    assert travel_score(0, 60) == 1.0
    assert travel_score(30, 60) == 0.5
    assert travel_score(90, 60) == 0.0
    assert combined_score(1.0, 0.0, 100) == 1.0
    assert combined_score(1.0, 0.0, 0) == 0.0
    assert combined_score(0.8, 0.4, 60) == pytest.approx(0.64)


def test_objectives_use_mean_or_max():
    c = combo(2, minutes=[10, 50])
    [ranked] = score_and_rank([c], objective=TravelObjective.MIN_TOTAL, attendance_weight_percent=0,
                              active_respondents=3, max_journey_minutes=60)
    assert ranked.travel_score == pytest.approx(1 - 30 / 60, abs=1e-6)
    score_and_rank([c], objective=TravelObjective.MIN_MAX_INDIVIDUAL, attendance_weight_percent=0,
                   active_respondents=3, max_journey_minutes=60)
    assert c.travel_score == pytest.approx(1 - 50 / 60, abs=1e-6)


def test_ranking_and_tie_break():
    # Same combined score (pure attendance weighting, same attendees); the one
    # with the shorter longest journey wins, then the earlier start.
    a = combo(3, minutes=[10, 10, 40], start=10, vid="a")
    b = combo(3, minutes=[20, 20, 20], start=11, vid="b")
    c = combo(3, minutes=[20, 20, 20], start=9, vid="c")
    excluded = combo(3, minutes=[5, 5, 5], vid="x")
    excluded.feasibility = FeasibilityStatus.EXCLUDED
    ranked = score_and_rank([a, b, c, excluded], objective=TravelObjective.MIN_TOTAL,
                            attendance_weight_percent=100, active_respondents=4, max_journey_minutes=60)
    assert [r.venue.venue_id for r in ranked] == ["c", "b", "a"]
    assert [r.rank for r in ranked] == [1, 2, 3]
    assert excluded.rank is None and excluded.combined_score is None


def test_higher_combined_score_ranks_first():
    close = combo(3, minutes=[5, 5, 5], vid="close")
    far = combo(3, minutes=[50, 50, 50], vid="far")
    ranked = score_and_rank([far, close], objective=TravelObjective.MIN_TOTAL,
                            attendance_weight_percent=50, active_respondents=3, max_journey_minutes=60)
    assert ranked[0].venue.venue_id == "close"
    assert ranked[0].combined_score > ranked[1].combined_score
