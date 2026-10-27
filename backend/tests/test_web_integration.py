from sqlmodel import Session, SQLModel, create_engine
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models import ActivityType, SupportStatus, Venue, VenueActivity, VenueCategory


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
                data_source="DEMO",
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
                VenueActivity(venue_id=venue.venue_id, activity_type_id=activity.activity_type_id, support_status=SupportStatus.SUPPORTED)
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
    settings.debug_auth_enabled = True
    settings.use_mock_providers = True
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

            # Editing a response invalidates the first snapshot. Regeneration
            # must replace identical Candidate Timeslots instead of violating
            # their unique (Session, start, end) constraint.
            assert client.put(f"/api/sessions/{session_id}/my-response", json=response_payload).status_code == 200
            regenerated = client.post(f"/api/sessions/{session_id}/recommendations")
            assert regenerated.status_code == 200, regenerated.text
            assert regenerated.json()["combinations"]
            combination_id = regenerated.json()["combinations"][0]["combinationId"]

            confirmed = client.post(f"/api/sessions/{session_id}/confirm", json={"combinationId": combination_id})
            assert confirmed.status_code == 200, confirmed.text
            assert confirmed.json()["status"] == "CONFIRMED"
            assert len(confirmed.json()["confirmed"]["attendees"]) == 2
    finally:
        settings.debug_auth_enabled = original_debug
        settings.use_mock_providers = original_mock
        app.dependency_overrides.clear()

