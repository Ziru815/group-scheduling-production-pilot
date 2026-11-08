from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.adapters.google_oauth import GoogleIdentity
from app.core.config import settings
from app.core.security import issue_app_token
from app.models import UserAccount
from app.repositories import UserAccountRepository
from app.schemas import AuthResponse


class AuthenticationService:
    @staticmethod
    def google_identity_login(db: Session, identity: GoogleIdentity) -> AuthResponse:
        repo = UserAccountRepository(db)
        account = repo.by_provider("GOOGLE", identity.subject)
        if account is None:
            if repo.by_email(identity.email) is not None:
                raise HTTPException(409, "Google sign-in could not be completed")
            account = UserAccount(
                email=identity.email,
                display_name=identity.display_name,
                auth_provider="GOOGLE",
                provider_user_id=identity.subject,
            )
        else:
            email_owner = repo.by_email(identity.email)
            if email_owner is not None and email_owner.account_id != account.account_id:
                raise HTTPException(409, "Google sign-in could not be completed")
            account.email = identity.email
            account.display_name = identity.display_name
        if account.account_status != "ACTIVE":
            raise HTTPException(403, "Google sign-in could not be completed")
        account.last_login_at = datetime.now(timezone.utc)
        try:
            repo.save(account)
            db.commit()
            db.refresh(account)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "Google sign-in could not be completed") from exc
        return AuthResponse(
            access_token=issue_app_token(account.account_id),
            account_id=account.account_id,
            display_name=account.display_name,
        )

    @staticmethod
    def development_login(db: Session, email: str, display_name: str) -> AuthResponse:
        if not settings.debug_auth_enabled: raise HTTPException(404, "Development login is disabled")
        repo = UserAccountRepository(db); account = repo.by_email(email.lower())
        if account is None: account = UserAccount(email=email.lower(), display_name=display_name, auth_provider="DEV", provider_user_id=email.lower())
        repo.save(account); db.commit(); db.refresh(account)
        return AuthResponse(access_token=issue_app_token(account.account_id), account_id=account.account_id, display_name=account.display_name)

