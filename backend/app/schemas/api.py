from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import FeasibilityStatus, LocationInputType, SubmissionSource, TransportMode, TravelObjective


class DTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GoogleLoginRequest(DTO): id_token: str
class DevLoginRequest(DTO): email: str; display_name: str


class AuthResponse(DTO):
    access_token: str
    token_type: str = "bearer"
    account_id: UUID
    display_name: str


class SessionCreate(DTO):
    name: str = Field(min_length=1, max_length=160)
    activity_type_id: UUID
    date_range_start: datetime
    date_range_end: datetime
    timezone: str = "Asia/Singapore"
    duration_minutes: Annotated[int, Field(ge=15, le=480)] = 60
    response_deadline: datetime
    minimum_attendee_threshold: int = Field(default=2, ge=1)
    travel_objective: TravelObjective = TravelObjective.MIN_MAX_INDIVIDUAL
    attendance_weight_percent: Annotated[int, Field(ge=0, le=100, multiple_of=10)] = 60
    travel_weight_percent: Annotated[int, Field(ge=0, le=100, multiple_of=10)] = 40

    @model_validator(mode="after")
    def validate_window(self):
        if self.date_range_start >= self.date_range_end:
            raise ValueError("date_range_start must be before date_range_end")
        if self.response_deadline >= self.date_range_start:
            raise ValueError("response_deadline must be before date_range_start")
        if self.attendance_weight_percent + self.travel_weight_percent != 100:
            raise ValueError("attendance and travel weights must total 100")
        return self


class SessionUpdate(DTO):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None
    response_deadline: datetime | None = None
    duration_minutes: Annotated[int | None, Field(ge=15, le=480)] = None
    minimum_attendee_threshold: int | None = Field(default=None, ge=1)


class SessionPublic(DTO):
    session_id: UUID
    name: str
    activity_type_id: UUID
    date_range_start: datetime
    date_range_end: datetime
    timezone: str
    duration_minutes: int
    response_deadline: datetime
    minimum_attendee_threshold: int
    travel_objective: TravelObjective
    attendance_weight_percent: int
    travel_weight_percent: int
    status: str
    source_revision: int


class SessionManagement(SessionPublic):
    invitation_token: str
    organiser_participant_id: UUID
    confirmed_combination_id: UUID | None


class JoinRequest(DTO): invitation_token: str


class ParticipantPublic(DTO):
    participant_id: UUID
    display_name: str
    role: str
    response_status: str


class AvailabilityIntervalInput(DTO):
    start_date_time: datetime
    end_date_time: datetime

    @model_validator(mode="after")
    def end_after_start(self):
        if self.start_date_time >= self.end_date_time:
            raise ValueError("availability interval start must be before end")
        return self


class AvailabilitySubmit(DTO):
    location_input_type: LocationInputType
    location_input: str = Field(min_length=1, max_length=300)
    transport_mode: TransportMode
    submission_source: SubmissionSource = SubmissionSource.MANUAL
    intervals: list[AvailabilityIntervalInput] = Field(default_factory=list)


class AvailabilityOwn(DTO):
    record_id: UUID
    location_input_type: LocationInputType
    location_input: str
    latitude: float | None
    longitude: float | None
    geocode_status: str
    transport_mode: TransportMode
    submission_source: SubmissionSource
    record_status: str
    intervals: list[AvailabilityIntervalInput]


class RecommendationSettings(DTO):
    travel_objective: TravelObjective
    attendance_weight_percent: Annotated[int, Field(ge=0, le=100, multiple_of=10)]
    travel_weight_percent: Annotated[int, Field(ge=0, le=100, multiple_of=10)]

    @model_validator(mode="after")
    def weights_total(self):
        if self.attendance_weight_percent + self.travel_weight_percent != 100:
            raise ValueError("weights must total 100")
        return self


class RankedCombination(DTO):
    combination_id: UUID
    start_date_time: datetime
    end_date_time: datetime
    venue_id: UUID
    venue_name: str
    venue_address: str
    attendee_count: int
    feasibility_status: FeasibilityStatus
    exclusion_reason: str | None
    attendance_score: float | None
    travel_score: float | None
    combined_score: float | None
    rank: int | None
    outdated: bool


class GenerateResult(DTO):
    source_revision: int
    timeslots_created: int
    shortlist_created: int
    combinations_created: int
    data_unavailable_count: int


class ConfirmRequest(DTO): expected_source_revision: int
class Message(DTO): message: str

