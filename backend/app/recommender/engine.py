"""Recommender: the core engine behind Generate Recommendations (UC-09, UC-10).

Pipeline for one run, on a consistent snapshot of the Session:

  1. Enumerate Candidate Timeslots and attendance           FR-C1, FR-C2
  2. If needed, offer a clearly-labelled best available
     fallback below the requested threshold                  Prototype recovery flow
  3. Filter Venues by activity and shortlist nearest N       FR-C3 to FR-C6, C8
  4. Pair Timeslots with shortlisted Venues (Combinations)
  5. Exclude on attendance, group size, booking lead time    FR-D1, FR-D4, FR-D5
  6. Route each needed (Participant, Venue) pair once        FR-D2, UC-10, NFR-8
  7. Mark missing travel data, exclude over-long journeys    NFR-3, FR-D3
  8. Score and rank the feasible Combinations                FR-D6 to FR-D10

Routing is done once per (Participant, Venue) pair, not once per Combination,
and only for pairs that some surviving Combination needs. With P Participants
and a shortlist of N Venues this caps a run at P x N calls (SRS 5.1, C8).
"""

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Iterable
from datetime import datetime

from app.adapters.ports import Router, RouteResult
from app.recommender.candidate_generation import (
    compute_attendance,
    enumerate_timeslots,
    filter_venues,
    participant_centroid,
    shortlist_venues,
    validate_session,
)
from app.recommender.config import DEFAULT_CONFIG, RecommenderConfig
from app.recommender.feasibility import (
    journey_exclusion,
    journey_limit_exceeded,
    pre_routing_exclusion,
)
from app.recommender.scoring import score_and_rank, snap_weight
from app.recommender.types import (
    Combination,
    ExclusionReason,
    FeasibilityStatus,
    ParticipantInput,
    RecommendationRequest,
    RecommendationResult,
    RoutingStatus,
    RunStatus,
    TravelEstimate,
    TravelObjective,
    VenueInput,
)

PairKey = tuple[str, str]  # (participant_id, venue_id)


class RecommendationEngine:
    def __init__(self, router: Router, config: RecommenderConfig = DEFAULT_CONFIG) -> None:
        self.router = router
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(self, request: RecommendationRequest) -> RecommendationResult:
        """Run UC-09 end to end and return every Combination with its outcome."""
        cfg = self.config
        session = request.session
        validate_session(session, cfg)

        threshold = session.minimum_attendee_threshold or cfg.default_minimum_attendee_threshold
        weight = snap_weight(session.attendance_weight_percent, cfg.weight_increment_percent)
        result = RecommendationResult(
            session_id=session.session_id,
            status=RunStatus.OK,
            generated_at=request.now,
            active_respondents=sum(1 for p in request.participants if p.is_active),
            minimum_attendee_threshold=threshold,
            travel_objective=session.travel_objective,
            attendance_weight_percent=weight,
        )
        if session.minimum_attendee_threshold is None:
            result.warnings.append(
                f"Minimum-Attendee Threshold not set; using placeholder default {threshold} (TBD-2)."
            )

        # 1. FR-C1, FR-C2
        slots = enumerate_timeslots(
            session.date_range_start,
            session.date_range_end,
            session.duration_minutes,
            cfg.timeslot_step_minutes,
        )
        result.timeslots = compute_attendance(slots, request.participants)

        # 2. Keep the requested minimum as the normal hard threshold.  For the
        # prototype, avoid a dead-end when a group has responses but just
        # misses that target: rank the best-attended slots as explicitly
        # labelled near matches, provided at least the system minimum (two)
        # people can attend.  A one-person "group" is never suggested.
        effective_threshold = threshold
        if not any(t.available_count >= threshold for t in result.timeslots):
            best_available = max((t.available_count for t in result.timeslots), default=0)
            if best_available < cfg.default_minimum_attendee_threshold:
                result.status = RunStatus.NO_TIMESLOT_MEETS_THRESHOLD
                return result
            effective_threshold = best_available
            result.status = RunStatus.BEST_AVAILABLE_BELOW_THRESHOLD
            result.warnings.append(
                f"No timeslot reached the requested minimum of {threshold}; "
                f"showing best available options for {best_available}."
            )

        # 3. FR-C3, FR-C4
        venues = filter_venues(request.venues, session.activity_type_id)
        if not venues:
            result.status = RunStatus.NO_SUPPORTING_VENUES
            return result
        centre = participant_centroid(request.participants)
        if centre is None:
            result.status = RunStatus.NO_VALID_LOCATIONS
            return result
        result.centroid = centre
        result.shortlist = shortlist_venues(venues, centre, cfg.shortlist_size)

        # 4. Combinations
        result.combinations = [
            Combination(timeslot=t, shortlist_entry=entry, attendee_ids=t.available_ids)
            for t in result.timeslots
            for entry in result.shortlist
        ]

        # 5. FR-D1, FR-D4, FR-D5 before any routing call
        survivors: list[Combination] = []
        for combo in result.combinations:
            reason = pre_routing_exclusion(combo, effective_threshold, request.now)
            if reason is not None:
                _exclude(combo, reason)
            else:
                survivors.append(combo)

        # 6. FR-D2: one routing call per needed (Participant, Venue) pair
        participants = {p.participant_id: p for p in request.participants}
        estimates = await self._route_pairs(_needed_pairs(survivors), participants)
        result.routing_calls = sum(1 for e in estimates.values() if e[1])

        # 7. NFR-3 and FR-D3
        for combo in survivors:
            travel = tuple(
                _with_limit_flag(estimates[(pid, combo.venue.venue_id)][0], cfg.max_journey_minutes)
                for pid in combo.attendee_ids
            )
            combo.travel = travel
            if any(t.status is not RoutingStatus.AVAILABLE for t in travel):
                combo.feasibility = FeasibilityStatus.DATA_UNAVAILABLE
                continue
            reason = journey_exclusion(travel, cfg.max_journey_minutes)
            if reason is not None:
                _exclude(combo, reason)

        unavailable = sum(
            1 for c in result.combinations if c.feasibility is FeasibilityStatus.DATA_UNAVAILABLE
        )
        if unavailable:
            result.warnings.append(
                f"{unavailable} option(s) are missing travel data and are shown as unavailable (NFR-3)."
            )

        # 8. FR-D7 to FR-D10
        score_and_rank(
            result.combinations,
            objective=result.travel_objective,
            attendance_weight_percent=weight,
            active_respondents=result.active_respondents,
            max_journey_minutes=cfg.max_journey_minutes,
        )
        return result

    def rescore(
        self,
        result: RecommendationResult,
        *,
        travel_objective: TravelObjective | None = None,
        attendance_weight_percent: float | None = None,
    ) -> RecommendationResult:
        """Re-score and re-rank an existing result after the Organiser changes the
        Travel Objective (FR-D6) or weighting (FR-D9). Makes no routing calls."""
        if travel_objective is not None:
            result.travel_objective = travel_objective
        if attendance_weight_percent is not None:
            result.attendance_weight_percent = snap_weight(
                attendance_weight_percent, self.config.weight_increment_percent
            )
        score_and_rank(
            result.combinations,
            objective=result.travel_objective,
            attendance_weight_percent=result.attendance_weight_percent,
            active_respondents=result.active_respondents,
            max_journey_minutes=self.config.max_journey_minutes,
        )
        return result

    # ------------------------------------------------------------------
    # Routing (UC-10)
    # ------------------------------------------------------------------

    async def _route_pairs(
        self,
        pairs: dict[PairKey, tuple[VenueInput, datetime]],
        participants: dict[str, ParticipantInput],
    ) -> dict[PairKey, tuple[TravelEstimate, bool]]:
        """Route every pair concurrently, bounded by the configured limit.

        Returns each pair's estimate and whether a provider call was made.
        """
        semaphore = asyncio.Semaphore(self.config.max_concurrent_routing_calls)

        async def one(key: PairKey, venue: VenueInput, depart_at: datetime):
            participant = participants[key[0]]
            if not participant.has_valid_location:
                # Location missing or geocoding failed: travel data unavailable (NFR-3).
                return key, (
                    TravelEstimate(
                        participant_id=key[0],
                        venue_id=key[1],
                        transport_mode=participant.transport_mode,
                        minutes=None,
                        status=RoutingStatus.UNAVAILABLE,
                    ),
                    False,
                )
            async with semaphore:
                try:
                    route: RouteResult = await self.router.route(
                        participant.location,  # type: ignore[arg-type]
                        venue.location,
                        participant.transport_mode,
                        depart_at,
                    )
                except Exception as exc:  # adapters should not raise; be defensive
                    route = RouteResult(status=RoutingStatus.ERROR, detail=repr(exc))
            if route.status is RoutingStatus.AVAILABLE and route.minutes is not None:
                minutes, status = route.minutes, RoutingStatus.AVAILABLE
            elif route.status is RoutingStatus.AVAILABLE:
                minutes, status = None, RoutingStatus.ERROR  # "success" with no duration
            else:
                minutes, status = None, route.status
            return key, (
                TravelEstimate(
                    participant_id=key[0],
                    venue_id=key[1],
                    transport_mode=participant.transport_mode,
                    minutes=minutes,
                    status=status,
                ),
                True,
            )

        results = await asyncio.gather(*(one(k, v, d) for k, (v, d) in pairs.items()))
        return dict(results)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _exclude(combo: Combination, reason: ExclusionReason) -> None:
    combo.feasibility = FeasibilityStatus.EXCLUDED
    combo.exclusion_reason = reason


def _needed_pairs(
    combos: Iterable[Combination],
) -> dict[PairKey, tuple[VenueInput, datetime]]:
    """Unique (Participant, Venue) pairs, each with the earliest Timeslot start
    it is needed for. That start is used as the departure time for
    public-transport routing, whose duration depends on the time of day."""
    pairs: dict[PairKey, tuple[VenueInput, datetime]] = {}
    for c in combos:
        for pid in c.attendee_ids:
            key = (pid, c.venue.venue_id)
            existing = pairs.get(key)
            if existing is None or c.timeslot.start < existing[1]:
                pairs[key] = (c.venue, c.timeslot.start)
    return pairs


def _with_limit_flag(estimate: TravelEstimate, max_journey_minutes: int) -> TravelEstimate:
    return dataclasses.replace(
        estimate, journey_limit_exceeded=journey_limit_exceeded(estimate, max_journey_minutes)
    )
