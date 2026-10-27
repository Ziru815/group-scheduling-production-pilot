from uuid import uuid4
from app.models import Combination, FeasibilityStatus, SchedulingSession


def test_source_revision_makes_old_combination_detectably_stale():
    session = SchedulingSession(session_id=uuid4(), name="S", activity_type_id=uuid4(), date_range_start="2026-10-20T09:00:00Z", date_range_end="2026-10-20T11:00:00Z", response_deadline="2026-10-19T09:00:00Z", invitation_token="t", source_revision=3)
    combination = Combination(session_id=session.session_id, candidate_timeslot_id=uuid4(), venue_id=uuid4(), feasibility_status=FeasibilityStatus.FEASIBLE, source_revision=2)
    assert combination.source_revision != session.source_revision

