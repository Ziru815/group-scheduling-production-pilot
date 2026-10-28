"""Separate, browser-bound OAuth flow for optional Google Calendar access."""

from __future__ import annotations

import hmac
import re
import secrets
import time
from base64 import urlsafe_b64encode
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from urllib.parse import urlencode, urlsplit
from uuid import UUID

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.adapters.google_oauth import (
    GOOGLE_AUTHORIZATION_ENDPOINT,
    GOOGLE_ISSUERS,
    GOOGLE_TOKEN_ENDPOINT,
    IdentityTokenVerifier,
    _verify_google_id_token,
)


TRANSACTION_COOKIE_SALT = "google-calendar-oauth-transaction"
CALENDAR_FREEBUSY_SCOPE = "https://www.googleapis.com/auth/calendar.freebusy"
CALENDAR_APP_CREATED_SCOPE = "https://www.googleapis.com/auth/calendar.app.created"
REQUIRED_SCOPES = frozenset({"openid", "email", CALENDAR_FREEBUSY_SCOPE, CALENDAR_APP_CREATED_SCOPE})
SESSION_PATH = re.compile(r"^/sessions(?:/[0-9a-fA-F-]{36}(?:/[A-Za-z0-9_-]+)?)?(?:\?[^\r\n]*)?$")
_CONSUMED_STATES: dict[str, float] = {}


class GoogleCalendarOAuthError(Exception):
    """A user-safe Calendar authorization failure."""


@dataclass(frozen=True)
class GoogleCalendarOAuthStart:
    authorization_url: str
    transaction_cookie: str


@dataclass(frozen=True)
class GoogleCalendarGrant:
    account_id: UUID
    subject: str
    refresh_token: str | None
    granted_scopes: tuple[str, ...]
    next_path: str


class GoogleCalendarOAuthClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        signing_secret: str,
        http_client: httpx.AsyncClient,
        id_token_verifier: IdentityTokenVerifier | None = None,
        transaction_max_age_seconds: int = 600,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.http_client = http_client
        self.id_token_verifier = id_token_verifier or _verify_google_id_token
        self.transaction_max_age_seconds = transaction_max_age_seconds
        self.serializer = URLSafeTimedSerializer(signing_secret, salt=TRANSACTION_COOKIE_SALT)

    def begin(self, account_id: UUID, provider_subject: str, next_path: str) -> GoogleCalendarOAuthStart:
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        transaction_cookie = self.serializer.dumps(
            {
                "state": state,
                "nonce": nonce,
                "verifier": verifier,
                "account_id": str(account_id),
                "provider_subject": provider_subject,
                "next_path": _safe_calendar_path(next_path),
            }
        )
        challenge = urlsafe_b64encode(sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(sorted(REQUIRED_SCOPES)),
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
            }
        )
        return GoogleCalendarOAuthStart(
            authorization_url=f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{query}",
            transaction_cookie=transaction_cookie,
        )

    async def complete(self, code: str, returned_state: str, transaction_cookie: str) -> GoogleCalendarGrant:
        transaction = self._load_transaction(transaction_cookie)
        expected_state = str(transaction.get("state", ""))
        if not hmac.compare_digest(expected_state, returned_state):
            raise GoogleCalendarOAuthError("Calendar OAuth transaction did not match this browser")
        self._consume_state(expected_state)

        verifier = transaction.get("verifier")
        expected_nonce = transaction.get("nonce")
        expected_subject = transaction.get("provider_subject")
        try:
            account_id = UUID(str(transaction.get("account_id", "")))
        except ValueError as exc:
            raise GoogleCalendarOAuthError("Calendar OAuth transaction is invalid") from exc
        if not all(isinstance(value, str) and value for value in (verifier, expected_nonce, expected_subject)):
            raise GoogleCalendarOAuthError("Calendar OAuth transaction is invalid")

        try:
            response = await self.http_client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                },
            )
            response.raise_for_status()
            payload = response.json()
            id_token_value = payload["id_token"]
            claims = self.id_token_verifier(id_token_value, self.client_id)
        except Exception as exc:
            raise GoogleCalendarOAuthError("Google Calendar authorization could not be verified") from exc

        self._validate_identity(claims, expected_nonce)
        if not hmac.compare_digest(str(claims["sub"]), expected_subject):
            raise GoogleCalendarOAuthError("Choose the same Google account used to sign in")
        granted_scopes = frozenset(str(payload.get("scope", "")).split())
        if not REQUIRED_SCOPES.issubset(granted_scopes):
            raise GoogleCalendarOAuthError("Required Google Calendar scope was not granted")

        refresh_token = payload.get("refresh_token")
        if refresh_token is not None and not isinstance(refresh_token, str):
            raise GoogleCalendarOAuthError("Google Calendar authorization response is invalid")
        return GoogleCalendarGrant(
            account_id=account_id,
            subject=expected_subject,
            refresh_token=refresh_token,
            granted_scopes=tuple(sorted(granted_scopes)),
            next_path=_safe_calendar_path(str(transaction.get("next_path", "/sessions"))),
        )

    async def aclose(self) -> None:
        await self.http_client.aclose()

    def transaction_path(self, transaction_cookie: str) -> str:
        return _safe_calendar_path(str(self._load_transaction(transaction_cookie).get("next_path", "/sessions")))

    def decline(self, returned_state: str, transaction_cookie: str) -> str:
        transaction = self._load_transaction(transaction_cookie)
        expected_state = str(transaction.get("state", ""))
        if not hmac.compare_digest(expected_state, returned_state):
            raise GoogleCalendarOAuthError("Calendar OAuth transaction did not match this browser")
        self._consume_state(expected_state)
        return _safe_calendar_path(str(transaction.get("next_path", "/sessions")))

    def _consume_state(self, state: str) -> None:
        now = time.monotonic()
        cutoff = now - self.transaction_max_age_seconds
        for consumed_state, consumed_at in list(_CONSUMED_STATES.items()):
            if consumed_at < cutoff:
                del _CONSUMED_STATES[consumed_state]
        if state in _CONSUMED_STATES:
            raise GoogleCalendarOAuthError("Calendar OAuth transaction was already used")
        _CONSUMED_STATES[state] = now

    def _load_transaction(self, transaction_cookie: str) -> Mapping[str, Any]:
        try:
            transaction = self.serializer.loads(transaction_cookie, max_age=self.transaction_max_age_seconds)
        except SignatureExpired as exc:
            raise GoogleCalendarOAuthError("Calendar OAuth transaction expired") from exc
        except (BadSignature, TypeError) as exc:
            raise GoogleCalendarOAuthError("Calendar OAuth transaction is invalid") from exc
        if not isinstance(transaction, Mapping):
            raise GoogleCalendarOAuthError("Calendar OAuth transaction is invalid")
        return transaction

    def _validate_identity(self, claims: Mapping[str, Any], expected_nonce: str) -> None:
        audience = claims.get("aud")
        audience_matches = audience == self.client_id or (
            isinstance(audience, list) and self.client_id in audience
        )
        if (
            claims.get("iss") not in GOOGLE_ISSUERS
            or not audience_matches
            or not hmac.compare_digest(str(claims.get("nonce", "")), expected_nonce)
            or not isinstance(claims.get("sub"), str)
            or not claims["sub"]
            or claims.get("email_verified") is not True
        ):
            raise GoogleCalendarOAuthError("Google Calendar identity claims are invalid")


def _safe_calendar_path(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or not value.startswith("/") or value.startswith(("//", "/\\")):
        return "/sessions"
    if value == "/profile" or SESSION_PATH.fullmatch(value):
        return value
    return "/sessions"
