from base64 import urlsafe_b64encode
from hashlib import sha256
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import httpx
import pytest
from itsdangerous import URLSafeTimedSerializer


ACCOUNT_ID = UUID("11111111-1111-1111-1111-111111111111")
SUBJECT = "google-subject-123"
REQUIRED_SCOPES = {
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.freebusy",
    "https://www.googleapis.com/auth/calendar.app.created",
}


def _module():
    from app.adapters import google_calendar_oauth

    return google_calendar_oauth


def _decode(cookie: str) -> dict:
    return URLSafeTimedSerializer(
        "a-production-signing-secret-over-32-characters",
        salt="google-calendar-oauth-transaction",
    ).loads(cookie)


def _verifier(**overrides):
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "client.apps.googleusercontent.com",
        "sub": SUBJECT,
        "email": "owner@example.com",
        "email_verified": True,
    }
    claims.update(overrides)
    return lambda _token, _audience: claims


def _client(transport=None, *, verifier=None, max_age=600):
    module = _module()
    return module.GoogleCalendarOAuthClient(
        client_id="client.apps.googleusercontent.com",
        client_secret="google-secret",
        redirect_uri="https://scheduler.example/api/calendar/google/callback",
        signing_secret="a-production-signing-secret-over-32-characters",
        http_client=httpx.AsyncClient(transport=transport),
        id_token_verifier=verifier or _verifier(),
        transaction_max_age_seconds=max_age,
    )


@pytest.mark.asyncio
async def test_begin_requests_exact_calendar_scopes_offline_consent_and_binds_browser():
    client = _client()
    try:
        start = client.begin(ACCOUNT_ID, SUBJECT, "/profile")
        query = parse_qs(urlparse(start.authorization_url).query)
        transaction = _decode(start.transaction_cookie)

        assert set(query["scope"][0].split()) == REQUIRED_SCOPES
        assert query["access_type"] == ["offline"]
        assert query["include_granted_scopes"] == ["true"]
        assert query["prompt"] == ["consent"]
        assert query["code_challenge_method"] == ["S256"]
        expected = urlsafe_b64encode(sha256(transaction["verifier"].encode()).digest()).rstrip(b"=").decode()
        assert query["code_challenge"] == [expected]
        assert transaction["account_id"] == str(ACCOUNT_ID)
        assert transaction["provider_subject"] == SUBJECT
        assert transaction["next_path"] == "/profile"
        assert "google-secret" not in start.authorization_url
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("/profile", "/profile"),
        ("/sessions", "/sessions"),
        ("/sessions/22222222-2222-2222-2222-222222222222/availability", "/sessions/22222222-2222-2222-2222-222222222222/availability"),
        ("/join/invitation-token", "/sessions"),
        ("https://attacker.example/steal", "/sessions"),
        ("//attacker.example/steal", "/sessions"),
    ],
)
async def test_begin_allows_only_calendar_safe_return_paths(requested, expected):
    client = _client()
    try:
        start = client.begin(ACCOUNT_ID, SUBJECT, requested)
        assert _decode(start.transaction_cookie)["next_path"] == expected
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_complete_returns_verified_grant_and_original_pkce_verifier():
    posted = {}

    def exchange(request: httpx.Request):
        posted.update(parse_qs(request.content.decode()))
        return httpx.Response(
            200,
            json={
                "id_token": "signed-id-token",
                "refresh_token": "refresh-secret",
                "scope": " ".join(sorted(REQUIRED_SCOPES)),
            },
        )

    client = _client(httpx.MockTransport(exchange))
    try:
        start = client.begin(ACCOUNT_ID, SUBJECT, "/profile")
        transaction = _decode(start.transaction_cookie)
        client.id_token_verifier = _verifier(nonce=transaction["nonce"])
        grant = await client.complete("code", transaction["state"], start.transaction_cookie)

        assert posted["code_verifier"] == [transaction["verifier"]]
        assert grant.account_id == ACCOUNT_ID
        assert grant.subject == SUBJECT
        assert grant.refresh_token == "refresh-secret"
        assert set(grant.granted_scopes) == REQUIRED_SCOPES
        assert grant.next_path == "/profile"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_complete_accepts_calendar_grant_when_google_omits_oidc_aliases_from_token_scope():
    calendar_scopes = {
        "https://www.googleapis.com/auth/calendar.freebusy",
        "https://www.googleapis.com/auth/calendar.app.created",
    }
    client = _client(
        httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "id_token": "signed",
                    "refresh_token": "refresh-secret",
                    "scope": " ".join(sorted(calendar_scopes)),
                },
            )
        )
    )
    try:
        start = client.begin(ACCOUNT_ID, SUBJECT, "/profile")
        transaction = _decode(start.transaction_cookie)
        client.id_token_verifier = _verifier(nonce=transaction["nonce"])

        grant = await client.complete("code", transaction["state"], start.transaction_cookie)

        assert set(grant.granted_scopes) == calendar_scopes
        assert grant.next_path == "/profile"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_complete_allows_same_subject_reconnect_without_new_refresh_token():
    client = _client(
        httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"id_token": "signed", "scope": " ".join(sorted(REQUIRED_SCOPES))},
            )
        )
    )
    try:
        start = client.begin(ACCOUNT_ID, SUBJECT, "/sessions")
        transaction = _decode(start.transaction_cookie)
        client.id_token_verifier = _verifier(nonce=transaction["nonce"])
        grant = await client.complete("code", transaction["state"], start.transaction_cookie)
        assert grant.refresh_token is None
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_complete_rejects_wrong_google_subject_and_missing_scope():
    response = {
        "id_token": "signed",
        "refresh_token": "must-be-discarded",
        "scope": " ".join(sorted(REQUIRED_SCOPES - {"https://www.googleapis.com/auth/calendar.app.created"})),
    }
    client = _client(httpx.MockTransport(lambda _request: httpx.Response(200, json=response)))
    try:
        start = client.begin(ACCOUNT_ID, SUBJECT, "/sessions")
        transaction = _decode(start.transaction_cookie)
        client.id_token_verifier = _verifier(nonce=transaction["nonce"], sub="different-subject")
        with pytest.raises(_module().GoogleCalendarOAuthError, match="same Google account"):
            await client.complete("code", transaction["state"], start.transaction_cookie)

        other = client.begin(ACCOUNT_ID, SUBJECT, "/sessions")
        other_transaction = _decode(other.transaction_cookie)
        client.id_token_verifier = _verifier(nonce=other_transaction["nonce"])
        with pytest.raises(_module().GoogleCalendarOAuthError, match="scope"):
            await client.complete("code", other_transaction["state"], other.transaction_cookie)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_complete_rejects_mismatch_expiry_and_reuse():
    client = _client(httpx.MockTransport(lambda _request: httpx.Response(500)))
    try:
        first = client.begin(ACCOUNT_ID, SUBJECT, "/sessions")
        second = client.begin(ACCOUNT_ID, SUBJECT, "/sessions")
        transaction = _decode(first.transaction_cookie)
        with pytest.raises(_module().GoogleCalendarOAuthError, match="transaction"):
            await client.complete("code", transaction["state"], second.transaction_cookie)
    finally:
        await client.aclose()

    expired = _client(httpx.MockTransport(lambda _request: httpx.Response(500)), max_age=-1)
    try:
        start = expired.begin(ACCOUNT_ID, SUBJECT, "/sessions")
        with pytest.raises(_module().GoogleCalendarOAuthError, match="expired"):
            await expired.complete("code", _decode(start.transaction_cookie)["state"], start.transaction_cookie)
    finally:
        await expired.aclose()


@pytest.mark.asyncio
async def test_complete_rejects_reused_transaction():
    client = _client(
        httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "id_token": "signed",
                    "refresh_token": "refresh-secret",
                    "scope": " ".join(sorted(REQUIRED_SCOPES)),
                },
            )
        )
    )
    try:
        start = client.begin(ACCOUNT_ID, SUBJECT, "/sessions")
        transaction = _decode(start.transaction_cookie)
        client.id_token_verifier = _verifier(nonce=transaction["nonce"])
        await client.complete("code", transaction["state"], start.transaction_cookie)
        with pytest.raises(_module().GoogleCalendarOAuthError, match="already used"):
            await client.complete("another-code", transaction["state"], start.transaction_cookie)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_decline_validates_and_consumes_returned_state():
    client = _client()
    try:
        start = client.begin(ACCOUNT_ID, SUBJECT, "/profile")
        transaction = _decode(start.transaction_cookie)
        with pytest.raises(_module().GoogleCalendarOAuthError, match="did not match"):
            client.decline("forged-state", start.transaction_cookie)
        assert client.decline(transaction["state"], start.transaction_cookie) == "/profile"
        with pytest.raises(_module().GoogleCalendarOAuthError, match="already used"):
            client.decline(transaction["state"], start.transaction_cookie)
    finally:
        await client.aclose()
