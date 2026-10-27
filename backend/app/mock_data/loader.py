"""Builds engine inputs from the JSON files in this folder."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.adapters.mock import load_venues
from app.adapters.ports import AddressMatch
from app.recommender.types import (
    Coordinates,
    GeocodeStatus,
    Interval,
    IntervalType,
    ParticipantInput,
    RecommendationRequest,
    RecordStatus,
    SessionInput,
    TransportMode,
    TravelObjective,
)

MOCK_DIR = Path(__file__).resolve().parent
VENUES_PATH = MOCK_DIR / "venues.json"
SAMPLE_SESSION_PATH = MOCK_DIR / "sample_session.json"


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def load_places(path: str | Path = SAMPLE_SESSION_PATH) -> list[AddressMatch]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        AddressMatch(
            label=p["label"],
            postal_code=p.get("postal_code"),
            coordinates=Coordinates(lat=p["lat"], lng=p["lng"]),
        )
        for p in data["places"]
    ]


def _participant(raw: dict[str, Any], places: dict[str, AddressMatch]) -> ParticipantInput:
    status = raw.get("record_status")
    intervals = tuple(
        Interval(_dt(s), _dt(e), IntervalType.AVAILABLE) for s, e in raw.get("intervals", [])
    ) + tuple(Interval(_dt(s), _dt(e), IntervalType.BUSY) for s, e in raw.get("busy", []))
    place = places.get(raw.get("place", ""))
    return ParticipantInput(
        participant_id=raw["participant_id"],
        display_name=raw["display_name"],
        record_status=RecordStatus(status) if status else None,
        intervals=intervals,
        location=place.coordinates if place else None,
        geocode_status=GeocodeStatus.VALID if place else GeocodeStatus.PENDING,
        transport_mode=TransportMode(raw.get("transport_mode", "PUBLIC_TRANSPORT")),
    )


def load_sample_request(
    session_path: str | Path = SAMPLE_SESSION_PATH,
    venues_path: str | Path = VENUES_PATH,
) -> RecommendationRequest:
    data = json.loads(Path(session_path).read_text(encoding="utf-8"))
    s = data["session"]
    session = SessionInput(
        session_id=s["session_id"],
        activity_type_id=s["activity_type_id"],
        date_range_start=_dt(s["date_range_start"]),
        date_range_end=_dt(s["date_range_end"]),
        duration_minutes=s["duration_minutes"],
        minimum_attendee_threshold=s.get("minimum_attendee_threshold"),
        travel_objective=TravelObjective(s.get("travel_objective", "MIN_TOTAL")),
        attendance_weight_percent=s.get("attendance_weight_percent", 50),
        timezone=s.get("timezone", "Asia/Singapore"),
    )
    places = {p.label: p for p in load_places(session_path)}
    participants = tuple(_participant(p, places) for p in data["participants"])
    return RecommendationRequest(
        session=session,
        participants=participants,
        venues=tuple(load_venues(venues_path)),
        now=_dt(data["now"]),
    )
