from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.core.database import get_db
from app.core.security import issue_app_token
from app.main import app
from app.models import (
    ActivityType,
    Participant,
    SchedulingSession,
    SupportStatus,
    UserAccount,
    Venue,
    VenueActivity,
    VenueCategory,
    VenueVerificationStatus,
)
from app.services.activity_availability import (
    ActivityUnavailableError,
    require_creatable_activity,
    require_mutable_activity,
    supported_activity_categories,
)
from app.services.web_contract_service import invitation_preview, session_detail


def _engine():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return engine


def _venue(name: str, *, verified: bool = True, active: bool = True) -> Venue:
    return Venue(
        name=name,
        category=VenueCategory.PARK,
        address=f"{name}, Singapore",
        latitude=1.30,
        longitude=103.80,
        data_source="DATA_GOV_SG_NPARKS_PARKS",
        source_key=name.lower().replace(" ", "-"),
        is_active=active,
        verification_status=(
            VenueVerificationStatus.VERIFIED_PUBLIC
            if verified
            else VenueVerificationStatus.UNVERIFIED
        ),
    )


def _seed_catalog(db: Session):
    activities = {
        name: ActivityType(category=category, name=name, is_active=active)
        for name, category, active in [
            ("Badminton", "SPORTS", True),
            ("Basketball", "SPORTS", True),
            ("Football", "SPORTS", True),
            ("Picnic", "SOCIAL", True),
            ("Board Games", "LEISURE", True),
            ("Bowling", "LEISURE", True),
            ("Retired", "LEISURE", False),
        ]
    }
    db.add_all(activities.values())
    db.flush()
    for name in ("Badminton", "Basketball", "Football", "Picnic"):
        venue = _venue(f"{name} verified")
        db.add(venue)
        db.flush()
        db.add(
            VenueActivity(
                venue_id=venue.venue_id,
                activity_type_id=activities[name].activity_type_id,
                support_status=SupportStatus.SUPPORTED,
            )
        )
    unverified = _venue("Board Games unverified", verified=False)
    inactive = _venue("Bowling inactive", active=False)
    db.add_all([unverified, inactive])
    db.flush()
    db.add_all(
        [
            VenueActivity(
                venue_id=unverified.venue_id,
                activity_type_id=activities["Board Games"].activity_type_id,
                support_status=SupportStatus.SUPPORTED,
            ),
            VenueActivity(
                venue_id=inactive.venue_id,
                activity_type_id=activities["Bowling"].activity_type_id,
                support_status=SupportStatus.SUPPORTED,
            ),
        ]
    )
    db.commit()
    return activities


def _names(groups: list[dict]) -> set[str]:
    return {item["name"] for group in groups for item in group["types"]}


def test_production_catalogue_contains_only_active_activities_with_verified_support():
    with Session(_engine()) as db:
        _seed_catalog(db)

        assert _names(supported_activity_categories(db, require_verified=True)) == {
            "Badminton",
            "Basketball",
            "Football",
            "Picnic",
        }


def test_development_catalogue_preserves_all_active_reference_activities():
    with Session(_engine()) as db:
        _seed_catalog(db)

        assert _names(supported_activity_categories(db, require_verified=False)) == {
            "Badminton",
            "Basketball",
            "Football",
            "Picnic",
            "Board Games",
            "Bowling",
        }


def test_create_and_mutation_policy_return_distinct_contract_errors():
    with Session(_engine()) as db:
        activities = _seed_catalog(db)
        unsupported = activities["Board Games"]
        start = datetime.now(timezone.utc) + timedelta(days=2)
        item = SchedulingSession(
            name="Historical unsupported session",
            activity_type_id=unsupported.activity_type_id,
            date_range_start=start,
            date_range_end=start + timedelta(hours=2),
            response_deadline=start - timedelta(days=1),
        )

        with pytest.raises(ActivityUnavailableError) as create_error:
            require_creatable_activity(
                db,
                unsupported.activity_type_id,
                require_verified=True,
            )
        assert create_error.value.field_name == "activityTypeId"

        with pytest.raises(ActivityUnavailableError) as mutation_error:
            require_mutable_activity(db, item, require_verified=True)
        assert mutation_error.value.field_name is None


def test_existing_unsupported_session_and_invitation_are_still_readable(monkeypatch):
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "use_mock_providers", False)
    with Session(_engine()) as db:
        activities = _seed_catalog(db)
        user = UserAccount(
            email="organiser@example.com",
            display_name="Organiser",
            provider_user_id="organiser-subject",
        )
        start = datetime.now(timezone.utc) + timedelta(days=2)
        item = SchedulingSession(
            name="Readable historical session",
            activity_type_id=activities["Board Games"].activity_type_id,
            date_range_start=start,
            date_range_end=start + timedelta(hours=2),
            response_deadline=start - timedelta(days=1),
            invitation_token="historical-token",
        )
        db.add_all([user, item])
        db.flush()
        organiser = Participant(
            user_account_id=user.account_id,
            session_id=item.session_id,
            display_name=user.display_name,
            role="ORGANISER",
        )
        db.add(organiser)
        db.flush()
        item.organiser_participant_id = organiser.participant_id
        db.add(item)
        db.commit()

        assert session_detail(db, user, item)["activitySupported"] is False
        assert invitation_preview(db, user, item.invitation_token)["activitySupported"] is False


def test_both_api_contracts_reject_stale_client_creation_with_field_error(monkeypatch, tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'activity-create.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        activities = _seed_catalog(db)
        user = UserAccount(
            email="creator@example.com",
            display_name="Creator",
            provider_user_id="creator-subject",
        )
        db.add(user)
        db.commit()
        activity_id = str(activities["Board Games"].activity_type_id)
        token = issue_app_token(user.account_id)

    def override_db():
        with Session(engine) as db:
            yield db

    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "use_mock_providers", False)
    app.dependency_overrides[get_db] = override_db
    headers = {"Authorization": f"Bearer {token}"}
    try:
        client = TestClient(app)
        web = client.post(
            "/api/sessions",
            headers=headers,
            json={
                "name": "Unsupported web create",
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
        legacy = client.post(
            "/api/v1/sessions",
            headers=headers,
            json={
                "name": "Unsupported legacy create",
                "activity_type_id": activity_id,
                "date_range_start": "2030-11-07T09:00:00+08:00",
                "date_range_end": "2030-11-07T13:00:00+08:00",
                "response_deadline": "2030-11-01T18:00:00+08:00",
            },
        )
    finally:
        app.dependency_overrides.clear()

    for response in (web, legacy):
        assert response.status_code == 422
        assert response.json() == {
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Please fix the highlighted fields.",
                "fields": {
                    "activityTypeId": "This activity is not currently supported by a verified venue."
                },
            }
        }


def test_existing_unsupported_session_is_readable_and_cancelable_but_not_mutable(monkeypatch, tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'activity-mutation.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        activities = _seed_catalog(db)
        organiser = UserAccount(
            email="history@example.com",
            display_name="History Organiser",
            provider_user_id="history-subject",
        )
        joiner = UserAccount(
            email="joiner@example.com",
            display_name="Joiner",
            provider_user_id="joiner-subject",
        )
        start = datetime.now(timezone.utc) + timedelta(days=2)
        item = SchedulingSession(
            name="Historical board games",
            activity_type_id=activities["Board Games"].activity_type_id,
            date_range_start=start,
            date_range_end=start + timedelta(hours=2),
            response_deadline=start - timedelta(days=1),
            invitation_token="unsupported-session-token",
        )
        db.add_all([organiser, joiner, item])
        db.flush()
        membership = Participant(
            user_account_id=organiser.account_id,
            session_id=item.session_id,
            display_name=organiser.display_name,
            role="ORGANISER",
        )
        db.add(membership)
        db.flush()
        item.organiser_participant_id = membership.participant_id
        db.add(item)
        db.commit()
        session_id = item.session_id
        organiser_token = issue_app_token(organiser.account_id)
        joiner_token = issue_app_token(joiner.account_id)

    def override_db():
        with Session(engine) as db:
            yield db

    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "use_mock_providers", False)
    app.dependency_overrides[get_db] = override_db
    organiser_headers = {"Authorization": f"Bearer {organiser_token}"}
    joiner_headers = {"Authorization": f"Bearer {joiner_token}"}
    try:
        client = TestClient(app)
        readable = client.get(f"/api/sessions/{session_id}", headers=organiser_headers)
        listed = client.get("/api/v1/sessions", headers=organiser_headers)
        preview = client.post(
            "/api/invitations/resolve",
            headers=joiner_headers,
            json={"token": "unsupported-session-token"},
        )
        join = client.post(
            "/api/invitations/join",
            headers=joiner_headers,
            json={"token": "unsupported-session-token"},
        )
        update = client.patch(
            f"/api/v1/sessions/{session_id}",
            headers=organiser_headers,
            json={"name": "Should not change"},
        )
        save_response_result = client.put(
            f"/api/sessions/{session_id}/my-response",
            headers=organiser_headers,
            json={
                "intervals": [],
                "calendarAssisted": False,
                "transportMode": "PUBLIC_TRANSPORT",
                "confirmUnavailable": True,
            },
        )
        withdraw_response_result = client.post(
            f"/api/sessions/{session_id}/my-response/withdraw",
            headers=organiser_headers,
        )
        legacy_response_result = client.put(
            f"/api/v1/sessions/{session_id}/availability/me",
            headers=organiser_headers,
            json={
                "location_input_type": "ADDRESS",
                "location_input": "Historical address",
                "transport_mode": "PUBLIC_TRANSPORT",
                "intervals": [],
            },
        )
        generate_result = client.post(
            f"/api/sessions/{session_id}/recommendations",
            headers=organiser_headers,
        )
        legacy_generate_result = client.post(
            f"/api/v1/sessions/{session_id}/recommendations/generate",
            headers=organiser_headers,
        )
        confirm_result = client.post(
            f"/api/sessions/{session_id}/confirm",
            headers=organiser_headers,
            json={"combinationId": "00000000-0000-0000-0000-000000000001"},
        )
        calendar_retry_result = client.post(
            f"/api/sessions/{session_id}/calendar-sync",
            headers=organiser_headers,
        )
        cancel = client.post(
            f"/api/sessions/{session_id}/cancel",
            headers=organiser_headers,
        )
    finally:
        app.dependency_overrides.clear()

    assert readable.status_code == 200
    assert readable.json()["activitySupported"] is False
    assert listed.status_code == 200
    assert preview.status_code == 200
    assert preview.json()["activitySupported"] is False
    for response in (
        join,
        update,
        save_response_result,
        withdraw_response_result,
        legacy_response_result,
        generate_result,
        legacy_generate_result,
        confirm_result,
        calendar_retry_result,
    ):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ACTIVITY_UNSUPPORTED"
    assert cancel.status_code == 200
