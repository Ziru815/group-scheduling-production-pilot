import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.config import Settings


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
