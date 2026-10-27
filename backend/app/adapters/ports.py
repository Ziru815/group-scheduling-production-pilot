from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.models.enums import TransportMode
from app.recommender.types import (
    Coordinates,
    GeocodeStatus,
    RoutingStatus,
    TransportMode as EngineTransportMode,
    VenueInput,
)


@dataclass(frozen=True)
class GeoPoint: latitude: float; longitude: float


@dataclass(frozen=True)
class RouteOutcome:
    duration_minutes: int | None
    provider: str
    error: str | None = None


class GeocoderPort(Protocol):
    async def geocode(self, location: str) -> GeoPoint | None: ...


class RoutingPort(Protocol):
    async def route(self, origin: GeoPoint, destination: GeoPoint, mode: TransportMode, when: datetime) -> RouteOutcome: ...


class CalendarPort(Protocol):
    async def free_busy(self, credential_reference: str, start: datetime, end: datetime): ...
    async def upsert_event(self, credential_reference: str, idempotency_key: str, title: str, start: datetime, end: datetime) -> str: ...
    async def delete_event(self, credential_reference: str, provider_event_id: str) -> None: ...


# The following provider-neutral contracts come from the standalone recommender.
# They intentionally coexist with the older persistence-layer ports above while
# the legacy /api/v1 surface remains available.  The integrated /api surface and
# the pure recommendation engine use these richer, explicit-status contracts.


@dataclass(frozen=True)
class AddressMatch:
    label: str
    postal_code: str | None
    coordinates: Coordinates


@dataclass(frozen=True)
class GeocodeResult:
    status: GeocodeStatus
    matches: tuple[AddressMatch, ...] = ()
    detail: str | None = None


@dataclass(frozen=True)
class RouteResult:
    status: RoutingStatus
    minutes: int | None = None
    distance_m: float | None = None
    detail: str | None = None
    raw_summary: dict = field(default_factory=dict, compare=False, repr=False)


@runtime_checkable
class Geocoder(Protocol):
    async def geocode(self, query: str) -> GeocodeResult: ...


@runtime_checkable
class Router(Protocol):
    async def route(
        self,
        origin: Coordinates,
        destination: Coordinates,
        mode: EngineTransportMode,
        depart_at: datetime,
    ) -> RouteResult: ...


@runtime_checkable
class VenueSource(Protocol):
    async def list_venues(self) -> list[VenueInput]: ...

