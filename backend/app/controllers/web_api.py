"""Browser-facing API matching frontend/docs/api-contract.md."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.adapters.google_oauth import GoogleOAuthClient, GoogleOAuthError
from app.adapters.google_calendar_oauth import GoogleCalendarOAuthClient, GoogleCalendarOAuthError
from app.adapters.google_calendar_adapter import (
    CalendarAuthorizationExpired,
    CalendarProviderUnavailable,
    GoogleCalendarAdapter,
)
from app.adapters.mock import MockGeocoder
from app.adapters.onemap import OneMapAdapter as EngineOneMapAdapter
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    current_web_user,
    decode_app_token,
    decode_location_candidate,
    issue_location_candidate,
)
from app.models import (
    CalendarConnection,
    ConnectionStatus,
    Participant,
    SchedulingSession,
    SessionStatus,
    UserAccount,
)
from app.repositories import CalendarRepository, ParticipantRepository, SessionRepository, UserAccountRepository
from app.schemas import SessionCreate
from app.schemas.web import (
    ConfirmPlanRequest,
    DemoSignInRequest,
    InvitationTokenRequest,
    LocationSearchRequest,
    SaveResponseRequest,
    WebSessionCreate,
    WebSessionUpdate,
)
from app.services.application_services import SessionService, _bump_revision, _ensure_active, _get_session_or_404
from app.services.activity_availability import production_support_required, require_mutable_activity
from app.services.authentication_service import AuthenticationService
from app.services.authorization_service import require_member, require_organiser
from app.services.integrated_recommendation_service import IntegratedRecommendationService
from app.services.calendar_service import CalendarService
from app.services.calendar_credentials import CalendarCredentialError, CalendarCredentialVault
from app.services.calendar_sync_service import CalendarSyncService, CalendarSyncSummary
from app.services.web_contract_service import (
    activity_categories,
    confirm_plan,
    invitation_preview,
    my_response,
    recommendation_set,
    response_status,
    save_response,
    session_detail,
    session_list,
    session_zone,
    withdraw_response,
)

router = APIRouter(prefix="/api")

DEMO_PERSONAS = {
    "demo-organiser": ("organiser@example.test", "Demo Organiser", "Create and manage sessions"),
    "demo-amirah": ("amirah@example.test", "Amirah", "Join as a participant"),
    "demo-wei-jie": ("weijie@example.test", "Wei Jie", "Join as a participant"),
}


@router.get("/me", tags=["web-authentication"])
def web_me(user: UserAccount = Depends(current_web_user)):
    return {"id": user.account_id, "displayName": user.display_name, "email": user.email}


async def get_google_oauth_client() -> AsyncIterator[GoogleOAuthClient]:
    async with httpx.AsyncClient(timeout=10) as http_client:
        yield GoogleOAuthClient(
            client_id=settings.google_client_id or "",
            client_secret=settings.google_client_secret or "",
            redirect_uri=settings.google_redirect_uri,
            signing_secret=settings.app_session_secret,
            http_client=http_client,
            transaction_max_age_seconds=settings.google_oauth_transaction_max_age_seconds,
        )


async def get_google_calendar_oauth_client() -> AsyncIterator[GoogleCalendarOAuthClient]:
    async with httpx.AsyncClient(timeout=10) as http_client:
        yield GoogleCalendarOAuthClient(
            client_id=settings.google_client_id or "",
            client_secret=settings.google_client_secret or "",
            redirect_uri=settings.google_calendar_redirect_uri or "",
            signing_secret=settings.app_session_secret,
            http_client=http_client,
            transaction_max_age_seconds=settings.google_oauth_transaction_max_age_seconds,
        )


async def get_google_calendar_adapter(db: Session = Depends(get_db)) -> AsyncIterator[GoogleCalendarAdapter]:
    bind = db.get_bind()

    def resolve_refresh_token(reference: str) -> str:
        if not settings.google_calendar_credential_key:
            raise CalendarCredentialError("Google Calendar credential storage is unavailable")
        with Session(bind) as credential_db:
            return CalendarCredentialVault(
                credential_db,
                settings.google_calendar_credential_key,
            ).refresh_token(reference)

    def resolve_calendar_id(reference: str) -> str | None:
        credential_id = CalendarCredentialVault._credential_id(reference)
        with Session(bind) as credential_db:
            credential = CalendarRepository(credential_db).credential(credential_id)
            return credential.google_calendar_id if credential is not None else None

    def save_calendar_id(reference: str, calendar_id: str | None) -> None:
        credential_id = CalendarCredentialVault._credential_id(reference)
        with Session(bind) as credential_db:
            credential = CalendarRepository(credential_db).credential(credential_id)
            if credential is None:
                raise CalendarCredentialError("Calendar credential was not found")
            credential.google_calendar_id = calendar_id
            credential_db.add(credential)
            credential_db.commit()

    def mark_expired(reference: str) -> None:
        with Session(bind) as credential_db:
            CalendarService.mark_expired(credential_db, reference)

    async with httpx.AsyncClient(timeout=10) as http_client:
        yield GoogleCalendarAdapter(
            client_id=settings.google_client_id or "",
            client_secret=settings.google_client_secret or "",
            http_client=http_client,
            refresh_token_resolver=resolve_refresh_token,
            calendar_id_resolver=resolve_calendar_id,
            calendar_id_saver=save_calendar_id,
            mark_expired=mark_expired,
        )


@router.get("/auth/google/login", tags=["web-authentication"])
def google_login(
    next: str = Query(default="/signin"),
    db: Session = Depends(get_db),
    oauth_client: GoogleOAuthClient = Depends(get_google_oauth_client),
):
    safe_next = _safe_path(next, fallback="/signin")
    if settings.debug_auth_enabled:
        auth = AuthenticationService.development_login(db, *DEMO_PERSONAS["demo-organiser"][:2])
        response = RedirectResponse(_frontend_url(safe_next), status_code=302)
        _set_cookie(response, auth.access_token)
        return response
    if not settings.google_client_id or not settings.google_client_secret:
        return RedirectResponse(_frontend_url("/signin?error=unavailable"), status_code=302)
    start = oauth_client.begin(safe_next)
    response = RedirectResponse(start.authorization_url, status_code=302)
    response.set_cookie(
        settings.google_oauth_transaction_cookie_name,
        start.transaction_cookie,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.google_oauth_transaction_max_age_seconds,
        path="/",
    )
    return response


@router.get("/auth/google/callback", tags=["web-authentication"])
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    oauth_client: GoogleOAuthClient = Depends(get_google_oauth_client),
):
    transaction_cookie = request.cookies.get(settings.google_oauth_transaction_cookie_name)
    if error:
        response = RedirectResponse(_frontend_url("/signin?error=declined"), status_code=302)
    elif not code or not state or not transaction_cookie:
        response = RedirectResponse(_frontend_url("/signin?error=unavailable"), status_code=302)
    else:
        try:
            identity = await oauth_client.complete(code, state, transaction_cookie)
            auth = AuthenticationService.google_identity_login(db, identity)
        except (GoogleOAuthError, HTTPException):
            response = RedirectResponse(_frontend_url("/signin?error=unavailable"), status_code=302)
        else:
            response = RedirectResponse(_frontend_url(identity.next_path), status_code=302)
            _set_cookie(response, auth.access_token)
    _clear_google_transaction_cookie(response)
    return response


@router.post("/auth/logout", status_code=204, tags=["web-authentication"])
def logout(response: Response):
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/dev/users", tags=["development"])
def demo_users(request: Request, db: Session = Depends(get_db)):
    if not settings.debug_auth_enabled:
        raise HTTPException(404, "Development login is disabled")
    current_id = None
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        try:
            account = db.get(UserAccount, decode_app_token(token))
            if account is not None:
                current_id = next((key for key, persona in DEMO_PERSONAS.items() if persona[0] == account.email), None)
        except HTTPException:
            pass
    return {
        "currentUserId": current_id,
        "users": [
            {"id": key, "displayName": display_name, "summary": summary}
            for key, (_email, display_name, summary) in DEMO_PERSONAS.items()
        ],
    }


@router.post("/dev/sign-in", status_code=204, tags=["development"])
def demo_sign_in(payload: DemoSignInRequest, response: Response, db: Session = Depends(get_db)):
    if not settings.debug_auth_enabled:
        raise HTTPException(404, "Development login is disabled")
    persona = DEMO_PERSONAS.get(payload.user_id)
    if persona is None:
        raise HTTPException(404, "Unknown demo user")
    auth = AuthenticationService.development_login(db, persona[0], persona[1])
    _set_cookie(response, auth.access_token)


@router.get("/activity-types", tags=["web-sessions"])
def web_activities(db: Session = Depends(get_db), _: UserAccount = Depends(current_web_user)):
    return activity_categories(db)


@router.get("/sessions", tags=["web-sessions"])
def web_sessions(db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    return session_list(db, user)


@router.post("/sessions", status_code=201, tags=["web-sessions"])
def web_create_session(payload: WebSessionCreate, db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    zone = session_zone(payload.timezone)
    start = datetime.combine(payload.start_date, payload.daily_start_time).replace(tzinfo=zone)
    end = datetime.combine(payload.end_date, payload.daily_end_time).replace(tzinfo=zone)
    deadline = payload.response_deadline.replace(tzinfo=zone) if payload.response_deadline.tzinfo is None else payload.response_deadline.astimezone(zone)
    data = SessionCreate(
        name=payload.name,
        activity_type_id=payload.activity_type_id,
        date_range_start=start,
        date_range_end=end,
        timezone=payload.timezone,
        duration_minutes=payload.duration_minutes,
        response_deadline=deadline,
        minimum_attendee_threshold=payload.minimum_attendees,
    )
    item = SessionService.create(db, user, data)
    return {"session": session_detail(db, user, item), "invitationUrl": _frontend_url(f"/join/{item.invitation_token}")}


@router.get("/sessions/{session_id}", tags=["web-sessions"])
def web_session(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    return session_detail(db, user, SessionService.get(db, user, session_id))


@router.patch("/sessions/{session_id}", tags=["web-sessions"])
def web_update_session(payload: WebSessionUpdate, session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    require_organiser(db, session_id, user)
    item = _get_session_or_404(db, session_id, lock=True)
    _ensure_active(item)
    require_mutable_activity(db, item, require_verified=production_support_required())
    zone = session_zone(item.timezone)
    current_start = item.date_range_start.replace(tzinfo=zone) if item.date_range_start.tzinfo is None else item.date_range_start.astimezone(zone)
    current_end = item.date_range_end.replace(tzinfo=zone) if item.date_range_end.tzinfo is None else item.date_range_end.astimezone(zone)
    start = datetime.combine(payload.start_date or current_start.date(), payload.daily_start_time or current_start.timetz().replace(tzinfo=None)).replace(tzinfo=zone)
    end = datetime.combine(payload.end_date or current_end.date(), payload.daily_end_time or current_end.timetz().replace(tzinfo=None)).replace(tzinfo=zone)
    deadline = payload.response_deadline or item.response_deadline
    deadline = deadline.replace(tzinfo=zone) if deadline.tzinfo is None else deadline.astimezone(zone)
    if start >= end or deadline >= start:
        raise HTTPException(422, "Invalid date range or response deadline")
    item.date_range_start = start
    item.date_range_end = end
    item.response_deadline = deadline
    if payload.name is not None:
        item.name = payload.name
    if payload.duration_minutes is not None:
        item.duration_minutes = payload.duration_minutes
    if payload.minimum_attendees is not None:
        item.minimum_attendee_threshold = payload.minimum_attendees
    if payload.travel_objective is not None:
        item.travel_objective = payload.travel_objective
    if payload.attendance_weight_percent is not None:
        item.attendance_weight_percent = payload.attendance_weight_percent
        item.travel_weight_percent = 100 - payload.attendance_weight_percent
    _bump_revision(item)
    db.add(item)
    db.commit()
    db.refresh(item)
    return session_detail(db, user, item)


@router.post("/sessions/{session_id}/cancel", tags=["web-sessions"])
def web_cancel_session(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    item = SessionService.cancel(db, user, session_id)
    return session_detail(db, user, item)


@router.get("/sessions/{session_id}/invitation", tags=["web-sessions"])
def web_invitation_link(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    require_organiser(db, session_id, user)
    item = _get_session_or_404(db, session_id)
    return {"invitationUrl": _frontend_url(f"/join/{item.invitation_token}")}


@router.post("/invitations/resolve", tags=["web-invitations"])
def resolve_invitation(payload: InvitationTokenRequest, db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    return invitation_preview(db, user, payload.token)


@router.post("/invitations/join", tags=["web-invitations"])
def join_invitation(payload: InvitationTokenRequest, db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    participant = SessionService.join(db, user, payload.token)
    return {"sessionId": participant.session_id, "participantId": participant.participant_id}


@router.post("/locations/search", tags=["web-availability"])
async def search_locations(payload: LocationSearchRequest, _: UserAccount = Depends(current_web_user)):
    provider = None
    if settings.use_mock_providers:
        from app.mock_data.loader import load_places

        provider = MockGeocoder(load_places())
    else:
        base_url = settings.onemap_base_url.rstrip("/")
        if base_url.endswith("/api"):
            base_url = base_url[:-4]
        provider = EngineOneMapAdapter(
            email=settings.onemap_email,
            password=settings.onemap_password,
            token=settings.onemap_token,
            base_url=base_url,
        )
    try:
        result = await provider.geocode(payload.query)
    finally:
        close = getattr(provider, "aclose", None)
        if close:
            await close()
    input_type = "POSTAL_CODE" if payload.query.strip().isdigit() and len(payload.query.strip()) == 6 else "ADDRESS"
    status = "UNAVAILABLE" if result.status.value == "UNAVAILABLE" else "RECEIVED"
    candidates = [
        {
            "candidateId": issue_location_candidate(
                {
                    "label": match.label,
                    "postal_code": match.postal_code,
                    "latitude": match.coordinates.lat,
                    "longitude": match.coordinates.lng,
                    "input_type": input_type,
                }
            ),
            "label": match.label,
            "postalCode": match.postal_code,
        }
        for match in result.matches
    ]
    return {"status": status, "inputType": input_type, "candidates": candidates}


@router.get("/sessions/{session_id}/my-response", tags=["web-availability"])
def web_my_response(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    return my_response(db, user, session_id)


@router.put("/sessions/{session_id}/my-response", tags=["web-availability"])
def web_save_response(payload: SaveResponseRequest, session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    location = None
    if payload.location is not None:
        decoded = decode_location_candidate(payload.location.candidate_id)
        location = {
            "input_type": payload.location.input_type,
            "input": payload.location.input,
            "latitude": float(decoded["latitude"]),
            "longitude": float(decoded["longitude"]),
        }
    return save_response(db, user, session_id, payload, location)


@router.post("/sessions/{session_id}/my-response/withdraw", tags=["web-availability"])
def web_withdraw_response(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    return withdraw_response(db, user, session_id)


@router.get("/sessions/{session_id}/responses", tags=["web-availability"])
def web_response_status(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    return response_status(db, user, session_id)


@router.get("/sessions/{session_id}/recommendations", tags=["web-recommendations"])
def web_recommendations(session_id: UUID, db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    return recommendation_set(db, user, session_id)


@router.post("/sessions/{session_id}/recommendations", tags=["web-recommendations"])
async def web_generate_recommendations(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_web_user),
    calendar_adapter: GoogleCalendarAdapter = Depends(get_google_calendar_adapter),
):
    result = await IntegratedRecommendationService.generate(
        db,
        user,
        session_id,
        calendar_adapter if settings.google_calendar_enabled else None,
    )
    if result.status.value == "NO_TIMESLOT_MEETS_THRESHOLD":
        raise HTTPException(409, "No Timeslot meets the Minimum-Attendee Threshold")
    return recommendation_set(db, user, session_id)


@router.post("/sessions/{session_id}/confirm", tags=["web-recommendations"])
async def web_confirm_plan(
    payload: ConfirmPlanRequest,
    session_id: UUID,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_web_user),
    calendar_adapter: GoogleCalendarAdapter = Depends(get_google_calendar_adapter),
):
    result = confirm_plan(db, user, session_id, payload.combination_id)
    if settings.google_calendar_enabled:
        try:
            summary = await CalendarSyncService(calendar_adapter).sync_confirmed(db, user, session_id)
        except Exception:
            # The Session confirmation above is authoritative; Calendar is a
            # best-effort side effect and cannot replace the successful result.
            db.rollback()
            summary = CalendarSyncSummary(failed=1, can_retry=True)
    else:
        summary = CalendarSyncSummary()
    result["confirmed"]["calendarSync"] = summary.to_api()
    return result


@router.post("/sessions/{session_id}/calendar-sync", tags=["web-calendar"])
async def retry_calendar_sync(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_web_user),
    calendar_adapter: GoogleCalendarAdapter = Depends(get_google_calendar_adapter),
):
    require_organiser(db, session_id, user)
    item = _get_session_or_404(db, session_id)
    require_mutable_activity(db, item, require_verified=production_support_required())
    if not settings.google_calendar_enabled:
        return CalendarSyncSummary().to_api()
    return (
        await CalendarSyncService(calendar_adapter).sync_confirmed(db, user, session_id)
    ).to_api()


@router.get("/calendar/connection", tags=["web-calendar"])
def calendar_connection(db: Session = Depends(get_db), user: UserAccount = Depends(current_web_user)):
    return {"status": CalendarService.user_status(db, user).value}


@router.get("/calendar/google/connect", tags=["web-calendar"])
def connect_calendar(
    next: str = Query(default="/sessions"),
    user: UserAccount = Depends(current_web_user),
    oauth_client: GoogleCalendarOAuthClient = Depends(get_google_calendar_oauth_client),
):
    if not settings.google_calendar_enabled:
        return RedirectResponse(_calendar_result_url(next, "unavailable"), status_code=302)
    start = oauth_client.begin(user.account_id, user.provider_user_id, next)
    response = RedirectResponse(start.authorization_url, status_code=302)
    response.set_cookie(
        settings.google_calendar_oauth_transaction_cookie_name,
        start.transaction_cookie,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.google_oauth_transaction_max_age_seconds,
        path="/",
    )
    return response


@router.get("/calendar/google/callback", tags=["web-calendar"])
async def calendar_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_web_user),
    oauth_client: GoogleCalendarOAuthClient = Depends(get_google_calendar_oauth_client),
    calendar_adapter: GoogleCalendarAdapter = Depends(get_google_calendar_adapter),
):
    transaction_cookie = request.cookies.get(settings.google_calendar_oauth_transaction_cookie_name)
    next_path = "/profile"
    if transaction_cookie and hasattr(oauth_client, "transaction_path"):
        try:
            next_path = oauth_client.transaction_path(transaction_cookie)
        except GoogleCalendarOAuthError:
            pass
    if not settings.google_calendar_enabled:
        response = RedirectResponse(_calendar_result_url(next_path, "unavailable"), status_code=302)
    elif error == "access_denied":
        try:
            if not state or not transaction_cookie:
                raise GoogleCalendarOAuthError("Calendar OAuth transaction is missing")
            next_path = oauth_client.decline(state, transaction_cookie)
        except GoogleCalendarOAuthError:
            response = RedirectResponse(_calendar_result_url(next_path, "unavailable"), status_code=302)
        else:
            response = RedirectResponse(_calendar_result_url(next_path, "declined"), status_code=302)
    elif not code or not state or not transaction_cookie:
        response = RedirectResponse(_calendar_result_url(next_path, "unavailable"), status_code=302)
    else:
        connected_reference = None
        try:
            grant = await oauth_client.complete(code, state, transaction_cookie)
            if grant.account_id != user.account_id:
                raise GoogleCalendarOAuthError("Calendar OAuth transaction belongs to another account")
            connected_reference = CalendarService.connect_user(
                db,
                user,
                subject=grant.subject,
                refresh_token=grant.refresh_token,
                granted_scopes=list(grant.granted_scopes),
            )
            await calendar_adapter.ensure_app_calendar(connected_reference, "Asia/Singapore")
        except GoogleCalendarOAuthError as exc:
            marker = "wrong-account" if "same Google account" in str(exc) else "missing-scopes" if "scope" in str(exc).lower() else "unavailable"
            response = RedirectResponse(_calendar_result_url(next_path, marker), status_code=302)
        except (CalendarCredentialError, CalendarAuthorizationExpired, CalendarProviderUnavailable, HTTPException):
            if connected_reference is not None:
                await CalendarService.disconnect_user(db, user, calendar_adapter)
            response = RedirectResponse(_calendar_result_url(next_path, "unavailable"), status_code=302)
        else:
            response = RedirectResponse(_calendar_result_url(grant.next_path, "connected"), status_code=302)
    _clear_google_calendar_transaction_cookie(response)
    return response


@router.delete("/calendar/connection", status_code=204, tags=["web-calendar"])
async def disconnect_calendar(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_web_user),
    adapter: GoogleCalendarAdapter = Depends(get_google_calendar_adapter),
):
    await CalendarService.disconnect_user(
        db,
        user,
        adapter if settings.google_calendar_enabled else None,
    )


@router.post("/sessions/{session_id}/calendar-busy", tags=["web-calendar"])
async def calendar_busy(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_web_user),
    adapter: GoogleCalendarAdapter = Depends(get_google_calendar_adapter),
):
    require_member(db, session_id, user)
    item = _get_session_or_404(db, session_id)
    require_mutable_activity(db, item, require_verified=production_support_required())
    if not settings.google_calendar_enabled:
        return {"status": "UNAVAILABLE", "busy": []}
    if settings.use_mock_providers:
        return {"status": "RECEIVED", "busy": []}
    busy = await CalendarService.import_busy(db, user, session_id, adapter)
    if busy is None:
        return {"status": "UNAVAILABLE", "busy": []}
    return {
        "status": "RECEIVED",
        "busy": [
            {"start": _calendar_iso(row.start), "end": _calendar_iso(row.end)}
            for row in busy
        ],
    }


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 12,
        path="/",
    )


def _clear_google_transaction_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.google_oauth_transaction_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _clear_google_calendar_transaction_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.google_calendar_oauth_transaction_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _safe_path(value: str, fallback: str = "/sessions") -> str:
    if not value.startswith("/") or value.startswith("//") or "\n" in value or "\r" in value:
        return fallback
    return value


def _frontend_url(path: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}{_safe_path(path)}"


def _calendar_result_url(path: str, result: str) -> str:
    safe_path = _safe_path(path)
    separator = "&" if "?" in safe_path else "?"
    return _frontend_url(f"{safe_path}{separator}calendar={result}")


def _calendar_iso(value: datetime) -> str:
    rendered = value.isoformat()
    return rendered[:-6] + "Z" if rendered.endswith("+00:00") else rendered

