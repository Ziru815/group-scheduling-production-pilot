from app.core.config import Settings


def test_debug_auth_is_disabled_by_default():
    assert Settings(_env_file=None).debug_auth_enabled is False


def test_production_secret_is_environment_configurable(monkeypatch):
    monkeypatch.setenv("APP_SESSION_SECRET", "test-secret")
    assert Settings(_env_file=None).app_session_secret == "test-secret"

