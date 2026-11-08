"""Aggregate repositories. All writes are flushed; services own transaction commits."""
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, col, delete, select

from app.models import (
    ActivityType, AvailabilityInterval, AvailabilityRecord, CalendarConnection,
    CalendarCredential,
    CalendarEvent, CandidateTimeslot, Combination, Participant, RecordStatus,
    SchedulingSession, ShortlistStatus, TimeslotAttendance, TravelEstimate,
    UserAccount, Venue, VenueActivity, VenueShortlistEntry,
    VenueVerificationStatus,
)


class UserAccountRepository:
    def __init__(self, db: Session): self.db = db
    def by_provider(self, provider: str, subject: str):
        return self.db.exec(select(UserAccount).where(UserAccount.auth_provider == provider, UserAccount.provider_user_id == subject)).first()
    def by_email(self, email: str): return self.db.exec(select(UserAccount).where(UserAccount.email == email)).first()
    def save(self, item): self.db.add(item); self.db.flush(); return item


class SessionRepository:
    def __init__(self, db: Session): self.db = db
    def get(self, session_id: UUID): return self.db.get(SchedulingSession, session_id)
    def by_token(self, token: str): return self.db.exec(select(SchedulingSession).where(SchedulingSession.invitation_token == token)).first()
    def for_user(self, account_id: UUID):
        return list(self.db.exec(select(SchedulingSession).join(Participant, Participant.session_id == SchedulingSession.session_id).where(Participant.user_account_id == account_id).order_by(col(SchedulingSession.created_at).desc())).all())
    def save(self, item): self.db.add(item); self.db.flush(); return item


class ParticipantRepository:
    def __init__(self, db: Session): self.db = db
    def get(self, participant_id: UUID): return self.db.get(Participant, participant_id)
    def membership(self, session_id: UUID, account_id: UUID):
        return self.db.exec(select(Participant).where(Participant.session_id == session_id, Participant.user_account_id == account_id)).first()
    def for_session(self, session_id: UUID): return list(self.db.exec(select(Participant).where(Participant.session_id == session_id)).all())
    def save(self, item): self.db.add(item); self.db.flush(); return item


class AvailabilityRepository:
    def __init__(self, db: Session): self.db = db
    def current(self, participant_id: UUID):
        return self.db.exec(select(AvailabilityRecord).where(AvailabilityRecord.participant_id == participant_id, AvailabilityRecord.record_status == RecordStatus.ACTIVE).order_by(col(AvailabilityRecord.source_revision).desc())).first()
    def intervals(self, record_id: UUID):
        return list(self.db.exec(select(AvailabilityInterval).where(AvailabilityInterval.availability_record_id == record_id).order_by(AvailabilityInterval.start_date_time)).all())
    def active_for_session(self, session_id: UUID):
        return list(self.db.exec(select(AvailabilityRecord).join(Participant, Participant.participant_id == AvailabilityRecord.participant_id).where(Participant.session_id == session_id, AvailabilityRecord.record_status == RecordStatus.ACTIVE)).all())
    def save(self, item): self.db.add(item); self.db.flush(); return item
    def add_intervals(self, items): self.db.add_all(items); self.db.flush()


class VenueRepository:
    def __init__(self, db: Session): self.db = db
    def activities(self): return list(self.db.exec(select(ActivityType).where(ActivityType.is_active == True)).all())  # noqa: E712
    def has_verified_support(self, activity_type_id: UUID) -> bool:
        return self.db.exec(
            select(Venue.venue_id)
            .join(VenueActivity, VenueActivity.venue_id == Venue.venue_id)
            .where(
                VenueActivity.activity_type_id == activity_type_id,
                VenueActivity.support_status == "SUPPORTED",
                Venue.is_active == True,  # noqa: E712
                Venue.verification_status == VenueVerificationStatus.VERIFIED_PUBLIC,
            )
            .limit(1)
        ).first() is not None
    def supported_for_activity(self, activity_type_id: UUID, *, require_verified: bool = False):
        query = select(Venue).join(VenueActivity, VenueActivity.venue_id == Venue.venue_id).where(
            VenueActivity.activity_type_id == activity_type_id,
            VenueActivity.support_status == "SUPPORTED",
        )
        if require_verified:
            query = query.where(
                Venue.is_active == True,  # noqa: E712
                Venue.verification_status == VenueVerificationStatus.VERIFIED_PUBLIC,
            )
        return list(self.db.exec(query).all())


class RecommendationRepository:
    def __init__(self, db: Session): self.db = db
    def invalidate(self, session_id: UUID):
        for slot in self.db.exec(select(CandidateTimeslot).where(CandidateTimeslot.session_id == session_id)).all(): slot.generation_status = "INVALIDATED"
        for row in self.db.exec(select(VenueShortlistEntry).where(VenueShortlistEntry.session_id == session_id, VenueShortlistEntry.shortlist_status == ShortlistStatus.CURRENT)).all(): row.shortlist_status = ShortlistStatus.INVALIDATED
    def delete_revision(self, session_id: UUID, revision: int):
        combo_ids = list(self.db.exec(select(Combination.combination_id).where(Combination.session_id == session_id, Combination.source_revision == revision)).all())
        if combo_ids: self.db.exec(delete(TravelEstimate).where(col(TravelEstimate.combination_id).in_(combo_ids)))
        slot_ids = list(self.db.exec(select(CandidateTimeslot.timeslot_id).where(CandidateTimeslot.session_id == session_id, CandidateTimeslot.source_revision == revision)).all())
        if slot_ids: self.db.exec(delete(TimeslotAttendance).where(col(TimeslotAttendance.candidate_timeslot_id).in_(slot_ids)))
        self.db.exec(delete(Combination).where(Combination.session_id == session_id, Combination.source_revision == revision))
        self.db.exec(delete(VenueShortlistEntry).where(VenueShortlistEntry.session_id == session_id, VenueShortlistEntry.source_revision == revision))
        self.db.exec(delete(CandidateTimeslot).where(CandidateTimeslot.session_id == session_id, CandidateTimeslot.source_revision == revision))
    def delete_all(self, session_id: UUID):
        # Calendar audit rows may refer to a prior candidate/combination. Keep
        # the audit row but detach those nullable references before replacing
        # the current recommendation snapshot.
        for event in self.db.exec(select(CalendarEvent).where(CalendarEvent.session_id == session_id)).all():
            event.candidate_timeslot_id = None
            event.combination_id = None
            self.db.add(event)
        self.db.flush()

        combo_ids = list(self.db.exec(select(Combination.combination_id).where(Combination.session_id == session_id)).all())
        if combo_ids:
            self.db.exec(delete(TravelEstimate).where(col(TravelEstimate.combination_id).in_(combo_ids)))
        slot_ids = list(self.db.exec(select(CandidateTimeslot.timeslot_id).where(CandidateTimeslot.session_id == session_id)).all())
        if slot_ids:
            self.db.exec(delete(TimeslotAttendance).where(col(TimeslotAttendance.candidate_timeslot_id).in_(slot_ids)))
        self.db.exec(delete(Combination).where(Combination.session_id == session_id))
        self.db.exec(delete(VenueShortlistEntry).where(VenueShortlistEntry.session_id == session_id))
        self.db.exec(delete(CandidateTimeslot).where(CandidateTimeslot.session_id == session_id))
        self.db.flush()
    def add_all(self, items): self.db.add_all(items); self.db.flush()
    def ranked(self, session_id: UUID):
        return list(self.db.exec(select(Combination).where(Combination.session_id == session_id).order_by(col(Combination.source_revision).desc(), col(Combination.rank).asc())).all())


class TravelEstimateRepository:
    def __init__(self, db: Session): self.db = db
    def for_combination(self, combination_id: UUID): return list(self.db.exec(select(TravelEstimate).where(TravelEstimate.combination_id == combination_id)).all())
    def save_all(self, items): self.db.add_all(items); self.db.flush()


class CalendarRepository:
    def __init__(self, db: Session): self.db = db
    def connection(self, participant_id: UUID): return self.db.exec(select(CalendarConnection).where(CalendarConnection.participant_id == participant_id)).first()
    def save(self, item): self.db.add(item); self.db.flush(); return item
    def events(self, session_id: UUID): return list(self.db.exec(select(CalendarEvent).where(CalendarEvent.session_id == session_id)).all())
    def credential_for_user(self, account_id: UUID): return self.db.exec(select(CalendarCredential).where(CalendarCredential.user_account_id == account_id)).first()
    def credential(self, credential_id: UUID): return self.db.get(CalendarCredential, credential_id)

