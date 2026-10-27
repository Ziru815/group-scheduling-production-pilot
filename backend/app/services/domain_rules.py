"""Pure domain calculations, deliberately independent of FastAPI and the database."""
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt

from app.models.enums import TravelObjective


def enumerate_timeslots(start: datetime, end: datetime, duration_minutes: int, step_minutes: int) -> list[tuple[datetime, datetime]]:
    if start >= end or duration_minutes <= 0 or step_minutes <= 0:
        raise ValueError("Invalid timeslot range, duration or step")
    result, cursor = [], start
    duration, step = timedelta(minutes=duration_minutes), timedelta(minutes=step_minutes)
    while cursor + duration <= end:
        result.append((cursor, cursor + duration))
        cursor += step
        if len(result) > 5000:
            raise ValueError("Candidate range creates more than 5000 timeslots")
    return result


def interval_covers(interval_start: datetime, interval_end: datetime, slot_start: datetime, slot_end: datetime) -> bool:
    return interval_start <= slot_start and interval_end >= slot_end


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * radius * asin(sqrt(a))


def attendance_score(attendee_count: int, participant_count: int) -> float:
    if participant_count <= 0: return 0.0
    return round(100.0 * attendee_count / participant_count, 4)


def travel_score(durations: list[int], participant_count: int, journey_cap: int, objective: TravelObjective) -> float | None:
    if participant_count <= 0 or journey_cap <= 0 or len(durations) != participant_count:
        return None
    if any(value < 0 or value > journey_cap for value in durations):
        return None
    burden = sum(durations) / (participant_count * journey_cap) if objective == TravelObjective.MIN_TOTAL else max(durations) / journey_cap
    return round(max(0.0, 100.0 * (1.0 - burden)), 4)


def combined_score(attendance: float, travel: float, attendance_weight_percent: int, travel_weight_percent: int) -> float:
    if attendance_weight_percent + travel_weight_percent != 100:
        raise ValueError("Weights must total 100")
    return round(attendance * attendance_weight_percent / 100 + travel * travel_weight_percent / 100, 4)

