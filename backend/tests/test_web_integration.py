from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, SQLModel, create_engine, select
from fastapi.testclient import TestClient
import pytest

from app.adapters.google_oauth import GoogleIdentity, GoogleOAuthError, GoogleOAuthStart
from app.adapters.google_calendar_oauth import (
    GoogleCalendarGrant,
    GoogleCalendarOAuthError,
    GoogleCalendarOAuthStart,
)
from app.adapters.google_calendar_adapter import CalendarAuthorizationExpired, CalendarProviderUnavailable
from app.adapters.ports import CalendarBusyInterval
from app.core.config import settings
from app.core.database import get_db
from app.core.security import issue_app_token
from app.controllers.web_api import get_google_oauth_client
from app.main import app
from app.services import web_contract_service
from app.models import (
    ActivityType,
    CalendarConnection,
    CalendarCredential,
    CalendarEvent,
    ConnectionStatus,
    EventStatus,
    EventType,
    Participant,
    SchedulingSession,
    SupportStatus,
    UserAccount,
    Venue,
    VenueActivity,
    VenueCategory,
    VenueVerificationStatus,
)


def test_frontend_backend_recommender_round_trip(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'integrated.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as db:
        activity = ActivityType(category="SPORTS", name="Badminton")
        venues = [
            Venue(
                name="Bishan Sports Hall",
                category=VenueCategory.SPORTS_FACILITY,
                address="5 Bishan Street 14, Singapore 579783 (demo)",
                latitude=1.3547,
                longitude=103.8507,
                data_source="DATA_GOV_SG_SPORT_FACILITIES",
                postal_code="579783",
                source_key="a" * 64,
                last_synced_at=datetime(2026, 10, 28, 8, tzinfo=timezone.utc),
                verification_status=VenueVerificationStatus.VERIFIED_PUBLIC,
                minimum_group_size=2,
                optimal_group_size=8,
                advance_booking_lead_minutes=60,
            ),
            Venue(
                name="Toa Payoh Sports Hall",
                category=VenueCategory.SPORTS_FACILITY,
                address="297 Lorong 6 Toa Payoh, Singapore 319389 (demo)",
                latitude=1.3309,
                longitude=103.8517,
                data_source="DEMO",
                minimum_group_size=2,
                optimal_group_size=10,
                advance_booking_lead_minutes=60,
            ),
        ]
        db.add(activity)
        db.add_all(venues)
        db.flush()
        db.add_all(
            [
                VenueActivity(
                    venue_id=venue.venue_id,
                    activity_type_id=activity.activity_type_id,
                    support_status=SupportStatus.SUPPORTED,
                    source_reference=(
                        "https://www.activesgcircle.gov.sg/facilities/bishan-sports-hall"
                        if venue.name == "Bishan Sports Hall"
                        else None
                    ),
                )
                for venue in venues
            ]
        )
        db.commit()
        activity_id = str(activity.activity_type_id)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    original_debug = settings.debug_auth_enabled
    original_mock = settings.use_mock_providers
    original_calendar_enabled = settings.google_calendar_enabled
    settings.debug_auth_enabled = True
    settings.use_mock_providers = True
    settings.google_calendar_enabled = True
    try:
        with TestClient(app) as client:
            assert client.post("/api/dev/sign-in", json={"userId": "demo-organiser"}).status_code == 204
            activities = client.get("/api/activity-types").json()
            assert activities[0]["types"][0]["id"] == activity_id

            created = client.post(
                "/api/sessions",
                json={
                    "name": "Integrated badminton",
                    "activityTypeId": activity_id,
                    "startDate": "2030-11-07",
                    "endDate": "2030-11-07",
                    "dailyStartTime": "09:00",
                    "dailyEndTime": "13:00",
                    "timezone": "Asia/Singapore",
                    "durationMinutes": 60,
                    "responseDeadline": "2030-11-01T18:00:00+08:00",
                    "minimumAttendees": 2,
                },
            )
            assert created.status_code == 201, created.text
            body = created.json()
            session_id = body["session"]["id"]
            token = body["invitationUrl"].rsplit("/", 1)[-1]

            bishan = client.post("/api/locations/search", json={"query": "Bishan"}).json()["candidates"][0]
            response_payload = {
                "intervals": [{"start": "2030-11-07T09:00:00+08:00", "end": "2030-11-07T12:00:00+08:00"}],
                "calendarAssisted": False,
                "transportMode": "PUBLIC_TRANSPORT",
                "location": {"inputType": "ADDRESS", "input": "Bishan", "candidateId": bishan["candidateId"]},
            }
            too_short = {**response_payload, "intervals": [{"start": "2030-11-07T09:00:00+08:00", "end": "2030-11-07T09:30:00+08:00"}]}
            rejected = client.put(f"/api/sessions/{session_id}/my-response", json=too_short)
            assert rejected.status_code == 422
            assert "continuous 60-minute block" in rejected.json()["error"]["message"]
            assert client.put(f"/api/sessions/{session_id}/my-response", json=response_payload).status_code == 200

            assert client.post("/api/dev/sign-in", json={"userId": "demo-amirah"}).status_code == 204
            preview = client.post("/api/invitations/resolve", json={"token": token}).json()
            assert preview["alreadyJoined"] is False
            assert client.post("/api/invitations/join", json={"token": token}).status_code == 200
            amk = client.post("/api/locations/search", json={"query": "Ang Mo Kio"}).json()["candidates"][0]
            response_payload["location"] = {"inputType": "ADDRESS", "input": "Ang Mo Kio", "candidateId": amk["candidateId"]}
            assert client.put(f"/api/sessions/{session_id}/my-response", json=response_payload).status_code == 200

            assert client.post("/api/dev/sign-in", json={"userId": "demo-organiser"}).status_code == 204
            statuses = client.get(f"/api/sessions/{session_id}/responses").json()
            assert statuses["counts"]["SUBMITTED"] == 2
            assert all("location" not in participant for participant in statuses["participants"])

            # A requested minimum that narrowly misses must return labelled
            # best-available options rather than a dead-end error.
            raised = client.patch(f"/api/sessions/{session_id}", json={"minimumAttendees": 3})
            assert raised.status_code == 200, raised.text
            near = client.post(f"/api/sessions/{session_id}/recommendations")
            assert near.status_code == 200, near.text
            assert near.json()["isNearMatch"] is True
            assert near.json()["minimumAttendees"] == 3
            assert near.json()["combinations"][0]["meetsRequestedMinimum"] is False

            lowered = client.patch(f"/api/sessions/{session_id}", json={"minimumAttendees": 2})
            assert lowered.status_code == 200, lowered.text
            generated = client.post(f"/api/sessions/{session_id}/recommendations")
            assert generated.status_code == 200, generated.text
            recommendations = generated.json()
            assert recommendations["isNearMatch"] is False
            assert recommendations["combinations"]
            assert recommendations["combinations"][0]["feasibilityStatus"] == "FEASIBLE"
            bishan_venue = next(
                option["venue"]
                for option in recommendations["combinations"]
                if option["venue"]["name"] == "Bishan Sports Hall"
            )
            assert bishan_venue["dataSource"] == "Sport Singapore via data.gov.sg"
            assert bishan_venue["lastUpdated"] == "2026-10-28T08:00:00+00:00"
            assert bishan_venue["officialUrl"] == "https://www.activesgcircle.gov.sg/facilities/bishan-sports-hall"
            assert "available" not in bishan_venue
            assert "bookable" not in bishan_venue
            demo_venue = next(
                option["venue"]
                for option in recommendations["combinations"]
                if option["venue"]["name"] == "Toa Payoh Sports Hall"
            )
            assert demo_venue["officialUrl"] is None

            # Editing a response invalidates the first snapshot. Regeneration
            # must replace identical Candidate Timeslots instead of violating
            # their unique (Session, start, end) constraint.
            assert client.put(f"/api/sessions/{session_id}/my-response", json=response_payload).status_code == 200
            regenerated = client.post(f"/api/sessions/{session_id}/recommendations")
            assert regenerated.status_code == 200, regenerated.text
            assert regenerated.json()["combinations"]
            selected_option = regenerated.json()["combinations"][0]
            combination_id = selected_option["combinationId"]

            confirmed = client.post(f"/api/sessions/{session_id}/confirm", json={"combinationId": combination_id})
            assert confirmed.status_code == 200, confirmed.text
            assert confirmed.json()["status"] == "CONFIRMED"
            assert len(confirmed.json()["confirmed"]["attendees"]) == 2
            assert confirmed.json()["confirmed"]["venue"]["officialUrl"] == selected_option["venue"]["officialUrl"]
            assert confirmed.json()["confirmed"]["calendarSync"] == {
                "succeeded": 0,
                "failed": 0,
                "notConnected": 2,
                "canRetry": False,
            }

            retried = client.post(f"/api/sessions/{session_id}/calendar-sync")
            assert retried.status_code == 200, retried.text
            assert retried.json()["notConnected"] == 2
    finally:
        settings.debug_auth_enabled = original_debug
        settings.use_mock_providers = original_mock
        settings.google_calendar_enabled = original_calendar_enabled
        app.dependency_overrides.clear()


def test_official_url_rejects_untrusted_or_unsupported_references(tmp_path):
    assert hasattr(web_contract_service, "_official_url"), "official URL projection is not implemented"

    engine = create_engine(
        f"sqlite:///{tmp_path / 'official-links.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    cases = [
        ("Park HTTP", VenueCategory.PARK, "http://www.nparks.gov.sg/park-http", SupportStatus.SUPPORTED, None),
        (
            "Park deceptive suffix",
            VenueCategory.PARK,
            "https://nparks.gov.sg.evil.example/park",
            SupportStatus.SUPPORTED,
            None,
        ),
        ("Park unrelated", VenueCategory.PARK, "https://example.com/park", SupportStatus.SUPPORTED, None),
        (
            "Park wrong official family",
            VenueCategory.PARK,
            "https://www.activesgcircle.gov.sg/facilities/park",
            SupportStatus.SUPPORTED,
            None,
        ),
        (
            "Sport wrong official family",
            VenueCategory.SPORTS_FACILITY,
            "https://www.nparks.gov.sg/sport",
            SupportStatus.SUPPORTED,
            None,
        ),
        (
            "Unsupported park",
            VenueCategory.PARK,
            "https://www.nparks.gov.sg/parks/unsupported",
            SupportStatus.UNAVAILABLE,
            None,
        ),
        (
            "Reviewed park subdomain",
            VenueCategory.PARK,
            "https://beta.nparks.gov.sg/parks/reviewed",
            SupportStatus.SUPPORTED,
            "https://beta.nparks.gov.sg/parks/reviewed",
        ),
        (
            "Reviewed sport subdomain",
            VenueCategory.SPORTS_FACILITY,
            "https://venues.activesgcircle.gov.sg/facilities/reviewed",
            SupportStatus.SUPPORTED,
            "https://venues.activesgcircle.gov.sg/facilities/reviewed",
        ),
    ]

    with Session(engine) as db:
        activity = ActivityType(category="TEST", name="Official URL validation")
        db.add(activity)
        db.flush()
        rows = []
        for index, (name, category, reference, status, expected) in enumerate(cases):
            venue = Venue(
                name=name,
                category=category,
                address=f"{index} Test Street, Singapore",
                latitude=1.30 + index / 1000,
                longitude=103.80 + index / 1000,
                data_source="TEST",
            )
            db.add(venue)
            db.flush()
            db.add(
                VenueActivity(
                    venue_id=venue.venue_id,
                    activity_type_id=activity.activity_type_id,
                    support_status=status,
                    source_reference=reference,
                )
            )
            rows.append((venue, expected))
        db.commit()

        assert [
            web_contract_service._official_url(db, venue, activity.activity_type_id)
            for venue, _ in rows
        ] == [expected for _, expected in rows]


class FakeGoogleOAuthClient:
    def __init__(self, *, fail_complete=False):
        self.begin_paths = []
        self.complete_calls = []
        self.fail_complete = fail_complete

    def begin(self, next_path):
        self.begin_paths.append(next_path)
        return GoogleOAuthStart(
            authorization_url="https://accounts.google.test/authorize",
            transaction_cookie="signed-browser-transaction",
        )

    async def complete(self, code, returned_state, transaction_cookie):
        self.complete_calls.append((code, returned_state, transaction_cookie))
        if self.fail_complete:
            raise GoogleOAuthError("test failure")
        return GoogleIdentity(
            subject="google-subject-123",
            email="person@example.com",
            display_name="Person Example",
            next_path="/sessions",
        )


def oauth_test_client(tmp_path, fake):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'oauth-web.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_google_oauth_client] = lambda: fake
    return TestClient(app, base_url="https://testserver")


def set_oauth_test_settings():
    original = {
        "debug_auth_enabled": settings.debug_auth_enabled,
        "session_cookie_secure": settings.session_cookie_secure,
        "frontend_base_url": settings.frontend_base_url,
        "use_mock_providers": settings.use_mock_providers,
        "google_client_id": settings.google_client_id,
        "google_client_secret": settings.google_client_secret,
    }
    settings.debug_auth_enabled = False
    settings.session_cookie_secure = True
    settings.frontend_base_url = "https://scheduler.example"
    settings.use_mock_providers = False
    settings.google_client_id = "client.apps.googleusercontent.com"
    settings.google_client_secret = "google-secret"
    return original


def restore_oauth_test_settings(original):
    for key, value in original.items():
        setattr(settings, key, value)
    app.dependency_overrides.clear()


def test_google_login_sets_http_only_transaction_cookie(tmp_path):
    fake = FakeGoogleOAuthClient()
    original = set_oauth_test_settings()
    try:
        with oauth_test_client(tmp_path, fake) as client:
            response = client.get(
                "/api/auth/google/login?next=/sessions/example",
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert response.headers["location"] == "https://accounts.google.test/authorize"
        cookie = response.headers["set-cookie"]
        assert "google_oauth_transaction=signed-browser-transaction" in cookie
        assert "HttpOnly" in cookie
        assert "Secure" in cookie
        assert "SameSite=lax" in cookie
        assert "Path=/" in cookie
        assert "Max-Age=600" in cookie
    finally:
        restore_oauth_test_settings(original)


def test_callback_requires_matching_cookie(tmp_path):
    fake = FakeGoogleOAuthClient()
    original = set_oauth_test_settings()
    try:
        with oauth_test_client(tmp_path, fake) as client:
            response = client.get(
                "/api/auth/google/callback?code=code&state=state",
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert response.headers["location"].endswith("/signin?error=unavailable")
        assert fake.complete_calls == []
    finally:
        restore_oauth_test_settings(original)


@pytest.mark.parametrize(
    "callback_path",
    [
        "/api/auth/google/callback?error=access_denied",
        "/api/auth/google/callback?code=code&state=state",
    ],
)
def test_callback_always_clears_transaction_cookie(tmp_path, callback_path):
    fake = FakeGoogleOAuthClient(fail_complete=True)
    original = set_oauth_test_settings()
    try:
        with oauth_test_client(tmp_path, fake) as client:
            client.cookies.set("google_oauth_transaction", "signed-browser-transaction")
            response = client.get(callback_path, follow_redirects=False)

        cookie = response.headers["set-cookie"]
        assert "google_oauth_transaction=" in cookie
        assert "Max-Age=0" in cookie
        assert "Path=/" in cookie
    finally:
        restore_oauth_test_settings(original)


def test_callback_sets_secure_app_cookie(tmp_path):
    fake = FakeGoogleOAuthClient()
    original = set_oauth_test_settings()
    try:
        with oauth_test_client(tmp_path, fake) as client:
            client.cookies.set("google_oauth_transaction", "signed-browser-transaction")
            response = client.get(
                "/api/auth/google/callback?code=code&state=state",
                follow_redirects=False,
            )

        cookies = response.headers.get_list("set-cookie")
        app_cookie = next(value for value in cookies if settings.session_cookie_name in value)
        assert "HttpOnly" in app_cookie
        assert "Secure" in app_cookie
        assert "SameSite=lax" in app_cookie
        assert "Path=/" in app_cookie
        assert fake.complete_calls == [
            ("code", "state", "signed-browser-transaction")
        ]
    finally:
        restore_oauth_test_settings(original)


def test_login_replaces_external_next_with_signin(tmp_path):
    fake = FakeGoogleOAuthClient()
    original = set_oauth_test_settings()
    try:
        with oauth_test_client(tmp_path, fake) as client:
            client.get(
                "/api/auth/google/login?next=https://attacker.example/steal",
                follow_redirects=False,
            )

        assert fake.begin_paths == ["/signin"]
    finally:
        restore_oauth_test_settings(original)


def test_legacy_google_id_token_endpoint_is_removed(tmp_path):
    fake = FakeGoogleOAuthClient()
    original = set_oauth_test_settings()
    try:
        with oauth_test_client(tmp_path, fake) as client:
            response = client.post(
                "/api/v1/auth/google",
                json={"id_token": "unbound-id-token"},
            )

        assert response.status_code == 404
    finally:
        restore_oauth_test_settings(original)


def test_production_denies_debug_auth_and_starts_real_google_flow(tmp_path, monkeypatch):
    fake = FakeGoogleOAuthClient()
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://app:secret@db/group")
    monkeypatch.setattr(settings, "auto_create_tables", False)
    monkeypatch.setattr(settings, "app_session_secret", "a-production-signing-secret-over-32-characters")
    monkeypatch.setattr(settings, "debug_auth_enabled", False)
    monkeypatch.setattr(settings, "use_mock_providers", False)
    monkeypatch.setattr(settings, "session_cookie_secure", True)
    monkeypatch.setattr(settings, "frontend_base_url", "https://scheduler.example")
    monkeypatch.setattr(settings, "google_client_id", "client.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "google_client_secret", "google-secret")
    monkeypatch.setattr(settings, "onemap_token", "onemap-token")

    database_path = tmp_path / "oauth-web.db"
    with oauth_test_client(tmp_path, fake) as client:
        users = client.get("/api/dev/users")
        sign_in = client.post("/api/dev/sign-in", json={"userId": "demo-organiser"})
        google = client.get("/api/auth/google/login", follow_redirects=False)

    assert users.status_code == 404
    assert sign_in.status_code == 404
    assert google.status_code == 302
    assert fake.begin_paths == ["/signin"]
    assert settings.session_cookie_name not in google.headers["set-cookie"]
    with Session(
        create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
        )
    ) as db:
        assert db.exec(select(UserAccount)).all() == []


class FakeGoogleCalendarOAuthClient:
    def __init__(self, grant=None, error: GoogleCalendarOAuthError | None = None):
        self.begin_calls = []
        self.complete_calls = []
        self.grant = grant
        self.error = error
        self.decline_calls = []

    def begin(self, account_id, provider_subject, next_path):
        self.begin_calls.append((account_id, provider_subject, next_path))
        return GoogleCalendarOAuthStart(
            authorization_url="https://accounts.google.test/calendar-authorize",
            transaction_cookie="signed-calendar-transaction",
        )

    async def complete(self, code, returned_state, transaction_cookie):
        self.complete_calls.append((code, returned_state, transaction_cookie))
        if self.error:
            raise self.error
        return self.grant

    def decline(self, returned_state, transaction_cookie):
        self.decline_calls.append((returned_state, transaction_cookie))
        return "/profile"


def calendar_oauth_test_client(tmp_path, fake):
    from app.controllers import web_api

    engine = create_engine(
        f"sqlite:///{tmp_path / 'calendar-oauth-web.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        account = UserAccount(
            email="calendar-owner@example.com",
            display_name="Calendar Owner",
            provider_user_id="google-calendar-owner",
        )
        db.add(account)
        db.flush()
        activity = ActivityType(category="SPORTS", name="Calendar OAuth badminton")
        db.add(activity)
        db.flush()
        session_ids = [
            UUID("11111111-1111-1111-1111-111111111111"),
            UUID("22222222-2222-2222-2222-222222222222"),
        ]
        for index, session_id in enumerate(session_ids):
            db.add(
                SchedulingSession(
                    session_id=session_id,
                    name=f"Calendar session {index}",
                    activity_type_id=activity.activity_type_id,
                    date_range_start=datetime(2030, 11, 7, 1, tzinfo=timezone.utc),
                    date_range_end=datetime(2030, 11, 7, 5, tzinfo=timezone.utc),
                    response_deadline=datetime(2030, 11, 1, 1, tzinfo=timezone.utc),
                    invitation_token=f"calendar-session-{index}",
                )
            )
        db.flush()
        db.add_all(
            [
                Participant(
                    user_account_id=account.account_id,
                    session_id=UUID("11111111-1111-1111-1111-111111111111"),
                    display_name=account.display_name,
                ),
                Participant(
                    user_account_id=account.account_id,
                    session_id=UUID("22222222-2222-2222-2222-222222222222"),
                    display_name=account.display_name,
                ),
            ]
        )
        db.commit()
        account_id = account.account_id

    def override_db():
        with Session(engine) as db:
            yield db

    original = {
        "google_calendar_enabled": settings.google_calendar_enabled,
        "google_calendar_redirect_uri": settings.google_calendar_redirect_uri,
        "google_calendar_credential_key": settings.google_calendar_credential_key,
        "session_cookie_secure": settings.session_cookie_secure,
        "frontend_base_url": settings.frontend_base_url,
        "use_mock_providers": settings.use_mock_providers,
    }
    settings.google_calendar_enabled = True
    settings.google_calendar_redirect_uri = "https://scheduler.example/api/calendar/google/callback"
    settings.google_calendar_credential_key = "Y2FsZW5kYXItY3JlZGVudGlhbC10ZXN0LWtleS0zMmI="
    settings.session_cookie_secure = True
    settings.frontend_base_url = "https://scheduler.example"
    settings.use_mock_providers = False
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[web_api.get_google_calendar_oauth_client] = lambda: fake
    app.dependency_overrides[web_api.get_google_calendar_adapter] = lambda: FakeGoogleCalendarAdapter(())
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(settings.session_cookie_name, issue_app_token(account_id))
    return client, engine, account_id, original


def close_calendar_oauth_test_client(client, original):
    client.close()
    for key, value in original.items():
        setattr(settings, key, value)
    app.dependency_overrides.clear()


def test_calendar_connect_from_profile_sets_separate_browser_transaction(tmp_path):
    fake = FakeGoogleCalendarOAuthClient()
    client, _engine, account_id, original = calendar_oauth_test_client(tmp_path, fake)
    try:
        response = client.get("/api/calendar/google/connect?next=/profile", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "https://accounts.google.test/calendar-authorize"
        assert fake.begin_calls == [(account_id, "google-calendar-owner", "/profile")]
        cookie = response.headers["set-cookie"]
        assert "google_calendar_oauth_transaction=signed-calendar-transaction" in cookie
        assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    finally:
        close_calendar_oauth_test_client(client, original)


def test_calendar_callback_connects_all_participant_rows_without_exposing_token(tmp_path):
    fake = FakeGoogleCalendarOAuthClient()
    client, engine, account_id, original = calendar_oauth_test_client(tmp_path, fake)
    fake.grant = GoogleCalendarGrant(
        account_id=account_id,
        subject="google-calendar-owner",
        refresh_token="never-return-this-refresh-token",
        granted_scopes=(
            "openid",
            "email",
            "https://www.googleapis.com/auth/calendar.freebusy",
            "https://www.googleapis.com/auth/calendar.app.created",
        ),
        next_path="/profile",
    )
    try:
        client.cookies.set(settings.google_calendar_oauth_transaction_cookie_name, "signed-calendar-transaction")
        response = client.get(
            "/api/calendar/google/callback?code=code&state=state",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "https://scheduler.example/profile?calendar=connected"
        assert "never-return-this-refresh-token" not in str(response.headers)
        assert "never-return-this-refresh-token" not in response.text
        assert "Max-Age=0" in response.headers["set-cookie"]

        with Session(engine) as db:
            credential = db.exec(select(CalendarCredential)).one()
            connections = list(db.exec(select(CalendarConnection)).all())
            assert credential.status == ConnectionStatus.CONNECTED
            assert credential.encrypted_refresh_token != "never-return-this-refresh-token"
            assert len(connections) == 2
            assert {row.credential_reference for row in connections} == {f"db:{credential.credential_id}"}
            assert all(row.connection_status == ConnectionStatus.CONNECTED for row in connections)

        status = client.get("/api/calendar/connection")
        assert status.json() == {"status": "CONNECTED"}
    finally:
        close_calendar_oauth_test_client(client, original)


@pytest.mark.parametrize(
    ("query", "suffix"),
    [
        ("error=access_denied&state=state", "?calendar=declined"),
        ("code=code&state=state", "?calendar=wrong-account"),
    ],
)
def test_calendar_callback_clears_transaction_and_returns_recoverable_state(tmp_path, query, suffix):
    fake = FakeGoogleCalendarOAuthClient(error=GoogleCalendarOAuthError("Choose the same Google account used to sign in"))
    client, _engine, _account_id, original = calendar_oauth_test_client(tmp_path, fake)
    try:
        client.cookies.set(settings.google_calendar_oauth_transaction_cookie_name, "signed-calendar-transaction")
        response = client.get(f"/api/calendar/google/callback?{query}", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"].endswith(suffix)
        assert "Max-Age=0" in response.headers["set-cookie"]
    finally:
        close_calendar_oauth_test_client(client, original)


@pytest.mark.parametrize(
    ("adapter_outcome", "expected_event_status", "credential_key"),
    [
        ((), EventStatus.DELETED, "configured"),
        (RuntimeError("provider cleanup failed"), EventStatus.ERROR, "configured"),
        ((), EventStatus.DELETED, ""),
        ((), EventStatus.DELETED, "not-a-fernet-key"),
    ],
)
def test_calendar_disconnect_clears_user_credential_and_all_connections(
    tmp_path, adapter_outcome, expected_event_status, credential_key
):
    from app.controllers import web_api

    fake = FakeGoogleCalendarOAuthClient()
    client, engine, account_id, original = calendar_oauth_test_client(tmp_path, fake)
    adapter = FakeGoogleCalendarAdapter(())
    fake.grant = GoogleCalendarGrant(
        account_id=account_id,
        subject="google-calendar-owner",
        refresh_token="refresh-token",
        granted_scopes=("openid", "email", "https://www.googleapis.com/auth/calendar.freebusy", "https://www.googleapis.com/auth/calendar.app.created"),
        next_path="/profile",
    )
    try:
        app.dependency_overrides[web_api.get_google_calendar_adapter] = lambda: adapter
        client.cookies.set(settings.google_calendar_oauth_transaction_cookie_name, "signed-calendar-transaction")
        client.get("/api/calendar/google/callback?code=code&state=state", follow_redirects=False)
        adapter.outcome = adapter_outcome
        with Session(engine) as db:
            credential = db.exec(select(CalendarCredential)).one()
            credential.google_calendar_id = "group-scheduler@example.com"
            connections = list(db.exec(select(CalendarConnection)).all())
            for index, connection in enumerate(connections):
                db.add_all(
                    [CalendarEvent(
                        calendar_connection_id=connection.connection_id,
                        session_id=UUID(f"{index + 1}{index + 1}{index + 1}{index + 1}{index + 1}{index + 1}{index + 1}{index + 1}-1111-1111-1111-111111111111"),
                        event_type=EventType.TENTATIVE_HOLD,
                        event_status=EventStatus.ACTIVE,
                        provider_event_id=f"owned-hold-{index}",
                    ), CalendarEvent(
                        calendar_connection_id=connection.connection_id,
                        session_id=UUID(f"{index + 1}{index + 1}{index + 1}{index + 1}{index + 1}{index + 1}{index + 1}{index + 1}-1111-1111-1111-111111111111"),
                        event_type=EventType.CONFIRMED_EVENT,
                        event_status=EventStatus.ACTIVE,
                        provider_event_id=f"confirmed-event-{index}",
                    )]
                )
            db.commit()
        if credential_key != "configured":
            settings.google_calendar_credential_key = credential_key
        response = client.delete("/api/calendar/connection")
        assert response.status_code == 204
        with Session(engine) as db:
            credential = db.exec(select(CalendarCredential)).one()
            connections = list(db.exec(select(CalendarConnection)).all())
            events = list(db.exec(select(CalendarEvent)).all())
            holds = [event for event in events if event.event_type == EventType.TENTATIVE_HOLD]
            confirmed = [event for event in events if event.event_type == EventType.CONFIRMED_EVENT]
            assert credential.status == ConnectionStatus.DISCONNECTED
            assert credential.encrypted_refresh_token is None
            assert all(row.connection_status == ConnectionStatus.DISCONNECTED for row in connections)
            assert all(row.credential_reference is None for row in connections)
            assert all(row.event_status == expected_event_status for row in holds)
            assert all(row.event_status == EventStatus.ACTIVE for row in confirmed)
            if expected_event_status == EventStatus.DELETED:
                assert len(adapter.deleted) == 2
                assert adapter.revoked == [f"db:{credential.credential_id}"]
            else:
                assert adapter.deleted == []
                assert adapter.revoked == []
    finally:
        close_calendar_oauth_test_client(client, original)


def test_calendar_feature_flag_blocks_existing_connection_provider_calls(tmp_path):
    from app.controllers import web_api

    fake_oauth = FakeGoogleCalendarOAuthClient()
    client, _engine, account_id, original = calendar_oauth_test_client(tmp_path, fake_oauth)
    adapter = FakeGoogleCalendarAdapter(AssertionError("provider must stay disabled"))
    try:
        _connect_calendar_for_busy_import(client, fake_oauth, account_id)
        app.dependency_overrides[web_api.get_google_calendar_adapter] = lambda: adapter
        settings.google_calendar_enabled = False

        response = client.post("/api/sessions/11111111-1111-1111-1111-111111111111/calendar-busy")

        assert response.status_code == 200
        assert response.json() == {"status": "UNAVAILABLE", "busy": []}
        assert adapter.calls == []
    finally:
        close_calendar_oauth_test_client(client, original)


class FakeGoogleCalendarAdapter:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []
        self.deleted = []
        self.revoked = []
        self.ensured = []

    async def ensure_app_calendar(self, credential_reference, timezone_name):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        self.ensured.append((credential_reference, timezone_name))
        return "group-scheduler@example.com"

    async def free_busy(self, credential_reference, start, end, timezone_name):
        self.calls.append((credential_reference, start, end, timezone_name))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    async def delete_event(self, credential_reference, provider_event_id):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        self.deleted.append((credential_reference, provider_event_id))

    async def revoke(self, credential_reference):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        self.revoked.append(credential_reference)


def _connect_calendar_for_busy_import(client, fake_oauth, account_id):
    fake_oauth.grant = GoogleCalendarGrant(
        account_id=account_id,
        subject="google-calendar-owner",
        refresh_token="refresh-token",
        granted_scopes=("openid", "email", "https://www.googleapis.com/auth/calendar.freebusy", "https://www.googleapis.com/auth/calendar.app.created"),
        next_path="/sessions",
    )
    client.cookies.set(settings.google_calendar_oauth_transaction_cookie_name, "signed-calendar-transaction")
    response = client.get("/api/calendar/google/callback?code=code&state=state", follow_redirects=False)
    assert response.status_code == 302


def test_calendar_busy_import_returns_only_interval_bounds(tmp_path):
    from app.controllers import web_api

    fake_oauth = FakeGoogleCalendarOAuthClient()
    client, _engine, account_id, original = calendar_oauth_test_client(tmp_path, fake_oauth)
    fake_adapter = FakeGoogleCalendarAdapter(
        (CalendarBusyInterval(datetime(2030, 11, 7, 2, tzinfo=timezone.utc), datetime(2030, 11, 7, 3, tzinfo=timezone.utc)),)
    )
    try:
        _connect_calendar_for_busy_import(client, fake_oauth, account_id)
        app.dependency_overrides[web_api.get_google_calendar_adapter] = lambda: fake_adapter
        response = client.post("/api/sessions/11111111-1111-1111-1111-111111111111/calendar-busy")
        assert response.status_code == 200
        assert response.json() == {
            "status": "RECEIVED",
            "busy": [{"start": "2030-11-07T02:00:00Z", "end": "2030-11-07T03:00:00Z"}],
        }
        assert fake_adapter.calls[0][3] == "Asia/Singapore"
    finally:
        close_calendar_oauth_test_client(client, original)


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_body"),
    [
        (CalendarProviderUnavailable("provider detail"), 200, {"status": "UNAVAILABLE", "busy": []}),
        (CalendarAuthorizationExpired("reconnect"), 409, "CALENDAR_NOT_CONNECTED"),
    ],
)
def test_calendar_busy_import_degrades_or_requires_reconnect(tmp_path, error, expected_status, expected_body):
    from app.controllers import web_api

    fake_oauth = FakeGoogleCalendarOAuthClient()
    client, _engine, account_id, original = calendar_oauth_test_client(tmp_path, fake_oauth)
    fake_adapter = FakeGoogleCalendarAdapter(error)
    try:
        _connect_calendar_for_busy_import(client, fake_oauth, account_id)
        app.dependency_overrides[web_api.get_google_calendar_adapter] = lambda: fake_adapter
        response = client.post("/api/sessions/11111111-1111-1111-1111-111111111111/calendar-busy")
        assert response.status_code == expected_status
        if isinstance(expected_body, dict):
            assert response.json() == expected_body
        else:
            assert response.json()["error"]["code"] == expected_body
    finally:
        close_calendar_oauth_test_client(client, original)

