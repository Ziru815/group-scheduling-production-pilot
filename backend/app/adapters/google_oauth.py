"""Google OpenID Connect authorization-code flow with browser-bound transactions."""

from __future__ import annotations

import hmac
import secrets
from base64 import urlsafe_b64encode
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
TRANSACTION_COOKIE_SALT = "google-oauth-transaction"

IdentityTokenVerifier = Callable[[str, str], Mapping[str, Any]]


class GoogleOAuthError(Exception):
    """A user-safe OAuth failure whose details must not expose provider data."""


@dataclass(frozen=True)
class GoogleOAuthStart:
    authorization_url: str
    transaction_cookie: str


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    display_name: str
    next_path: str


class GoogleOAuthClient:
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
        self.serializer = URLSafeTimedSerializer(
            signing_secret,
            salt=TRANSACTION_COOKIE_SALT,
        )

    def begin(self, next_path: str) -> GoogleOAuthStart:
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        safe_next_path = _safe_relative_path(next_path)
        transaction_cookie = self.serializer.dumps(
            {
                "state": state,
                "nonce": nonce,
                "verifier": verifier,
                "next_path": safe_next_path,
            }
        )
        challenge = urlsafe_b64encode(sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "access_type": "online",
                "prompt": "select_account",
            }
        )
        return GoogleOAuthStart(
            authorization_url=f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{query}",
            transaction_cookie=transaction_cookie,
        )

    async def complete(
        self,
        code: str,
        returned_state: str,
        transaction_cookie: str,
    ) -> GoogleIdentity:
        transaction = self._load_transaction(transaction_cookie)
        if not hmac.compare_digest(str(transaction.get("state", "")), returned_state):
            raise GoogleOAuthError("OAuth transaction did not match this browser")

        verifier = transaction.get("verifier")
        expected_nonce = transaction.get("nonce")
        if not isinstance(verifier, str) or not isinstance(expected_nonce, str):
            raise GoogleOAuthError("OAuth transaction is invalid")

        try:
            token_response = await self.http_client.post(
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
            token_response.raise_for_status()
            id_token_value = token_response.json()["id_token"]
            if not isinstance(id_token_value, str) or not id_token_value:
                raise ValueError("missing ID token")
            claims = self.id_token_verifier(id_token_value, self.client_id)
        except Exception as exc:
            raise GoogleOAuthError("Google identity could not be verified") from exc

        self._validate_identity_claims(claims, expected_nonce)
        subject = claims["sub"]
        email = claims["email"].strip().lower()
        display_name = str(claims.get("name") or email).strip()
        next_path = _safe_relative_path(str(transaction.get("next_path", "/signin")))
        return GoogleIdentity(
            subject=subject,
            email=email,
            display_name=display_name,
            next_path=next_path,
        )

    async def aclose(self) -> None:
        await self.http_client.aclose()

    def _load_transaction(self, transaction_cookie: str) -> Mapping[str, Any]:
        try:
            transaction = self.serializer.loads(
                transaction_cookie,
                max_age=self.transaction_max_age_seconds,
            )
        except SignatureExpired as exc:
            raise GoogleOAuthError("OAuth transaction expired") from exc
        except (BadSignature, TypeError) as exc:
            raise GoogleOAuthError("OAuth transaction is invalid") from exc
        if not isinstance(transaction, Mapping):
            raise GoogleOAuthError("OAuth transaction is invalid")
        return transaction

    def _validate_identity_claims(
        self,
        claims: Mapping[str, Any],
        expected_nonce: str,
    ) -> None:
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
            or not isinstance(claims.get("email"), str)
            or not claims["email"].strip()
        ):
            raise GoogleOAuthError("Google identity claims are invalid")
        if claims.get("email_verified") is not True:
            raise GoogleOAuthError("Google identity requires a verified email")


def _safe_relative_path(value: str) -> str:
    parts = urlsplit(value)
    if (
        not value.startswith("/")
        or value.startswith("//")
        or value.startswith("/\\")
        or parts.scheme
        or parts.netloc
    ):
        return "/signin"
    return value


def _verify_google_id_token(token: str, audience: str) -> Mapping[str, Any]:
    from google.auth.transport import requests
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(token, requests.Request(), audience)
