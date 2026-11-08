"""Encrypted persistence for Google Calendar refresh credentials."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlmodel import Session

from app.models import CalendarCredential, ConnectionStatus
from app.repositories import CalendarRepository


class CalendarCredentialError(Exception):
    """A credential lookup or decryption failed without exposing secret data."""


class CalendarCredentialVault:
    def __init__(self, db: Session, encryption_key: str) -> None:
        self.db = db
        try:
            self.cipher = Fernet(encryption_key.encode())
        except (TypeError, ValueError) as exc:
            raise CalendarCredentialError("Google Calendar credential key is invalid") from exc

    @staticmethod
    def reference(credential_id: UUID) -> str:
        return f"db:{credential_id}"

    def store(
        self,
        user_account_id: UUID,
        refresh_token: str | None,
        granted_scopes: list[str],
        google_calendar_id: str | None = None,
    ) -> CalendarCredential:
        repo = CalendarRepository(self.db)
        credential = repo.credential_for_user(user_account_id)
        now = datetime.now(timezone.utc)
        if credential is None:
            credential = CalendarCredential(user_account_id=user_account_id)
        if refresh_token is not None:
            credential.encrypted_refresh_token = self.cipher.encrypt(refresh_token.encode()).decode()
        elif not credential.encrypted_refresh_token:
            raise CalendarCredentialError("Google did not return a refresh token; reconnect with consent")
        if google_calendar_id is not None:
            credential.google_calendar_id = google_calendar_id
        credential.granted_scopes = " ".join(sorted(set(granted_scopes)))
        credential.status = ConnectionStatus.CONNECTED
        credential.updated_at = now
        credential.revoked_at = None
        repo.save(credential)
        return credential

    def refresh_token(self, credential_reference: str) -> str:
        credential_id = self._credential_id(credential_reference)
        credential = CalendarRepository(self.db).credential(credential_id)
        if credential is None:
            raise CalendarCredentialError("Calendar credential was not found")
        if not credential.encrypted_refresh_token:
            raise CalendarCredentialError("Calendar credential is disconnected")
        try:
            return self.cipher.decrypt(credential.encrypted_refresh_token.encode()).decode()
        except (InvalidToken, ValueError) as exc:
            raise CalendarCredentialError("Calendar credential could not be decrypted") from exc

    def disconnect(self, user_account_id: UUID) -> None:
        self.disconnect_record(self.db, user_account_id)

    @staticmethod
    def disconnect_record(db: Session, user_account_id: UUID) -> None:
        """Clear a stored credential without requiring the encryption key."""
        credential = CalendarRepository(db).credential_for_user(user_account_id)
        if credential is None:
            return
        now = datetime.now(timezone.utc)
        credential.encrypted_refresh_token = None
        credential.granted_scopes = ""
        credential.status = ConnectionStatus.DISCONNECTED
        credential.updated_at = now
        credential.revoked_at = now
        db.add(credential)

    @staticmethod
    def _credential_id(credential_reference: str) -> UUID:
        prefix, separator, value = credential_reference.partition(":")
        if prefix != "db" or separator != ":":
            raise CalendarCredentialError("Calendar credential reference is invalid")
        try:
            return UUID(value)
        except ValueError as exc:
            raise CalendarCredentialError("Calendar credential reference is invalid") from exc
