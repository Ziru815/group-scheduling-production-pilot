"""Offline stand-ins for the external providers, for development and tests.

They implement the same ports as the real adapters, so ApplicationStartup can
swap them in (for example with ``USE_MOCK_PROVIDERS=1``) and the rest of the
backend runs with no network access and no OneMap credentials.

MockRouter estimates a journey from straight-line distance with a detour
factor and a per-mode speed and overhead. The numbers are rough Singapore
figures chosen to look plausible in demos; they are not a substitute for
routing and must never feed real scoring (NFR-8).
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.adapters.ports import AddressMatch, GeocodeResult, RouteResult
from app.recommender.geo import haversine_km
from app.recommender.types import (
    Coordinates,
    GeocodeStatus,
    RoutingStatus,
    TransportMode,
    VenueCategory,
    VenueInput,
)


@dataclass(frozen=True)
class ModeProfile:
    speed_kmh: float
    overhead_minutes: float  # waiting, parking, walking to the stop


DEFAULT_PROFILES: Mapping[TransportMode, ModeProfile] = {
    TransportMode.WALK: ModeProfile(speed_kmh=4.8, overhead_minutes=0),
    TransportMode.DRIVE: ModeProfile(speed_kmh=35.0, overhead_minutes=6),
    TransportMode.PUBLIC_TRANSPORT: ModeProfile(speed_kmh=20.0, overhead_minutes=10),
}

DETOUR_FACTOR = 1.3  # roads and rail lines are longer than the straight line


class MockRouter:
    """Deterministic Router. Counts calls so tests can check the routing budget."""

    def __init__(
        self,
        profiles: Mapping[TransportMode, ModeProfile] = DEFAULT_PROFILES,
        *,
        unavailable_origins: Iterable[Coordinates] = (),
    ) -> None:
        self.profiles = dict(profiles)
        self.unavailable_origins = set(unavailable_origins)
        self.calls: list[tuple[Coordinates, Coordinates, TransportMode, datetime]] = []

    async def route(
        self,
        origin: Coordinates,
        destination: Coordinates,
        mode: TransportMode,
        depart_at: datetime,
    ) -> RouteResult:
        self.calls.append((origin, destination, mode, depart_at))
        if origin in self.unavailable_origins:
            return RouteResult(status=RoutingStatus.UNAVAILABLE, detail="mock: provider down")
        profile = self.profiles[mode]
        km = haversine_km(origin, destination) * DETOUR_FACTOR
        minutes = math.ceil(km / profile.speed_kmh * 60 + profile.overhead_minutes)
        return RouteResult(status=RoutingStatus.AVAILABLE, minutes=minutes, distance_m=km * 1000)


class MockGeocoder:
    """Looks queries up in a fixed table (case-insensitive, by label or postal code)."""

    def __init__(self, places: Iterable[AddressMatch]) -> None:
        self._places = list(places)

    async def geocode(self, query: str) -> GeocodeResult:
        q = query.strip().lower()
        if not q:
            return GeocodeResult(status=GeocodeStatus.INVALID, detail="empty query")
        matches = tuple(
            p
            for p in self._places
            if q == (p.postal_code or "").lower() or q in p.label.lower()
        )
        if not matches:
            return GeocodeResult(status=GeocodeStatus.INVALID, detail="no match")
        return GeocodeResult(status=GeocodeStatus.VALID, matches=matches)


class JsonVenueSource:
    """VenueSource backed by a JSON file in the format of ``mock_data/venues.json``."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    async def list_venues(self) -> list[VenueInput]:
        return load_venues(self.path)


def load_venues(path: str | Path) -> list[VenueInput]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [venue_from_dict(v) for v in data["venues"]]


def venue_from_dict(v: Mapping) -> VenueInput:
    return VenueInput(
        venue_id=v["venue_id"],
        name=v["name"],
        category=VenueCategory(v["category"]),
        location=Coordinates(lat=v["lat"], lng=v["lng"]),
        supported_activity_type_ids=frozenset(v["activity_types"]),
        address=v.get("address", ""),
        min_group_size=v.get("min_group_size"),
        optimal_group_size=v.get("optimal_group_size"),
        advance_booking_lead_minutes=v.get("advance_booking_lead_minutes"),
    )
