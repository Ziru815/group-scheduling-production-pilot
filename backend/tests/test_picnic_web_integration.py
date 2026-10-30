import json
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.controllers import web_api
from app.adapters.mock import MockRouter
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.recommender.types import Coordinates
from app.services import integrated_recommendation_service
from app.models import (
    ActivityType,
    CalendarConnection,
    Combination,
    ConnectionStatus,
    Participant,
    SupportStatus,
    Venue,
    VenueActivity,
    VenueCategory,
    VenueVerificationStatus,
)


class RecordingCalendarAdapter:
    def __init__(self):
        self.upserts = []
        self.deleted = []

    async def upsert_event(self, credential_reference, idempotency_key, event):
        self.upserts.append((credential_reference, idempotency_key, event))
        return sha256(idempotency_key.encode()).hexdigest()[:24]

    async def delete_event(self, credential_reference, provider_event_id):
        self.deleted.append((credential_reference, provider_event_id))


def _seed_picnic_catalog(engine):
    with Session(engine) as db:
        activity = ActivityType(category="SOCIAL", name="Picnic")
        db.add(activity)
        db.flush()
        parks = [
            Venue(
                name="Bishan-Ang Mo Kio Park",
                category=VenueCategory.PARK,
                address="1384 Ang Mo Kio Avenue 1, Singapore 569931",
                meeting_point="Pond Gardens entrance",
                latitude=1.3621,
                longitude=103.8464,
                data_source="DATA_GOV_SG_NPARKS_PARKS",
                source_key="picnic-bishan-amk",
                last_synced_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
                verification_status=VenueVerificationStatus.VERIFIED_PUBLIC,
                minimum_group_size=99,
                optimal_group_size=99,
                advance_booking_lead_minutes=999999,
            ),
            Venue(
                name="Toa Payoh Town Park",
                category=VenueCategory.PARK,
                address="Lorong 6 Toa Payoh, Singapore 319385",
                meeting_point="Observation tower entrance",
                latitude=1.3302,
                longitude=103.8505,
                data_source="DATA_GOV_SG_NPARKS_PARKS",
                source_key="picnic-toa-payoh",
                last_synced_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
                verification_status=VenueVerificationStatus.VERIFIED_PUBLIC,
                minimum_group_size=99,
                optimal_group_size=99,
                advance_booking_lead_minutes=999999,
            ),
            Venue(
                name="Kallang Riverside Park",
                category=VenueCategory.PARK,
                address="5 Stadium Road, Singapore 397732",
                meeting_point="Stadium Road entrance",
                latitude=1.3074,
                longitude=103.8680,
                data_source="DATA_GOV_SG_NPARKS_PARKS",
                source_key="picnic-kallang-riverside",
                last_synced_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
                verification_status=VenueVerificationStatus.VERIFIED_PUBLIC,
                minimum_group_size=99,
                optimal_group_size=99,
                advance_booking_lead_minutes=999999,
            ),
        ]
        db.add_all(parks)
        db.flush()
        db.add_all(
            [
                VenueActivity(
                    venue_id=park.venue_id,
                    activity_type_id=activity.activity_type_id,
                    support_status=SupportStatus.SUPPORTED,
                )
                for park in parks
            ]
        )
        db.commit()
        return str(activity.activity_type_id)


def test_three_origin_picnic_journey_is_stable_private_and_calendar_ready(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'picnic-web.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    activity_id = _seed_picnic_catalog(engine)

    def override_db():
        with Session(engine) as db:
            yield db

    calendar = RecordingCalendarAdapter()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[web_api.get_google_calendar_adapter] = lambda: calendar
    original = {
        "debug_auth_enabled": settings.debug_auth_enabled,
        "use_mock_providers": settings.use_mock_providers,
        "google_calendar_enabled": settings.google_calendar_enabled,
    }
    settings.debug_auth_enabled = True
    settings.use_mock_providers = True
    settings.google_calendar_enabled = False
    try:
        client = TestClient(app)
        assert client.post("/api/dev/sign-in", json={"userId": "demo-organiser"}).status_code == 204
        created = client.post(
            "/api/sessions",
            json={
                "name": "Three-origin picnic",
                "activityTypeId": activity_id,
                "startDate": "2030-11-07",
                "endDate": "2030-11-07",
                "dailyStartTime": "09:00",
                "dailyEndTime": "13:00",
                "timezone": "Asia/Singapore",
                "durationMinutes": 60,
                "responseDeadline": "2030-11-01T18:00:00+08:00",
                "minimumAttendees": 3,
            },
        )
        assert created.status_code == 201, created.text
        session_id = created.json()["session"]["id"]
        invitation_token = created.json()["invitationUrl"].rsplit("/", 1)[-1]

        origins = [
            ("demo-organiser", "Bishan"),
            ("demo-amirah", "Tampines"),
            ("demo-wei-jie", "Jurong East"),
        ]
        for index, (persona, query) in enumerate(origins):
            assert client.post("/api/dev/sign-in", json={"userId": persona}).status_code == 204
            if index:
                joined = client.post("/api/invitations/join", json={"token": invitation_token})
                assert joined.status_code == 200, joined.text
            place = client.post("/api/locations/search", json={"query": query}).json()["candidates"][0]
            saved = client.put(
                f"/api/sessions/{session_id}/my-response",
                json={
                    "intervals": [
                        {
                            "start": "2030-11-07T09:00:00+08:00",
                            "end": "2030-11-07T12:00:00+08:00",
                        }
                    ],
                    "calendarAssisted": False,
                    "transportMode": "PUBLIC_TRANSPORT",
                    "location": {
                        "inputType": "ADDRESS",
                        "input": query,
                        "candidateId": place["candidateId"],
                    },
                },
            )
            assert saved.status_code == 200, saved.text

        assert client.post("/api/dev/sign-in", json={"userId": "demo-organiser"}).status_code == 204
        legacy = client.post(
            f"/api/v1/sessions/{session_id}/recommendations/generate",
            headers={
                "Authorization": f"Bearer {client.cookies.get(settings.session_cookie_name)}"
            },
        )
        assert legacy.status_code == 200, legacy.text
        with Session(engine) as db:
            legacy_combinations = list(
                db.exec(
                    select(Combination).where(
                        Combination.session_id == UUID(session_id)
                    )
                ).all()
            )
            assert legacy_combinations
            assert all(row.exclusion_reason != "MINIMUM_GROUP_SIZE" for row in legacy_combinations)
            assert all(row.exclusion_reason != "INSUFFICIENT_BOOKING_LEAD" for row in legacy_combinations)

        normal_provider = integrated_recommendation_service._provider
        unavailable_origins = [
            Coordinates(1.3510, 103.8485),
            Coordinates(1.3534, 103.9452),
            Coordinates(1.3332, 103.7423),
        ]
        monkeypatch.setattr(
            integrated_recommendation_service,
            "_provider",
            lambda: MockRouter(unavailable_origins=unavailable_origins),
        )
        unavailable = client.post(f"/api/sessions/{session_id}/recommendations")
        assert unavailable.status_code == 200, unavailable.text
        unavailable_options = unavailable.json()["combinations"]
        assert unavailable_options
        assert all(option["feasibilityStatus"] == "DATA_UNAVAILABLE" for option in unavailable_options)
        assert all(
            attendee["travelMinutes"] is None
            for option in unavailable_options
            for attendee in option["attendees"]
        )
        cannot_confirm = client.post(
            f"/api/sessions/{session_id}/confirm",
            json={"combinationId": unavailable_options[0]["combinationId"]},
        )
        assert cannot_confirm.status_code == 409
        assert cannot_confirm.json()["error"]["code"] == "COMBINATION_NOT_FEASIBLE"
        monkeypatch.setattr(integrated_recommendation_service, "_provider", normal_provider)

        first = client.post(f"/api/sessions/{session_id}/recommendations")
        second = client.post(f"/api/sessions/{session_id}/recommendations")
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        first_options = first.json()["combinations"]
        second_options = second.json()["combinations"]
        assert len({option["venue"]["name"] for option in first_options}) >= 2
        assert [
            (option["rank"], option["venue"]["name"], option["start"])
            for option in first_options
        ] == [
            (option["rank"], option["venue"]["name"], option["start"])
            for option in second_options
        ]
        assert all(option["feasibilityStatus"] == "FEASIBLE" for option in second_options)
        assert all(
            set(attendee) <= {
                "participantId",
                "displayName",
                "transportMode",
                "travelMinutes",
                "routingStatus",
            }
            for option in second_options
            for attendee in option["attendees"]
        )
        rendered = json.dumps(second_options)
        assert "579827" not in rendered
        assert "529538" not in rendered
        assert "609690" not in rendered

        with Session(engine) as db:
            organiser = db.exec(
                select(Participant).where(
                    Participant.session_id == UUID(session_id),
                    Participant.role == "ORGANISER",
                )
            ).one()
            db.add(
                CalendarConnection(
                    participant_id=organiser.participant_id,
                    connection_status=ConnectionStatus.CONNECTED,
                    credential_reference="db:11111111-1111-1111-1111-111111111111",
                    granted_scopes="calendar.freebusy calendar.app.created",
                )
            )
            db.commit()

        settings.google_calendar_enabled = True
        chosen = second_options[0]
        confirmed = client.post(
            f"/api/sessions/{session_id}/confirm",
            json={"combinationId": chosen["combinationId"]},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["confirmed"]["venue"]["meetingPoint"]
        opaque = [event for _, _, event in calendar.upserts if event.transparency == "opaque"]
        assert len(opaque) == 1
        venue = confirmed.json()["confirmed"]["venue"]
        assert opaque[0].location == f'{venue["meetingPoint"]}, {venue["address"]}'
        assert all(query not in opaque[0].location for _, query in origins)
    finally:
        app.dependency_overrides.clear()
        settings.debug_auth_enabled = original["debug_auth_enabled"]
        settings.use_mock_providers = original["use_mock_providers"]
        settings.google_calendar_enabled = original["google_calendar_enabled"]
