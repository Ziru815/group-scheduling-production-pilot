"""End-to-end Generate Recommendations runs (UC-09, UC-10) with mock routing."""

from __future__ import annotations

from app.adapters.mock import MockRouter
from app.adapters.ports import RouteResult
from app.mock_data.loader import load_sample_request
from app.recommender.config import RecommenderConfig
from app.recommender.engine import RecommendationEngine
from app.recommender.types import (
    ExclusionReason,
    FeasibilityStatus,
    RecordStatus,
    RoutingStatus,
    RunStatus,
    TravelObjective,
    VenueCategory,
)

from .conftest import AMK, BISHAN, JURONG, TAMPINES, TOA_PAYOH, person, request, session, venue

VENUES = [venue("v-bishan", BISHAN), venue("v-tp", TOA_PAYOH), venue("v-amk", AMK), venue("v-jurong", JURONG)]


def test_no_qualifying_timeslot_makes_no_routing_calls(run):
    router = MockRouter()
    people = [person("a", (8, 10)), person("b", (11, 13))]  # never two at once
    result = run(RecommendationEngine(router).generate(request(session(threshold=2), people, VENUES)))
    assert result.status is RunStatus.NO_TIMESLOT_MEETS_THRESHOLD
    assert router.calls == [] and result.combinations == []


def test_best_available_fallback_avoids_dead_end_for_two_of_three(run):
    router = MockRouter()
    people = [
        person("short", (8, 9.5)),
        person("a", (8, 10)),
        person("b", (8, 10)),
    ]
    result = run(
        RecommendationEngine(router).generate(
            request(session(duration=120, threshold=3), people, VENUES)
        )
    )

    assert result.status is RunStatus.BEST_AVAILABLE_BELOW_THRESHOLD
    assert result.ranked
    assert all(combo.attendee_count == 2 for combo in result.ranked)
    assert any("requested minimum of 3" in warning for warning in result.warnings)


def test_routing_is_bounded_by_participants_times_shortlist(run):
    router = MockRouter()
    people = [person(f"p{i}", (8, 14), location=loc) for i, loc in enumerate([BISHAN, AMK, TOA_PAYOH, TAMPINES])]
    cfg = RecommenderConfig(shortlist_size=3)
    result = run(RecommendationEngine(router, cfg).generate(request(session(), people, VENUES)))
    assert result.status is RunStatus.OK
    assert len(result.shortlist) == 3
    assert len(router.calls) == result.routing_calls <= 4 * 3  # C8 / SRS 5.1
    assert len({(o, d) for o, d, *_ in router.calls}) == len(router.calls)  # each pair once


def test_withdrawn_and_unresponsive_participants_are_ignored(run):
    router = MockRouter()
    people = [
        person("a", (8, 14)),
        person("b", (8, 14)),
        person("w", (8, 14), status=RecordStatus.WITHDRAWN, location=TAMPINES),
        person("n", status=None, location=None),
    ]
    result = run(RecommendationEngine(router).generate(request(session(), people, VENUES)))
    assert result.active_respondents == 2
    for c in result.combinations:
        assert set(c.attendee_ids) <= {"a", "b"}
    assert all(o == BISHAN for o, *_ in router.calls)  # nobody else was routed


def test_routing_failure_marks_data_unavailable_not_excluded(run):
    router = MockRouter(unavailable_origins=[AMK])
    people = [person("a", (8, 14), location=BISHAN), person("b", (8, 14), location=AMK)]
    result = run(RecommendationEngine(router).generate(request(session(), people, VENUES)))
    assert result.combinations
    for c in result.combinations:
        assert c.feasibility is FeasibilityStatus.DATA_UNAVAILABLE
        assert c.exclusion_reason is None and c.rank is None
        b = next(t for t in c.travel if t.participant_id == "b")
        assert b.status is RoutingStatus.UNAVAILABLE and b.minutes is None
    assert result.ranked == []
    assert any("NFR-3" in w for w in result.warnings)


def test_router_exception_is_contained(run):
    class Exploding:
        async def route(self, *args):
            raise RuntimeError("boom")

    people = [person("a", (8, 14)), person("b", (8, 14))]
    result = run(RecommendationEngine(Exploding()).generate(request(session(), people, VENUES)))
    assert all(c.feasibility is FeasibilityStatus.DATA_UNAVAILABLE for c in result.combinations)
    assert all(t.status is RoutingStatus.ERROR for c in result.combinations for t in c.travel)


def test_route_success_without_minutes_is_an_error(run):
    class NoMinutes:
        async def route(self, *args):
            return RouteResult(status=RoutingStatus.AVAILABLE, minutes=None)

    people = [person("a", (8, 14)), person("b", (8, 14))]
    result = run(RecommendationEngine(NoMinutes()).generate(request(session(), people, VENUES)))
    assert all(t.status is RoutingStatus.ERROR for c in result.combinations for t in c.travel)


def test_journey_limit_excludes_whole_combination(run):
    people = [person("near", (8, 14), location=BISHAN), person("far", (8, 14), location=JURONG)]
    cfg = RecommenderConfig(max_journey_minutes=30)
    result = run(RecommendationEngine(MockRouter(), cfg).generate(request(session(), people, VENUES)))
    by_venue = {c.venue.venue_id: c for c in result.combinations if c.timeslot.index == 0}
    assert by_venue["v-bishan"].exclusion_reason is ExclusionReason.JOURNEY_LIMIT
    flags = {t.participant_id: t.journey_limit_exceeded for t in by_venue["v-bishan"].travel}
    assert flags == {"near": False, "far": True}


def test_group_size_and_lead_time_exclusions_run_before_routing(run):
    router = MockRouter()
    stadium = venue("v-stadium", BISHAN, category=VenueCategory.SPORTS_FACILITY, min_group=6)
    people = [person("a", (8, 14)), person("b", (8, 14))]
    result = run(RecommendationEngine(router).generate(request(session(), people, [stadium])))
    assert {c.exclusion_reason for c in result.combinations} == {ExclusionReason.GROUP_SIZE}
    assert router.calls == []


def test_rescore_changes_ranking_without_routing(run):
    router = MockRouter()
    engine = RecommendationEngine(router)
    result = run(engine.generate(load_sample_request()))
    calls = len(router.calls)
    first = [c.combined_score for c in result.ranked]
    engine.rescore(result, travel_objective=TravelObjective.MIN_TOTAL, attendance_weight_percent=33)
    assert result.attendance_weight_percent == 30
    assert len(router.calls) == calls
    assert [c.combined_score for c in result.ranked] != first
    assert [c.rank for c in result.ranked] == list(range(1, len(result.ranked) + 1))


def test_sample_session_end_to_end(run):
    result = run(RecommendationEngine(MockRouter()).generate(load_sample_request()))
    assert result.status is RunStatus.OK
    assert result.active_respondents == 7  # Hui Min withdrew, Ivan never responded
    assert result.ranked, "the mock Session should produce at least one option"
    best = result.ranked[0]
    assert best.feasibility is FeasibilityStatus.FEASIBLE
    assert best.combined_score is not None and 0 <= best.combined_score <= 1
    assert len(best.travel) == best.attendee_count
    assert all(t.status is RoutingStatus.AVAILABLE for t in best.travel)
    assert result.routing_calls <= 7 * len(result.shortlist)


def test_nfr1_scale_scores_well_within_budget(run):
    """NFR-1 scenario: 12 Participants, 30 shortlisted Venues, a 7-day range at
    30-minute steps. With instant mock routing this measures only the engine's
    own work, which must leave most of the 5-second budget for nothing else."""
    import random
    import time

    from app.recommender.types import Coordinates

    rng = random.Random(7)

    def spot():
        return Coordinates(1.30 + rng.random() * 0.12, 103.70 + rng.random() * 0.25)

    days = [(8 + 24 * d, 22 + 24 * d) for d in range(7)]
    people = [person(f"p{i}", *days, location=spot()) for i in range(12)]
    venues = [venue(f"v{i}", spot()) for i in range(40)]
    sess = session(start=8, end=8 + 24 * 7, duration=120, threshold=6)
    cfg = RecommenderConfig(shortlist_size=30, max_journey_minutes=120)

    t0 = time.perf_counter()
    result = run(RecommendationEngine(MockRouter(), cfg).generate(request(sess, people, venues)))
    elapsed = time.perf_counter() - t0

    assert len(result.shortlist) == 30
    assert result.routing_calls <= 12 * 30
    assert len(result.combinations) > 5000
    assert elapsed < 2.0, f"engine took {elapsed:.2f}s"
