import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

import app.main as main_module
from app.core.config import Settings
from app.models import ActivityType, Venue
from scripts.seed_reference_data import seed_reference_data


def production_settings(**overrides) -> Settings:
    values = {
        "app_environment": "production",
        "database_url": "postgresql+psycopg://app:secret@db.internal:5432/group_scheduler",
        "auto_create_tables": False,
        "google_client_id": "client.apps.googleusercontent.com",
        "google_client_secret": "google-secret",
        "google_redirect_uri": "https://scheduler.example/api/auth/google/callback",
        "app_session_secret": "a-production-signing-secret-over-32-characters",
        "session_cookie_secure": True,
        "frontend_base_url": "https://scheduler.example",
        "debug_auth_enabled": False,
        "use_mock_providers": False,
        "onemap_token": "onemap-token",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_calendar_feature_requires_redirect_and_credential_key():
    with pytest.raises(ValueError, match="GOOGLE_CALENDAR_REDIRECT_URI"):
        production_settings(
            google_calendar_enabled=True,
            google_calendar_redirect_uri=None,
            google_calendar_credential_key=None,
        ).validate_runtime()

    with pytest.raises(ValueError, match="GOOGLE_CALENDAR_CREDENTIAL_KEY"):
        production_settings(
            google_calendar_enabled=True,
            google_calendar_redirect_uri="https://scheduler.example/api/calendar/google/callback",
            google_calendar_credential_key=None,
        ).validate_runtime()


def test_production_calendar_feature_can_remain_disabled_without_calendar_secrets():
    production_settings(
        google_calendar_enabled=False,
        google_calendar_redirect_uri=None,
        google_calendar_credential_key=None,
    ).validate_runtime()


def test_production_rejects_default_secret():
    settings = production_settings(app_session_secret="change-me-before-deployment")

    with pytest.raises(ValueError, match="APP_SESSION_SECRET"):
        settings.validate_runtime()


def test_production_rejects_short_secret():
    settings = production_settings(app_session_secret="too-short")

    with pytest.raises(ValueError, match="APP_SESSION_SECRET"):
        settings.validate_runtime()


def test_production_requires_postgresql():
    settings = production_settings(database_url="sqlite:///./production.db")

    with pytest.raises(ValueError, match="DATABASE_URL"):
        settings.validate_runtime()


def test_railway_postgresql_url_uses_psycopg_driver():
    settings = production_settings(
        database_url="postgresql://app:secret@db.internal:5432/group_scheduler?sslmode=require"
    )

    settings.validate_runtime()

    assert settings.database_url == (
        "postgresql+psycopg://app:secret@db.internal:5432/group_scheduler?sslmode=require"
    )


def test_production_rejects_automatic_table_creation():
    settings = production_settings(auto_create_tables=True)

    with pytest.raises(ValueError, match="AUTO_CREATE_TABLES"):
        settings.validate_runtime()


def test_production_rejects_debug_auth():
    settings = production_settings(debug_auth_enabled=True)

    with pytest.raises(ValueError, match="DEBUG_AUTH_ENABLED"):
        settings.validate_runtime()


def test_production_rejects_mock_providers():
    settings = production_settings(use_mock_providers=True)

    with pytest.raises(ValueError, match="USE_MOCK_PROVIDERS"):
        settings.validate_runtime()


def test_production_requires_secure_cookie():
    settings = production_settings(session_cookie_secure=False)

    with pytest.raises(ValueError, match="SESSION_COOKIE_SECURE"):
        settings.validate_runtime()


@pytest.mark.parametrize(
    ("overrides", "missing_name"),
    [
        ({"google_client_id": None}, "GOOGLE_CLIENT_ID"),
        ({"google_client_secret": None}, "GOOGLE_CLIENT_SECRET"),
        ({"onemap_token": None, "onemap_email": None, "onemap_password": None}, "ONEMAP"),
    ],
)
def test_production_requires_external_provider_configuration(overrides, missing_name):
    settings = production_settings(**overrides)

    with pytest.raises(ValueError, match=missing_name):
        settings.validate_runtime()


def test_development_allows_local_defaults():
    Settings(_env_file=None).validate_runtime()


def test_reference_seed_is_idempotent_and_does_not_create_demo_venues():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        first = seed_reference_data(session)
        second = seed_reference_data(session)
        names = {item.name for item in session.exec(select(ActivityType)).all()}

        assert first == 6
        assert second == 0
        assert names == {
            "Badminton",
            "Football",
            "Basketball",
            "Picnic",
            "Board Games",
            "Bowling",
        }
        assert list(session.exec(select(Venue)).all()) == []


def test_ready_returns_200_when_database_responds(monkeypatch):
    monkeypatch.setattr(main_module, "database_is_ready", lambda: True)

    with TestClient(main_module.app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_503_when_database_fails(monkeypatch):
    monkeypatch.setattr(main_module, "database_is_ready", lambda: False)

    with TestClient(main_module.app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "EXTERNAL_SERVICE_UNAVAILABLE"


def static_test_client(tmp_path) -> TestClient:
    from app.static_site import mount_static_site

    static_dir = tmp_path / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<html><body>pilot shell</body></html>")
    (assets_dir / "app.js").write_text("window.pilot = true")
    application = FastAPI()

    @application.get("/api/ping")
    def ping():
        return {"status": "ok"}

    mount_static_site(application, static_dir)
    return TestClient(application)


def test_spa_fallback_serves_deep_link(tmp_path):
    with static_test_client(tmp_path) as client:
        response = client.get("/sessions/example")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "pilot shell" in response.text


def test_static_asset_is_served(tmp_path):
    with static_test_client(tmp_path) as client:
        response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert response.text == "window.pilot = true"


def test_unknown_api_route_remains_json_404(tmp_path):
    with static_test_client(tmp_path) as client:
        response = client.get("/api/not-real")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Not Found"}
