from datetime import datetime, timezone
from fastapi import HTTPException
from sqlmodel import Session

from app.core.config import settings
from app.core.security import issue_app_token
from app.models import UserAccount
from app.repositories import UserAccountRepository
from app.schemas import AuthResponse


class AuthenticationService:
    @staticmethod
    def google_login(db: Session, id_token_value: str) -> AuthResponse:
        if not settings.google_client_id:
            raise HTTPException(503, "Google login is not configured")
        try:
            from google.auth.transport import requests
            from google.oauth2 import id_token
            claims = id_token.verify_oauth2_token(id_token_value, requests.Request(), settings.google_client_id)
        except Exception as exc:
            raise HTTPException(401, "Google identity token verification failed") from exc
        if not claims.get("sub") or not claims.get("email"):
            raise HTTPException(401, "Google token lacks required identity claims")
        repo = UserAccountRepository(db); account = repo.by_provider("GOOGLE", claims["sub"])
        if account is None:
            account = UserAccount(email=claims["email"].lower(), display_name=claims.get("name") or claims["email"], provider_user_id=claims["sub"])
        account.last_login_at = datetime.now(timezone.utc); repo.save(account); db.commit(); db.refresh(account)
        return AuthResponse(access_token=issue_app_token(account.account_id), account_id=account.account_id, display_name=account.display_name)

    @staticmethod
    def development_login(db: Session, email: str, display_name: str) -> AuthResponse:
        if not settings.debug_auth_enabled: raise HTTPException(404, "Development login is disabled")
        repo = UserAccountRepository(db); account = repo.by_email(email.lower())
        if account is None: account = UserAccount(email=email.lower(), display_name=display_name, auth_provider="DEV", provider_user_id=email.lower())
        repo.save(account); db.commit(); db.refresh(account)
        return AuthResponse(access_token=issue_app_token(account.account_id), account_id=account.account_id, display_name=account.display_name)

