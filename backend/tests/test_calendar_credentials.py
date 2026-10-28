from base64 import urlsafe_b64encode
from importlib import import_module
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import CalendarEvent, UserAccount


FERNET_KEY = urlsafe_b64encode(b"calendar-credential-test-key-32b"[:32]).decode()
MIGRATION = Path(__file__).parents[1] / "migrations" / "versions" / "c9d4e5f6a7b8_add_calendar_credentials.py"


def _vault(db: Session):
    module = import_module("app.services.calendar_credentials")
    return module.CalendarCredentialVault(db, FERNET_KEY)


def _account(db: Session) -> UserAccount:
    account = UserAccount(
        email="calendar-owner@example.com",
        display_name="Calendar Owner",
        provider_user_id="google-calendar-owner",
    )
    db.add(account)
    db.commit()
    return account


def test_vault_encrypts_refresh_token_and_round_trips_without_plaintext(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'vault.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as db:
        account = _account(db)
        vault = _vault(db)
        stored = vault.store(
            user_account_id=account.account_id,
            refresh_token="refresh-token-must-stay-secret",
            granted_scopes=["scope.z", "scope.a", "scope.z"],
            google_calendar_id="group-scheduler@example.com",
        )
        db.commit()

        assert stored.encrypted_refresh_token != "refresh-token-must-stay-secret"
        assert "refresh-token-must-stay-secret" not in stored.encrypted_refresh_token
        assert stored.granted_scopes == "scope.a scope.z"
        assert vault.refresh_token(vault.reference(stored.credential_id)) == "refresh-token-must-stay-secret"


def test_store_upserts_one_credential_per_account_and_disconnect_preserves_calendar_id(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'upsert.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as db:
        account = _account(db)
        vault = _vault(db)
        first = vault.store(account.account_id, "first-token", ["scope.a"], "calendar-id")
        second = vault.store(account.account_id, "second-token", ["scope.b"], None)
        vault.disconnect(account.account_id)
        db.commit()

        module = import_module("app.models")
        rows = list(db.exec(select(module.CalendarCredential)).all())
        assert len(rows) == 1
        assert first.credential_id == second.credential_id == rows[0].credential_id
        assert rows[0].encrypted_refresh_token is None
        assert rows[0].google_calendar_id == "calendar-id"
        assert rows[0].status.value == "DISCONNECTED"
        assert rows[0].revoked_at is not None


def test_same_account_reconnect_without_refresh_token_preserves_existing_secret(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'reconnect.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as db:
        account = _account(db)
        vault = _vault(db)
        first = vault.store(account.account_id, "durable-refresh-token", ["scope.a"], "calendar-id")
        second = vault.store(account.account_id, None, ["scope.a", "scope.b"], None)
        db.commit()

        assert second.credential_id == first.credential_id
        assert vault.refresh_token(vault.reference(second.credential_id)) == "durable-refresh-token"
        assert second.granted_scopes == "scope.a scope.b"


def test_vault_rejects_bad_key_and_malformed_or_unknown_references(tmp_path):
    module = import_module("app.services.calendar_credentials")
    engine = create_engine(f"sqlite:///{tmp_path / 'invalid.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as db:
        with pytest.raises(module.CalendarCredentialError, match="credential key"):
            module.CalendarCredentialVault(db, "not-a-fernet-key")

        vault = _vault(db)
        with pytest.raises(module.CalendarCredentialError, match="reference"):
            vault.refresh_token("plain-token")
        with pytest.raises(module.CalendarCredentialError, match="not found"):
            vault.refresh_token("db:00000000-0000-0000-0000-000000000000")


def test_calendar_schema_supports_user_credential_and_confirmed_event_without_candidate():
    credential_table = SQLModel.metadata.tables["calendar_credentials"]
    event_table = SQLModel.metadata.tables[CalendarEvent.__tablename__]

    assert credential_table.c.user_account_id.unique is True
    assert event_table.c.candidate_timeslot_id.nullable is True
    assert any(
        constraint.name == "uq_calendar_event_owned_slot_type"
        for constraint in event_table.constraints
    )


def test_additive_migration_creates_vault_and_nullable_candidate_reference():
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'op.create_table("calendar_credentials"' in source
    assert 'op.alter_column("candidate_timeslot_id", nullable=True)' in source
    assert "uq_calendar_event_owned_slot_type" in source

