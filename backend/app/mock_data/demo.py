"""Run the recommender on the mock Session and print the outcome.

    cd backend
    python -m app.mock_data.demo            # mock routing, no network
    python -m app.mock_data.demo --onemap   # real OneMap routing; needs ONEMAP_EMAIL and ONEMAP_PASSWORD
"""

from __future__ import annotations

import argparse
import asyncio
import os
from collections import Counter

from app.adapters.mock import MockRouter
from app.mock_data.loader import load_sample_request
from app.recommender.engine import RecommendationEngine
from app.recommender.types import Combination, FeasibilityStatus, RecommendationResult, TravelObjective


def _fmt(c: Combination, names: dict[str, str]) -> str:
    t = c.timeslot
    when = f"{t.start:%a %d %b %H:%M}-{t.end:%H:%M}"
    travel = ", ".join(f"{names[e.participant_id].split()[0]} {e.minutes}m" for e in c.travel)
    return (
        f"#{c.rank:<2} {c.combined_score:.3f}  {when}  {c.venue.name:<26} "
        f"att {c.attendee_count} ({c.attendance_score:.2f})  travel {c.travel_score:.2f}  "
        f"max {c.max_travel_minutes}m\n      {travel}"
    )


def report(result: RecommendationResult, names: dict[str, str], top: int = 5) -> None:
    print(f"Run status: {result.status.value}   routing calls: {result.routing_calls}")
    print(
        f"Objective: {result.travel_objective.value}   attendance weight: "
        f"{result.attendance_weight_percent}%   threshold: {result.minimum_attendee_threshold}"
    )
    if result.centroid:
        print(f"Centroid: {result.centroid.lat:.4f}, {result.centroid.lng:.4f}")
    print("Shortlist: " + ", ".join(f"{e.rank}. {e.venue.name}" for e in result.shortlist))
    outcomes = Counter(
        c.exclusion_reason.value if c.exclusion_reason else c.feasibility.value
        for c in result.combinations
    )
    print("Outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())))
    for w in result.warnings:
        print(f"Warning: {w}")
    print(f"\nTop {top}:")
    for c in result.top(top):
        print(_fmt(c, names))
    if not result.ranked:
        print("  (no feasible option)")


async def main(use_onemap: bool) -> None:
    request = load_sample_request()
    names = {p.participant_id: p.display_name for p in request.participants}

    if use_onemap:
        from app.adapters.onemap import OneMapAdapter

        router = OneMapAdapter(
            email=os.environ.get("ONEMAP_EMAIL"),
            password=os.environ.get("ONEMAP_PASSWORD"),
            token=os.environ.get("ONEMAP_TOKEN"),
        )
    else:
        router = MockRouter()

    engine = RecommendationEngine(router)
    try:
        result = await engine.generate(request)
        report(result, names)

        print("\n--- Organiser switches to MIN_TOTAL and 30% attendance (no new routing) ---")
        before = result.routing_calls
        engine.rescore(result, travel_objective=TravelObjective.MIN_TOTAL, attendance_weight_percent=33)
        report(result, names, top=3)
        assert result.routing_calls == before
    finally:
        if use_onemap:
            await router.aclose()  # type: ignore[union-attr]

    feasible = sum(1 for c in result.combinations if c.feasibility is FeasibilityStatus.FEASIBLE)
    print(f"\n{feasible} feasible of {len(result.combinations)} Combinations.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--onemap", action="store_true", help="route with the real OneMap API")
    asyncio.run(main(parser.parse_args().onemap))
