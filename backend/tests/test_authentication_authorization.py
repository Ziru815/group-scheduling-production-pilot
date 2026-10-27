import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from app.adapters.google_oauth import GoogleIdentity
from app.core.config import Settings
from app.models import UserAccount
from app.services.authentication_service import AuthenticationService


@pytest.fixture
def auth_db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def google_identity(**overrides):
    values = {
        "subject": "google-subject-123",
        "email": "person@example.com",
        "display_name": "Person Example",
        "next_path": "/sessions",
    }
    values.update(overrides)
    return GoogleIdentity(**values)


def test_debug_auth_is_disabled_by_default():
    assert Settings(_env_file=None).debug_auth_enabled is False


def test_production_secret_is_environment_configurable(monkeypatch):
    monkeypatch.setenv("APP_SESSION_SECRET", "test-secret")
    assert Settings(_env_file=None).app_session_secret == "test-secret"


def test_google_login_creates_account_by_subject(auth_db):
    response = AuthenticationService.google_identity_login(auth_db, google_identity())

    account = auth_db.exec(select(UserAccount)).one()
    assert response.account_id == account.account_id
    assert account.auth_provider == "GOOGLE"
    assert account.provider_user_id == "google-subject-123"
    assert account.email == "person@example.com"


def test_google_login_updates_display_name_for_same_subject(auth_db):
    account = UserAccount(
        email="old@example.com",
        display_name="Old Name",
        auth_provider="GOOGLE",
        provider_user_id="google-subject-123",
    )
    auth_db.add(account)
    auth_db.commit()

    AuthenticationService.google_identity_login(
        auth_db,
        google_identity(email="new@example.com", display_name="New Name"),
    )

    auth_db.refresh(account)
    assert account.email == "new@example.com"
    assert account.display_name == "New Name"


def test_google_login_rejects_existing_email_with_different_subject(auth_db):
    original = UserAccount(
        email="person@example.com",
        display_name="Original Account",
        auth_provider="GOOGLE",
        provider_user_id="original-google-subject",
    )
    auth_db.add(original)
    auth_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        AuthenticationService.google_identity_login(auth_db, google_identity())

    assert exc_info.value.status_code == 409
    auth_db.refresh(original)
    assert original.provider_user_id == "original-google-subject"
    assert original.display_name == "Original Account"

