"""Feasibility checks (SRS Section 4.4, FR-D1 and FR-D3 to FR-D5).

The checks that need no travel data (FR-D1, FR-D4, FR-D5) run before any
routing call, so excluded Combinations never cost an external request
(SRS C8, NFR-2). FR-D3 runs once travel durations are known.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.recommender.types import (
    Combination,
    ExclusionReason,
    TravelEstimate,
    VenueCategory,
)


def pre_routing_exclusion(
    combo: Combination,
    minimum_attendee_threshold: int,
    now: datetime,
) -> ExclusionReason | None:
    """FR-D1, FR-D4 and FR-D5, in that order. Returns the first reason that applies."""
    count = combo.attendee_count
    venue = combo.venue

    # FR-D1: attendance below the Session's Minimum-Attendee Threshold.
    if count < minimum_attendee_threshold:
        return ExclusionReason.BELOW_THRESHOLD

    if venue.category is VenueCategory.SPORTS_FACILITY:
        # FR-D4: attendance below the Venue's minimum group size.
        if venue.min_group_size is not None and count < venue.min_group_size:
            return ExclusionReason.GROUP_SIZE
        # FR-D5: Timeslot falls inside the Venue's required advance-booking window,
        # i.e. it starts sooner than the Venue's minimum booking lead time.
        if venue.advance_booking_lead_minutes:
            earliest_bookable = now + timedelta(minutes=venue.advance_booking_lead_minutes)
            if combo.timeslot.start < earliest_bookable:
                return ExclusionReason.BOOKING_LEAD_TIME

    return None


def journey_limit_exceeded(estimate: TravelEstimate, max_journey_minutes: int) -> bool | None:
    """Whether one attendee's journey is over the cap (B.3.13 JourneyLimitExceeded)."""
    if estimate.minutes is None:
        return None
    return estimate.minutes > max_journey_minutes


def journey_exclusion(
    travel: tuple[TravelEstimate, ...],
    max_journey_minutes: int,
) -> ExclusionReason | None:
    """FR-D3: exclude if any attending Participant's journey exceeds the cap."""
    if any(journey_limit_exceeded(t, max_journey_minutes) for t in travel):
        return ExclusionReason.JOURNEY_LIMIT
    return None
