from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

from app.schemas import AvailabilityIntervalInput, SessionCreate


def test_session_rejects_deadline_after_start_and_invalid_weights():
    start = datetime.now(timezone.utc) + timedelta(days=3)
    with pytest.raises(ValidationError):
        SessionCreate(name="Bad", activity_type_id="00000000-0000-0000-0000-000000000001", date_range_start=start, date_range_end=start + timedelta(hours=2), response_deadline=start, attendance_weight_percent=50, travel_weight_percent=40)


def test_interval_requires_positive_duration():
    instant = datetime.now(timezone.utc)
    with pytest.raises(ValidationError): AvailabilityIntervalInput(start_date_time=instant, end_date_time=instant)

