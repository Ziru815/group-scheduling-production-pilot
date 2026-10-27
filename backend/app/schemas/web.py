"""Request models for the React frontend's camelCase API contract."""

from datetime import date, datetime, time
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import LocationInputType, TransportMode, TravelObjective


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class WebDTO(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class WebSessionCreate(WebDTO):
    name: str = Field(min_length=1, max_length=160)
    activity_type_id: UUID
    start_date: date
    end_date: date
    daily_start_time: time
    daily_end_time: time
    timezone: str = "Asia/Singapore"
    duration_minutes: Annotated[int, Field(ge=15, le=480)]
    response_deadline: datetime
    minimum_attendees: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_window(self):
        if self.start_date > self.end_date:
            raise ValueError("startDate must not be after endDate")
        if self.daily_start_time >= self.daily_end_time:
            raise ValueError("dailyStartTime must be before dailyEndTime")
        return self


class WebSessionUpdate(WebDTO):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    start_date: date | None = None
    end_date: date | None = None
    daily_start_time: time | None = None
    daily_end_time: time | None = None
    duration_minutes: Annotated[int | None, Field(default=None, ge=15, le=480)]
    response_deadline: datetime | None = None
    minimum_attendees: int | None = Field(default=None, ge=1)
    travel_objective: TravelObjective | None = None
    attendance_weight_percent: Annotated[int | None, Field(default=None, ge=0, le=100, multiple_of=10)]


class InvitationTokenRequest(WebDTO):
    token: str = Field(min_length=1, max_length=256)


class LocationSearchRequest(WebDTO):
    query: str = Field(min_length=1, max_length=300)


class LocationSelection(WebDTO):
    input_type: LocationInputType
    input: str = Field(min_length=1, max_length=300)
    candidate_id: str = Field(min_length=1)


class TimeIntervalRequest(WebDTO):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def end_after_start(self):
        if self.start >= self.end:
            raise ValueError("interval start must be before end")
        return self


class SaveResponseRequest(WebDTO):
    intervals: list[TimeIntervalRequest] = Field(default_factory=list)
    calendar_assisted: bool = False
    transport_mode: TransportMode
    location: LocationSelection | None = None
    confirm_unavailable: bool = False

    @model_validator(mode="after")
    def require_zero_availability_confirmation(self):
        if not self.intervals and not self.confirm_unavailable:
            raise ValueError("confirmUnavailable must be true when no time is selected")
        return self


class ConfirmPlanRequest(WebDTO):
    combination_id: UUID


class DemoSignInRequest(WebDTO):
    user_id: str = Field(min_length=1, max_length=80)

