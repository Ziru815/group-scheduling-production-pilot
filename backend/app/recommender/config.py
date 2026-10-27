"""System configuration for the recommendation engine (SRS Appendix B.4).

Several values are still open in SRS Appendix C. They are given working
placeholder defaults here so the engine runs and can be tested; each one is
marked with its TBD number and must be replaced once the client decides.
Do not treat the placeholders as requirements.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecommenderConfig:
    # TBD-1: maximum individual journey time used by FR-D3.
    # PLACEHOLDER. Client decision pending.
    max_journey_minutes: int = 60

    # TBD-2: number of Venues kept in the shortlist nearest the centroid (FR-C4).
    # PLACEHOLDER. NFR-1 is tested with up to 30, which is not a decision on N.
    shortlist_size: int = 10

    # TBD-2: fallback Minimum-Attendee Threshold when the Organiser leaves it unset.
    # PLACEHOLDER.
    default_minimum_attendee_threshold: int = 2

    # TBD-13: interval between successive Candidate Timeslot start times (FR-C1).
    # PLACEHOLDER.
    timeslot_step_minutes: int = 30

    # Upper bound on simultaneous routing requests, to stay inside the
    # provider's rate limit while still finishing within NFR-1.
    max_concurrent_routing_calls: int = 8

    # Permitted session duration (FR-A1.1).
    min_duration_minutes: int = 15
    max_duration_minutes: int = 480

    # Weight snapping step (FR-D9.1, B.4 WeightIncrementPercent).
    weight_increment_percent: int = 10

    def __post_init__(self) -> None:
        if self.max_journey_minutes <= 0:
            raise ValueError("max_journey_minutes must be positive")
        if self.shortlist_size <= 0:
            raise ValueError("shortlist_size must be positive")
        if self.timeslot_step_minutes <= 0:
            raise ValueError("timeslot_step_minutes must be positive")
        if self.max_concurrent_routing_calls <= 0:
            raise ValueError("max_concurrent_routing_calls must be positive")
        if 100 % self.weight_increment_percent != 0:
            raise ValueError("weight_increment_percent must divide 100")


DEFAULT_CONFIG = RecommenderConfig()
