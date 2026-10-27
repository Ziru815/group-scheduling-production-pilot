from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.adapters.one_map_adapter import OneMapAdapter
from app.core.database import get_db
from app.core.security import current_user
from app.models import ActivityType, AvailabilityRecord, Combination, Participant, SchedulingSession, UserAccount
from app.schemas import (
    AuthResponse, AvailabilityOwn, AvailabilitySubmit, ConfirmRequest, DevLoginRequest,
    GenerateResult, GoogleLoginRequest, JoinRequest, Message, ParticipantPublic,
    RankedCombination, RecommendationSettings, SessionCreate, SessionManagement,
    SessionPublic, SessionUpdate,
)
from app.services.application_services import AvailabilityService, RecommendationService, SessionService, _bump_revision, _get_session_or_404
from app.services.authentication_service import AuthenticationService
from app.services.authorization_service import require_member, require_organiser
from app.services.travel_service import TravelService

router = APIRouter()


@router.post("/auth/google", response_model=AuthResponse, tags=["authentication"])
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)): return AuthenticationService.google_login(db, payload.id_token)


@router.post("/auth/dev", response_model=AuthResponse, tags=["authentication"])
def dev_login(payload: DevLoginRequest, db: Session = Depends(get_db)): return AuthenticationService.development_login(db, payload.email, payload.display_name)


@router.get("/auth/me", tags=["authentication"])
def me(user: UserAccount = Depends(current_user)): return {"account_id": user.account_id, "display_name": user.display_name, "email": user.email}


@router.get("/activities", response_model=list[ActivityType], tags=["sessions"])
def activities(db: Session = Depends(get_db), _: UserAccount = Depends(current_user)): return list(db.exec(select(ActivityType).where(ActivityType.is_active == True)).all())  # noqa: E712


@router.post("/sessions", response_model=SessionManagement, status_code=201, tags=["sessions"])
def create_session(payload: SessionCreate, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)): return SessionService.create(db, user, payload)


@router.get("/sessions", response_model=list[SessionPublic], tags=["sessions"])
def list_sessions(db: Session = Depends(get_db), user: UserAccount = Depends(current_user)): return SessionService.list_for_user(db, user)


@router.get("/sessions/{session_id}", response_model=SessionPublic, tags=["sessions"])
def get_session(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)): return SessionService.get(db, user, session_id)


@router.patch("/sessions/{session_id}", response_model=SessionManagement, tags=["sessions"])
def update_session(session_id: UUID, payload: SessionUpdate, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)): return SessionService.update(db, user, session_id, payload)


@router.post("/sessions/{session_id}/cancel", response_model=Message, tags=["sessions"])
def cancel_session(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    SessionService.cancel(db, user, session_id); return Message(message="Session cancelled")


@router.post("/participants/join", response_model=ParticipantPublic, tags=["participants"])
def join_session(payload: JoinRequest, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)): return SessionService.join(db, user, payload.invitation_token)


@router.get("/sessions/{session_id}/participants/status", response_model=list[ParticipantPublic], tags=["participants"])
def response_statuses(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    require_organiser(db, session_id, user); return list(db.exec(select(Participant).where(Participant.session_id == session_id)).all())


@router.put("/sessions/{session_id}/availability/me", response_model=AvailabilityOwn, tags=["availability"])
def submit_availability(session_id: UUID, payload: AvailabilitySubmit, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)): return AvailabilityService.submit(db, user, session_id, payload)


@router.get("/sessions/{session_id}/availability/me", response_model=AvailabilityOwn, tags=["availability"])
def own_availability(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)): return AvailabilityService.get_own(db, user, session_id)


@router.delete("/sessions/{session_id}/availability/me", status_code=204, tags=["availability"])
def withdraw_availability(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    AvailabilityService.withdraw(db, user, session_id); return Response(status_code=204)


@router.post("/sessions/{session_id}/availability/me/geocode", tags=["travel"])
async def geocode_own_location(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    member = require_member(db, session_id, user)
    record = db.exec(select(AvailabilityRecord).where(AvailabilityRecord.participant_id == member.participant_id, AvailabilityRecord.record_status == "ACTIVE")).first()
    if record is None: raise HTTPException(404, "No active response")
    updated = await TravelService(OneMapAdapter(), OneMapAdapter()).geocode_own_record(db, user, session_id, record)
    return {"geocode_status": updated.geocode_status}


@router.put("/sessions/{session_id}/recommendation-settings", response_model=SessionPublic, tags=["recommendations"])
def recommendation_settings(session_id: UUID, payload: RecommendationSettings, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    require_organiser(db, session_id, user); item = _get_session_or_404(db, session_id, lock=True)
    item.travel_objective = payload.travel_objective; item.attendance_weight_percent = payload.attendance_weight_percent; item.travel_weight_percent = payload.travel_weight_percent; _bump_revision(item)
    db.add(item); db.commit(); db.refresh(item); return item


@router.post("/sessions/{session_id}/recommendations/generate", response_model=GenerateResult, tags=["recommendations"])
def generate(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)): return RecommendationService.generate(db, user, session_id)


@router.post("/sessions/{session_id}/recommendations/{combination_id}/route", tags=["travel"])
async def calculate_routes(session_id: UUID, combination_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    return await TravelService(OneMapAdapter(), OneMapAdapter()).calculate_for_combination(db, user, session_id, combination_id)


@router.post("/sessions/{session_id}/recommendations/rescore", tags=["recommendations"])
def rescore(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)): return {"ranked": RecommendationService.rescore(db, user, session_id)}


@router.get("/sessions/{session_id}/recommendations", response_model=list[RankedCombination], tags=["recommendations"])
def ranked(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)): return RecommendationService.list_ranked(db, user, session_id)


@router.post("/sessions/{session_id}/final-plan/{combination_id}", tags=["final plan"])
def confirm(session_id: UUID, combination_id: UUID, payload: ConfirmRequest, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    combination = RecommendationService.confirm(db, user, session_id, combination_id, payload.expected_source_revision)
    return {"combination_id": combination.combination_id, "status": combination.status, "calendar_sync": "PENDING_OR_NOT_CONNECTED"}


@router.get("/sessions/{session_id}/final-plan", tags=["final plan"])
def final_plan(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    require_member(db, session_id, user); item = _get_session_or_404(db, session_id)
    if item.confirmed_combination_id is None: raise HTTPException(404, "No final plan confirmed")
    choices = RecommendationService.list_ranked(db, user, session_id)
    return next((value for value in choices if value.combination_id == item.confirmed_combination_id), None)


@router.get("/sessions/{session_id}/calendar/status", tags=["calendar"])
def calendar_status(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    member = require_member(db, session_id, user)
    return {"participant_id": member.participant_id, "configured": False, "reason": "OAuth scopes and credential vault require team approval"}

