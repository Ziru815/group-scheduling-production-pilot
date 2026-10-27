"""Application authentication boundary.

Production accepts only a server-issued app session token. For a classroom/local demo,
DEBUG_AUTH_ENABLED=true permits a UUID account id as the bearer token. It is off by
default and must never be enabled in deployment.
"""
from uuid import UUID
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import UserAccount

bearer = HTTPBearer(auto_error=False)
serializer = URLSafeTimedSerializer(settings.app_session_secret, salt="group-scheduling-session")
location_serializer = URLSafeTimedSerializer(settings.app_session_secret, salt="group-scheduling-location")


def issue_app_token(account_id: UUID) -> str:
    return serializer.dumps({"account_id": str(account_id)})


def decode_app_token(token: str) -> UUID:
    if settings.debug_auth_enabled:
        try:
            return UUID(token)
        except ValueError:
            pass
    try:
        payload = serializer.loads(token, max_age=60 * 60 * 12)
        return UUID(payload["account_id"])
    except (BadSignature, SignatureExpired, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session") from exc


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> UserAccount:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    account = db.get(UserAccount, decode_app_token(credentials.credentials))
    if account is None or account.account_status != "ACTIVE":
        raise HTTPException(status_code=401, detail="Unknown or inactive account")
    return account


def current_web_user(
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> UserAccount:
    """Authenticate the browser contract with an httpOnly cookie.

    Bearer tokens are also accepted so API clients can use the same /api routes
    during migration from the legacy /api/v1 surface.
    """
    token = session_cookie or (credentials.credentials if credentials else None)
    if token is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    account = db.get(UserAccount, decode_app_token(token))
    if account is None or account.account_status != "ACTIVE":
        raise HTTPException(status_code=401, detail="Unknown or inactive account")
    return account


def issue_location_candidate(payload: dict) -> str:
    return location_serializer.dumps(payload)


def decode_location_candidate(token: str) -> dict:
    try:
        return location_serializer.loads(token, max_age=60 * 30)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(status_code=422, detail="Location selection expired; search again") from exc

