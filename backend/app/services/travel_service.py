from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from app.adapters.ports import GeoPoint, GeocoderPort, RoutingPort
from app.core.config import settings
from app.models import (
    AttendanceStatus, AvailabilityRecord, CandidateTimeslot, Combination,
    GeocodeStatus, RoutingStatus, TimeslotAttendance, TravelEstimate, UserAccount,
    Venue,
)
from app.services.authorization_service import require_organiser


class TravelService:
    def __init__(self, geocoder: GeocoderPort, router: RoutingPort): self.geocoder, self.router = geocoder, router

    async def geocode_own_record(self, db: Session, user: UserAccount, session_id: UUID, record: AvailabilityRecord):
        point = await self.geocoder.geocode(record.location_input)
        if point is None: record.geocode_status = GeocodeStatus.INVALID; record.latitude = None; record.longitude = None
        else: record.geocode_status = GeocodeStatus.VALID; record.latitude = point.latitude; record.longitude = point.longitude
        db.add(record); db.commit(); return record

    async def calculate_for_combination(self, db: Session, user: UserAccount, session_id: UUID, combination_id: UUID):
        require_organiser(db, session_id, user); combo = db.get(Combination, combination_id)
        if combo is None or combo.session_id != session_id: raise HTTPException(404, "Combination not found")
        venue, slot = db.get(Venue, combo.venue_id), db.get(CandidateTimeslot, combo.candidate_timeslot_id)
        available_ids = list(db.exec(select(TimeslotAttendance.participant_id).where(TimeslotAttendance.candidate_timeslot_id == slot.timeslot_id, TimeslotAttendance.attendance_status == AttendanceStatus.AVAILABLE)).all())
        records = list(db.exec(select(AvailabilityRecord).where(AvailabilityRecord.participant_id.in_(available_ids), AvailabilityRecord.geocode_status == GeocodeStatus.VALID)).all())
        if len(records) != len(available_ids): return {"stored": 0, "unavailable": len(available_ids), "message": "Some available participants lack valid geocoding"}
        existing = list(db.exec(select(TravelEstimate).where(TravelEstimate.combination_id == combination_id, TravelEstimate.source_revision == combo.source_revision)).all())
        for row in existing: db.delete(row)
        stored, unavailable = 0, 0
        for record in records:
            outcome = await self.router.route(GeoPoint(record.latitude, record.longitude), GeoPoint(venue.latitude, venue.longitude), record.transport_mode, slot.start_date_time)
            status = RoutingStatus.AVAILABLE if outcome.duration_minutes is not None else RoutingStatus.ERROR
            estimate = TravelEstimate(combination_id=combo.combination_id, participant_id=record.participant_id, transport_mode=record.transport_mode, travel_duration_minutes=outcome.duration_minutes, routing_status=status, journey_limit_exceeded=(outcome.duration_minutes > settings.default_journey_cap_minutes) if outcome.duration_minutes is not None else None, provider=outcome.provider, request_time=datetime.now(timezone.utc), source_revision=combo.source_revision)
            db.add(estimate); stored += status == RoutingStatus.AVAILABLE; unavailable += status != RoutingStatus.AVAILABLE
        db.commit(); return {"stored": stored, "unavailable": unavailable}

