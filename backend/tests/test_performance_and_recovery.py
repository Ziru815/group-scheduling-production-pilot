from datetime import datetime, timedelta, timezone
from app.services.domain_rules import enumerate_timeslots


def test_seven_day_candidate_enumeration_is_bounded():
    start = datetime(2026, 10, 20, tzinfo=timezone.utc)
    slots = enumerate_timeslots(start, start + timedelta(days=7), 60, 15)
    assert 0 < len(slots) < 5000

