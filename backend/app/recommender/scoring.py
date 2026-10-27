"""Scoring and ranking (SRS Section 4.4, FR-D6 to FR-D10).

The exact formulas are open in the SRS (TBD-15) and so is the tie-break rule
(TBD-9). This module implements a concrete proposal for both, chosen so that:

* every score lies in [0, 1] and means the same thing from run to run, so a
  Combination's score does not change just because other Combinations were
  added or removed (no min-max normalisation across the candidate set);
* travel scoring does not double-penalise attendance: under MIN_TOTAL the
  travel value is the mean journey per attendee, which is what minimising the
  group's total travel means once attendee counts differ between options;
* changing the Travel Objective or weighting only re-scores and re-ranks
  stored results and never triggers new routing calls (FR-D9).

Proposal for TBD-15
  AttendanceScore = attendees / Participants with an active response
  TravelValue     = mean journey (MIN_TOTAL) or longest journey (MIN_MAX_INDIVIDUAL)
  TravelScore     = 1 - TravelValue / MaximumJourneyTime, clamped to [0, 1]
  CombinedScore   = w * AttendanceScore + (1 - w) * TravelScore, w in 10% steps

Proposal for TBD-9 (applied in order when Combined Scores are equal)
  more attendees, shorter longest journey, earlier start, nearer Venue
  (shortlist rank), then VenueID.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.recommender.types import (
    Combination,
    FeasibilityStatus,
    TravelObjective,
)

SCORE_PRECISION = 6  # decimal places kept, so float noise cannot change a ranking


def snap_weight(raw_percent: float, increment: int = 10) -> int:
    """FR-D9.1: round the raw control value to the nearest increment, half up, in [0, 100]."""
    clamped = min(100.0, max(0.0, float(raw_percent)))
    return int(increment * int(clamped / increment + 0.5))


def attendance_score(attendee_count: int, active_respondents: int) -> float:
    """FR-D8: share of Participants with an active response who can attend."""
    if active_respondents <= 0:
        return 0.0
    return min(1.0, attendee_count / active_respondents)


def travel_value(combo: Combination, objective: TravelObjective) -> float:
    """The quantity the selected Travel Objective minimises (FR-D6, FR-D7)."""
    if objective is TravelObjective.MIN_MAX_INDIVIDUAL:
        value = combo.max_travel_minutes
    else:
        value = combo.mean_travel_minutes
    if value is None:
        raise ValueError("travel value needs a routing duration for every attendee")
    return float(value)


def travel_score(value_minutes: float, max_journey_minutes: int) -> float:
    """FR-D7: 1 for a zero-minute journey, 0 at the journey cap (TBD-1)."""
    return min(1.0, max(0.0, 1.0 - value_minutes / max_journey_minutes))


def combined_score(attendance: float, travel: float, attendance_weight_percent: int) -> float:
    """FR-D10: weighted sum; weights total 100% (B.3.2)."""
    w = attendance_weight_percent / 100.0
    return round(w * attendance + (1.0 - w) * travel, SCORE_PRECISION)


def _tie_break_key(c: Combination) -> tuple:
    return (
        -(c.combined_score or 0.0),
        -c.attendee_count,
        c.max_travel_minutes if c.max_travel_minutes is not None else float("inf"),
        c.timeslot.start,
        c.shortlist_entry.rank,
        c.venue.venue_id,
    )


def score_and_rank(
    combinations: Iterable[Combination],
    *,
    objective: TravelObjective,
    attendance_weight_percent: int,
    active_respondents: int,
    max_journey_minutes: int,
) -> list[Combination]:
    """Score every FEASIBLE Combination and assign ranks 1..n (FR-D7 to FR-D10).

    Non-feasible Combinations have their scores and rank cleared, since
    DATA_UNAVAILABLE and EXCLUDED options are never ranked (B.3.12).
    Returns the feasible Combinations in rank order.
    """
    feasible: list[Combination] = []
    for c in combinations:
        if c.feasibility is not FeasibilityStatus.FEASIBLE:
            c.attendance_score = c.travel_score = c.combined_score = None
            c.rank = None
            continue
        c.attendance_score = round(attendance_score(c.attendee_count, active_respondents), SCORE_PRECISION)
        c.travel_score = round(
            travel_score(travel_value(c, objective), max_journey_minutes), SCORE_PRECISION
        )
        c.combined_score = combined_score(c.attendance_score, c.travel_score, attendance_weight_percent)
        feasible.append(c)

    feasible.sort(key=_tie_break_key)
    for i, c in enumerate(feasible, start=1):
        c.rank = i
    return feasible
