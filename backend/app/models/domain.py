"""SQLModel persistence model matching the final Lab 3 class/domain diagrams.

Relationships use explicit foreign keys. Cross-row invariants (same-session checks,
exactly one organiser and result freshness) are enforced in the service layer.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, Enum as SAEnum, ForeignKey, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from .enums import *


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def enum_column(enum_type, default):
    return Column(SAEnum(enum_type, native_enum=False), nullable=False, default=default)


class UserAccount(SQLModel, table=True):
    __tablename__ = "user_accounts"
    __table_args__ = (UniqueConstraint("auth_provider", "provider_user_id"),)
    account_id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=320)
    display_name: str = Field(max_length=120)
    auth_provider: str = Field(default="GOOGLE", max_length=30)
    provider_user_id: str = Field(index=True, max_length=255)
    account_status: str = Field(default="ACTIVE", max_length=30)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    last_login_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class ActivityType(SQLModel, table=True):
    __tablename__ = "activity_types"
    activity_type_id: UUID = Field(default_factory=uuid4, primary_key=True)
    category: str = Field(max_length=80)
    name: str = Field(index=True, unique=True, max_length=120)
    is_active: bool = True


class SchedulingSession(SQLModel, table=True):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("date_range_start < date_range_end", name="ck_session_dates"),
        CheckConstraint("duration_minutes BETWEEN 15 AND 480", name="ck_session_duration"),
        CheckConstraint("minimum_attendee_threshold > 0", name="ck_session_min_attendees"),
        CheckConstraint("attendance_weight_percent + travel_weight_percent = 100", name="ck_session_weights_total"),
    )
    session_id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=160)
    activity_type_id: UUID = Field(foreign_key="activity_types.activity_type_id", index=True)
    organiser_participant_id: Optional[UUID] = Field(default=None, sa_column=Column(Uuid, ForeignKey("participants.participant_id", name="fk_session_organiser", use_alter=True), nullable=True))
    date_range_start: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    date_range_end: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    timezone: str = Field(default="Asia/Singapore", max_length=64)
    duration_minutes: int = 60
    response_deadline: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    minimum_attendee_threshold: int = 2
    travel_objective: TravelObjective = Field(default=TravelObjective.MIN_MAX_INDIVIDUAL, sa_column=enum_column(TravelObjective, TravelObjective.MIN_MAX_INDIVIDUAL))
    attendance_weight_percent: int = 60
    travel_weight_percent: int = 40
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, sa_column=enum_column(SessionStatus, SessionStatus.ACTIVE))
    invitation_token: str = Field(index=True, unique=True, max_length=128)
    confirmed_combination_id: Optional[UUID] = Field(default=None, sa_column=Column(Uuid, ForeignKey("combinations.combination_id", name="fk_session_confirmed_combination", use_alter=True), nullable=True))
    source_revision: int = 1
    recommendations_source_revision: Optional[int] = None
    recommendations_run_status: Optional[str] = Field(default=None, max_length=80)
    recommendations_generated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    confirmed_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class Participant(SQLModel, table=True):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("session_id", "user_account_id"),)
    participant_id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_account_id: UUID = Field(foreign_key="user_accounts.account_id", index=True)
    session_id: UUID = Field(foreign_key="sessions.session_id", index=True)
    display_name: str = Field(max_length=120)
    role: ParticipantRole = Field(default=ParticipantRole.PARTICIPANT, sa_column=enum_column(ParticipantRole, ParticipantRole.PARTICIPANT))
    response_status: ResponseStatus = Field(default=ResponseStatus.NOT_SUBMITTED, sa_column=enum_column(ResponseStatus, ResponseStatus.NOT_SUBMITTED))
    joined_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class AvailabilityRecord(SQLModel, table=True):
    __tablename__ = "availability_records"
    record_id: UUID = Field(default_factory=uuid4, primary_key=True)
    participant_id: UUID = Field(foreign_key="participants.participant_id", index=True)
    location_input_type: LocationInputType = Field(sa_column=enum_column(LocationInputType, LocationInputType.ADDRESS))
    location_input: str = Field(max_length=300)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geocode_status: GeocodeStatus = Field(default=GeocodeStatus.PENDING, sa_column=enum_column(GeocodeStatus, GeocodeStatus.PENDING))
    transport_mode: TransportMode = Field(sa_column=enum_column(TransportMode, TransportMode.PUBLIC_TRANSPORT))
    submission_source: SubmissionSource = Field(default=SubmissionSource.MANUAL, sa_column=enum_column(SubmissionSource, SubmissionSource.MANUAL))
    record_status: RecordStatus = Field(default=RecordStatus.ACTIVE, sa_column=enum_column(RecordStatus, RecordStatus.ACTIVE))
    source_revision: int = 1
    submitted_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    withdrawn_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class AvailabilityInterval(SQLModel, table=True):
    __tablename__ = "availability_intervals"
    __table_args__ = (CheckConstraint("start_date_time < end_date_time", name="ck_availability_interval"),)
    interval_id: UUID = Field(default_factory=uuid4, primary_key=True)
    availability_record_id: UUID = Field(foreign_key="availability_records.record_id", index=True)
    start_date_time: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    end_date_time: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    interval_type: IntervalType = Field(default=IntervalType.AVAILABLE, sa_column=enum_column(IntervalType, IntervalType.AVAILABLE))
    interval_source: IntervalSource = Field(default=IntervalSource.MANUAL, sa_column=enum_column(IntervalSource, IntervalSource.MANUAL))


class Venue(SQLModel, table=True):
    __tablename__ = "venues"
    __table_args__ = (
        UniqueConstraint(
            "data_source",
            "source_key",
            name="uq_venues_data_source_source_key",
        ),
    )
    venue_id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True, max_length=180)
    category: VenueCategory = Field(sa_column=enum_column(VenueCategory, VenueCategory.SPORTS_FACILITY))
    address: str = Field(max_length=300)
    postal_code: Optional[str] = Field(default=None, max_length=6)
    latitude: float
    longitude: float
    data_source: str = Field(max_length=100)
    source_key: Optional[str] = Field(default=None, max_length=64)
    last_synced_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    is_active: bool = True
    verification_status: VenueVerificationStatus = Field(
        default=VenueVerificationStatus.UNVERIFIED,
        sa_column=enum_column(
            VenueVerificationStatus,
            VenueVerificationStatus.UNVERIFIED,
        ),
    )
    minimum_group_size: Optional[int] = None
    optimal_group_size: Optional[int] = None
    advance_booking_lead_minutes: Optional[int] = None


class VenueActivity(SQLModel, table=True):
    __tablename__ = "venue_activities"
    __table_args__ = (UniqueConstraint("venue_id", "activity_type_id"),)
    venue_activity_id: UUID = Field(default_factory=uuid4, primary_key=True)
    venue_id: UUID = Field(foreign_key="venues.venue_id", index=True)
    activity_type_id: UUID = Field(foreign_key="activity_types.activity_type_id", index=True)
    support_status: SupportStatus = Field(default=SupportStatus.SUPPORTED, sa_column=enum_column(SupportStatus, SupportStatus.SUPPORTED))
    source_reference: Optional[str] = Field(default=None, max_length=300)


class CandidateTimeslot(SQLModel, table=True):
    __tablename__ = "candidate_timeslots"
    __table_args__ = (UniqueConstraint("session_id", "start_date_time", "end_date_time"),)
    timeslot_id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_id: UUID = Field(foreign_key="sessions.session_id", index=True)
    start_date_time: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    end_date_time: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    generation_status: GenerationStatus = Field(default=GenerationStatus.GENERATED, sa_column=enum_column(GenerationStatus, GenerationStatus.GENERATED))
    available_count: int = 0
    source_revision: int = 1


class TimeslotAttendance(SQLModel, table=True):
    __tablename__ = "timeslot_attendance"
    __table_args__ = (UniqueConstraint("candidate_timeslot_id", "participant_id"),)
    attendance_id: UUID = Field(default_factory=uuid4, primary_key=True)
    candidate_timeslot_id: UUID = Field(foreign_key="candidate_timeslots.timeslot_id", index=True)
    participant_id: UUID = Field(foreign_key="participants.participant_id", index=True)
    attendance_status: AttendanceStatus = Field(sa_column=enum_column(AttendanceStatus, AttendanceStatus.NO_RESPONSE))
    source: AttendanceSource = Field(default=AttendanceSource.NONE, sa_column=enum_column(AttendanceSource, AttendanceSource.NONE))
    reason_code: Optional[str] = Field(default=None, max_length=80)


class VenueShortlistEntry(SQLModel, table=True):
    __tablename__ = "venue_shortlist_entries"
    __table_args__ = (UniqueConstraint("session_id", "venue_id", "source_revision"),)
    entry_id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_id: UUID = Field(foreign_key="sessions.session_id", index=True)
    venue_id: UUID = Field(foreign_key="venues.venue_id", index=True)
    centroid_latitude: float
    centroid_longitude: float
    straight_line_distance_km: float
    shortlist_rank: int
    shortlist_status: ShortlistStatus = Field(default=ShortlistStatus.CURRENT, sa_column=enum_column(ShortlistStatus, ShortlistStatus.CURRENT))
    source_revision: int = 1


class Combination(SQLModel, table=True):
    __tablename__ = "combinations"
    __table_args__ = (UniqueConstraint("session_id", "candidate_timeslot_id", "venue_id", "source_revision"),)
    combination_id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_id: UUID = Field(foreign_key="sessions.session_id", index=True)
    candidate_timeslot_id: UUID = Field(foreign_key="candidate_timeslots.timeslot_id", index=True)
    venue_id: UUID = Field(foreign_key="venues.venue_id", index=True)
    attendee_count: int = 0
    feasibility_status: FeasibilityStatus = Field(default=FeasibilityStatus.DATA_UNAVAILABLE, sa_column=enum_column(FeasibilityStatus, FeasibilityStatus.DATA_UNAVAILABLE))
    exclusion_reason: Optional[str] = Field(default=None, max_length=240)
    attendance_score: Optional[float] = None
    travel_score: Optional[float] = None
    combined_score: Optional[float] = None
    rank: Optional[int] = None
    status: CombinationStatus = Field(default=CombinationStatus.CANDIDATE, sa_column=enum_column(CombinationStatus, CombinationStatus.CANDIDATE))
    source_revision: int = 1


class TravelEstimate(SQLModel, table=True):
    __tablename__ = "travel_estimates"
    __table_args__ = (UniqueConstraint("combination_id", "participant_id", "source_revision"),)
    estimate_id: UUID = Field(default_factory=uuid4, primary_key=True)
    combination_id: UUID = Field(foreign_key="combinations.combination_id", index=True)
    participant_id: UUID = Field(foreign_key="participants.participant_id", index=True)
    transport_mode: TransportMode = Field(sa_column=enum_column(TransportMode, TransportMode.PUBLIC_TRANSPORT))
    travel_duration_minutes: Optional[int] = None
    routing_status: RoutingStatus = Field(sa_column=enum_column(RoutingStatus, RoutingStatus.UNAVAILABLE))
    journey_limit_exceeded: Optional[bool] = None
    provider: Optional[str] = Field(default=None, max_length=60)
    request_time: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    source_revision: int = 1


class CalendarConnection(SQLModel, table=True):
    __tablename__ = "calendar_connections"
    __table_args__ = (UniqueConstraint("participant_id"),)
    connection_id: UUID = Field(default_factory=uuid4, primary_key=True)
    participant_id: UUID = Field(foreign_key="participants.participant_id", index=True)
    provider: CalendarProvider = Field(default=CalendarProvider.GOOGLE, sa_column=enum_column(CalendarProvider, CalendarProvider.GOOGLE))
    connection_status: ConnectionStatus = Field(default=ConnectionStatus.DISCONNECTED, sa_column=enum_column(ConnectionStatus, ConnectionStatus.DISCONNECTED))
    granted_scopes: str = Field(default="", max_length=500)
    credential_reference: Optional[str] = Field(default=None, max_length=500)


class CalendarEvent(SQLModel, table=True):
    __tablename__ = "calendar_events"
    __table_args__ = (UniqueConstraint("calendar_connection_id", "session_id", "candidate_timeslot_id", "event_type"),)
    event_id: UUID = Field(default_factory=uuid4, primary_key=True)
    calendar_connection_id: UUID = Field(foreign_key="calendar_connections.connection_id", index=True)
    session_id: UUID = Field(foreign_key="sessions.session_id", index=True)
    candidate_timeslot_id: UUID = Field(foreign_key="candidate_timeslots.timeslot_id")
    combination_id: Optional[UUID] = Field(default=None, foreign_key="combinations.combination_id")
    event_type: EventType = Field(sa_column=enum_column(EventType, EventType.TENTATIVE_HOLD))
    event_status: EventStatus = Field(default=EventStatus.PENDING, sa_column=enum_column(EventStatus, EventStatus.PENDING))
    provider_event_id: Optional[str] = Field(default=None, max_length=500)
    last_error: Optional[str] = Field(default=None, max_length=500)

