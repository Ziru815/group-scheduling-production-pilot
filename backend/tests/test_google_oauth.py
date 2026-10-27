from base64 import urlsafe_b64encode
from hashlib import sha256
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from itsdangerous import URLSafeTimedSerializer

from app.adapters.google_oauth import GoogleOAuthClient, GoogleOAuthError


def decode_transaction(cookie: str):
    serializer = URLSafeTimedSerializer(
        "a-production-signing-secret-over-32-characters",
        salt="google-oauth-transaction",
    )
    return serializer.loads(cookie)


def verifier_with(**overrides):
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "client.apps.googleusercontent.com",
        "sub": "google-subject-123",
        "email": "Person@Example.com",
        "email_verified": True,
        "name": "Person Example",
    }
    claims.update(overrides)

    def verify(_token: str, _audience: str):
        return claims

    return verify


def oauth_client(
    transport: httpx.BaseTransport | None = None,
    *,
    verifier=None,
    transaction_max_age_seconds: int = 600,
):
    http_client = httpx.AsyncClient(transport=transport) if transport else httpx.AsyncClient()
    return GoogleOAuthClient(
        client_id="client.apps.googleusercontent.com",
        client_secret="google-secret",
        redirect_uri="https://scheduler.example/api/auth/google/callback",
        signing_secret="a-production-signing-secret-over-32-characters",
        http_client=http_client,
        id_token_verifier=verifier or verifier_with(),
        transaction_max_age_seconds=transaction_max_age_seconds,
    )


@pytest.mark.asyncio
async def test_begin_emits_random_state_nonce_and_s256_challenge():
    client = oauth_client()
    try:
        first = client.begin("/sessions")
        second = client.begin("/sessions")
        first_query = parse_qs(urlparse(first.authorization_url).query)
        second_query = parse_qs(urlparse(second.authorization_url).query)
        transaction = decode_transaction(first.transaction_cookie)

        assert first_query["response_type"] == ["code"]
        assert first_query["scope"] == ["openid email profile"]
        assert first_query["code_challenge_method"] == ["S256"]
        assert first_query["state"] == [transaction["state"]]
        assert first_query["nonce"] == [transaction["nonce"]]
        assert first_query["state"] != second_query["state"]
        assert first_query["nonce"] != second_query["nonce"]
        expected_challenge = urlsafe_b64encode(
            sha256(transaction["verifier"].encode()).digest()
        ).rstrip(b"=").decode()
        assert first_query["code_challenge"] == [expected_challenge]
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("/sessions/example?tab=results", "/sessions/example?tab=results"),
        ("https://attacker.example/steal", "/signin"),
        ("//attacker.example/steal", "/signin"),
        ("not-a-path", "/signin"),
    ],
)
async def test_begin_preserves_only_relative_next_path(requested, expected):
    client = oauth_client()
    try:
        start = client.begin(requested)
        transaction = decode_transaction(start.transaction_cookie)
        assert transaction["next_path"] == expected
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_callback_rejects_state_without_matching_transaction_cookie():
    client = oauth_client()
    try:
        first = client.begin("/sessions")
        second = client.begin("/sessions")
        copied_state = parse_qs(urlparse(first.authorization_url).query)["state"][0]

        with pytest.raises(GoogleOAuthError, match="transaction"):
            await client.complete("code", copied_state, second.transaction_cookie)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_callback_rejects_expired_transaction():
    client = oauth_client(transaction_max_age_seconds=-1)
    try:
        start = client.begin("/sessions")
        state = parse_qs(urlparse(start.authorization_url).query)["state"][0]

        with pytest.raises(GoogleOAuthError, match="expired"):
            await client.complete("code", state, start.transaction_cookie)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_callback_sends_original_code_verifier():
    posted = {}

    def exchange(request: httpx.Request):
        posted.update(parse_qs(request.content.decode()))
        return httpx.Response(200, json={"id_token": "signed-id-token"})

    client = oauth_client(httpx.MockTransport(exchange))
    try:
        start = client.begin("/sessions")
        transaction = decode_transaction(start.transaction_cookie)
        client.id_token_verifier = verifier_with(nonce=transaction["nonce"])
        state = parse_qs(urlparse(start.authorization_url).query)["state"][0]

        await client.complete("authorization-code", state, start.transaction_cookie)

        assert posted == {
            "code": ["authorization-code"],
            "client_id": ["client.apps.googleusercontent.com"],
            "client_secret": ["google-secret"],
            "redirect_uri": ["https://scheduler.example/api/auth/google/callback"],
            "grant_type": ["authorization_code"],
            "code_verifier": [transaction["verifier"]],
        }
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_complete_rejects_nonce_mismatch():
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"id_token": "signed-id-token"})
    )
    client = oauth_client(transport, verifier=verifier_with(nonce="wrong-nonce"))
    try:
        start = client.begin("/sessions")
        state = parse_qs(urlparse(start.authorization_url).query)["state"][0]

        with pytest.raises(GoogleOAuthError, match="identity"):
            await client.complete("code", state, start.transaction_cookie)
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "another-client.apps.googleusercontent.com"},
        {"iss": "https://attacker.example"},
    ],
)
async def test_complete_rejects_wrong_audience_or_issuer(claims):
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"id_token": "signed-id-token"})
    )
    client = oauth_client(transport)
    try:
        start = client.begin("/sessions")
        transaction = decode_transaction(start.transaction_cookie)
        client.id_token_verifier = verifier_with(nonce=transaction["nonce"], **claims)
        state = parse_qs(urlparse(start.authorization_url).query)["state"][0]

        with pytest.raises(GoogleOAuthError, match="identity"):
            await client.complete("code", state, start.transaction_cookie)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_verify_identity_rejects_unverified_email():
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"id_token": "signed-id-token"})
    )
    client = oauth_client(transport)
    try:
        start = client.begin("/sessions")
        transaction = decode_transaction(start.transaction_cookie)
        client.id_token_verifier = verifier_with(
            nonce=transaction["nonce"], email_verified=False
        )
        state = parse_qs(urlparse(start.authorization_url).query)["state"][0]

        with pytest.raises(GoogleOAuthError, match="verified email"):
            await client.complete("code", state, start.transaction_cookie)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_complete_returns_normalized_google_identity():
    verified = {}

    def verify(token: str, audience: str):
        verified.update(token=token, audience=audience)
        return verifier_with(nonce=None)(token, audience)

    def exchange(_request: httpx.Request):
        return httpx.Response(200, json={"id_token": "signed-id-token"})

    client = oauth_client(httpx.MockTransport(exchange), verifier=verify)
    try:
        start = client.begin("/sessions/example")
        transaction = decode_transaction(start.transaction_cookie)

        def verify_with_nonce(token: str, audience: str):
            claims = verifier_with(nonce=transaction["nonce"])(token, audience)
            verified.update(token=token, audience=audience)
            return claims

        client.id_token_verifier = verify_with_nonce
        state = parse_qs(urlparse(start.authorization_url).query)["state"][0]
        identity = await client.complete("code", state, start.transaction_cookie)

        assert verified == {
            "token": "signed-id-token",
            "audience": "client.apps.googleusercontent.com",
        }
        assert identity.subject == "google-subject-123"
        assert identity.email == "person@example.com"
        assert identity.display_name == "Person Example"
        assert identity.next_path == "/sessions/example"
    finally:
        await client.aclose()
