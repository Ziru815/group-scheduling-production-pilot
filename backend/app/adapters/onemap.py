"""OneMap adapter: geocoding (FR-B3, UC-08) and routing (FR-D2, UC-10).

Implements the ``Geocoder`` and ``Router`` ports. OneMap is the Singapore
Land Authority's national map platform (SRS R1).

Endpoints used
  POST /api/auth/post/getToken             {email, password} -> access_token
  GET  /api/common/elastic/search          searchVal, returnGeom, getAddrDetails, pageNum
  GET  /api/public/routingsvc/route        start, end, routeType (+ pt parameters)

The routing call needs an access token, sent as ``Authorization: Bearer <token>``.
Tokens last about three days; this adapter caches one and fetches a new one
shortly before it expires. Credentials come from configuration (environment
variables), never from client code (SRS 3.4, 5.5).

Failure handling (NFR-3). Nothing here raises for provider problems:
  * network error, timeout, 429 or 5xx       -> UNAVAILABLE (provider unreachable)
  * search with no match                     -> GeocodeStatus.INVALID (FR-B3.1)
  * route answered but unusable / no route   -> RoutingStatus.ERROR

Response field names (``route_summary.total_time`` for walk/drive,
``plan.itineraries[].duration`` for public transport, both in seconds) follow
OneMap's documented responses. Re-check them against a live call when the
team first runs this with real credentials; the parsers are isolated in
``_parse_route_minutes`` for that reason.
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.adapters.ports import AddressMatch, GeocodeResult, RouteResult
from app.recommender.types import Coordinates, GeocodeStatus, RoutingStatus, TransportMode

ONEMAP_BASE_URL = "https://www.onemap.gov.sg"
SINGAPORE_TZ = ZoneInfo("Asia/Singapore")

_ROUTE_TYPE = {
    TransportMode.WALK: "walk",
    TransportMode.DRIVE: "drive",
    TransportMode.PUBLIC_TRANSPORT: "pt",
}

# Refresh the token this long before OneMap says it expires.
_TOKEN_REFRESH_MARGIN = timedelta(minutes=10)


class OneMapAdapter:
    """Async OneMap client. Create once at start-up and share (ApplicationStartup)."""

    def __init__(
        self,
        *,
        email: str | None = None,
        password: str | None = None,
        token: str | None = None,
        base_url: str = ONEMAP_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 10.0,
        pt_max_walk_distance_m: int = 1000,
        pt_num_itineraries: int = 3,
    ) -> None:
        self._email = email
        self._password = password
        self._static_token = token
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        self._token_lock = asyncio.Lock()
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._pt_max_walk = pt_max_walk_distance_m
        self._pt_itineraries = pt_num_itineraries

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> OneMapAdapter:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # Geocoding (FR-B3, UC-08)
    # ------------------------------------------------------------------

    async def geocode(self, query: str) -> GeocodeResult:
        query = query.strip()
        if not query:
            return GeocodeResult(status=GeocodeStatus.INVALID, detail="empty query")
        params = {"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": "1"}
        try:
            resp = await self._client.get(
                f"{self._base_url}/api/common/elastic/search", params=params
            )
        except httpx.HTTPError as exc:
            return GeocodeResult(status=GeocodeStatus.UNAVAILABLE, detail=type(exc).__name__)
        if _is_unavailable(resp):
            return GeocodeResult(status=GeocodeStatus.UNAVAILABLE, detail=f"HTTP {resp.status_code}")
        try:
            body = resp.json()
            matches = tuple(_parse_search_result(r) for r in body.get("results") or [])
        except (ValueError, KeyError, TypeError) as exc:
            return GeocodeResult(status=GeocodeStatus.UNAVAILABLE, detail=f"bad response: {exc!r}")
        if not matches:
            return GeocodeResult(status=GeocodeStatus.INVALID, detail="no match")
        return GeocodeResult(status=GeocodeStatus.VALID, matches=matches)

    # ------------------------------------------------------------------
    # Routing (FR-D2, UC-10)
    # ------------------------------------------------------------------

    async def route(
        self,
        origin: Coordinates,
        destination: Coordinates,
        mode: TransportMode,
        depart_at: datetime,
    ) -> RouteResult:
        token = await self._get_token()
        if token is None:
            return RouteResult(status=RoutingStatus.UNAVAILABLE, detail="no OneMap token")

        params: dict[str, str] = {
            "start": f"{origin.lat},{origin.lng}",
            "end": f"{destination.lat},{destination.lng}",
            "routeType": _ROUTE_TYPE[mode],
        }
        if mode is TransportMode.PUBLIC_TRANSPORT:
            local = _to_singapore_time(depart_at)
            params.update(
                {
                    "date": local.strftime("%m-%d-%Y"),
                    "time": local.strftime("%H:%M:%S"),
                    "mode": "TRANSIT",
                    "maxWalkDistance": str(self._pt_max_walk),
                    "numItineraries": str(self._pt_itineraries),
                }
            )
        try:
            resp = await self._client.get(
                f"{self._base_url}/api/public/routingsvc/route",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            return RouteResult(status=RoutingStatus.UNAVAILABLE, detail=type(exc).__name__)

        if resp.status_code in (401, 403) and self._static_token is None:
            self._token = None  # stale token: drop it so the next call fetches a new one
            return RouteResult(status=RoutingStatus.UNAVAILABLE, detail="OneMap rejected the token")
        if _is_unavailable(resp):
            return RouteResult(status=RoutingStatus.UNAVAILABLE, detail=f"HTTP {resp.status_code}")
        if resp.status_code >= 400:
            return RouteResult(status=RoutingStatus.ERROR, detail=f"HTTP {resp.status_code}")
        try:
            body = resp.json()
        except ValueError:
            return RouteResult(status=RoutingStatus.ERROR, detail="response was not JSON")

        minutes = _parse_route_minutes(body, mode)
        if minutes is None:
            return RouteResult(status=RoutingStatus.ERROR, detail="no route in response")
        return RouteResult(status=RoutingStatus.AVAILABLE, minutes=minutes)

    # ------------------------------------------------------------------
    # Token handling
    # ------------------------------------------------------------------

    async def _get_token(self) -> str | None:
        if self._static_token:
            return self._static_token
        if self._token and self._token_expires_at and _now() < self._token_expires_at:
            return self._token
        if not (self._email and self._password):
            return None
        async with self._token_lock:
            if self._token and self._token_expires_at and _now() < self._token_expires_at:
                return self._token  # another task refreshed it while we waited
            try:
                resp = await self._client.post(
                    f"{self._base_url}/api/auth/post/getToken",
                    json={"email": self._email, "password": self._password},
                )
                resp.raise_for_status()
                body = resp.json()
                token = body["access_token"]
            except (httpx.HTTPError, ValueError, KeyError):
                return None
            self._token = token
            self._token_expires_at = _parse_expiry(body.get("expiry_timestamp"))
            return token


# ----------------------------------------------------------------------
# Parsing helpers (kept separate so they can be checked against live responses)
# ----------------------------------------------------------------------


def _is_unavailable(resp: httpx.Response) -> bool:
    return resp.status_code == 429 or resp.status_code >= 500


def _parse_search_result(r: dict[str, Any]) -> AddressMatch:
    postal = r.get("POSTAL")
    if postal in (None, "", "NIL"):
        postal = None
    label = r.get("ADDRESS") or r.get("SEARCHVAL") or ""
    return AddressMatch(
        label=str(label),
        postal_code=postal,
        coordinates=Coordinates(lat=float(r["LATITUDE"]), lng=float(r["LONGITUDE"])),
    )


def _parse_route_minutes(body: dict[str, Any], mode: TransportMode) -> int | None:
    """Journey time in whole minutes, rounded up, or ``None`` if there is no route."""
    seconds: float | None = None
    if mode is TransportMode.PUBLIC_TRANSPORT:
        itineraries = (body.get("plan") or {}).get("itineraries") or []
        durations = [i.get("duration") for i in itineraries if isinstance(i.get("duration"), (int, float))]
        seconds = min(durations) if durations else None
    else:
        summary = body.get("route_summary") or {}
        total = summary.get("total_time")
        seconds = total if isinstance(total, (int, float)) else None
    if seconds is None or seconds < 0:
        return None
    return math.ceil(seconds / 60)


def _parse_expiry(value: Any) -> datetime:
    """OneMap returns the expiry as a Unix timestamp (string or number)."""
    try:
        expires = datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        expires = _now() + timedelta(hours=24)  # conservative fallback
    return expires - _TOKEN_REFRESH_MARGIN


def _to_singapore_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("depart_at must be timezone-aware")
    return value.astimezone(SINGAPORE_TZ)


def _now() -> datetime:
    return datetime.now(timezone.utc)
