"""OneMap adapter. Endpoint details are isolated here for easy provider replacement."""
from datetime import datetime
import math
import httpx

from app.adapters.ports import GeoPoint, RouteOutcome
from app.core.config import settings
from app.models.enums import TransportMode


class OneMapAdapter:
    def __init__(self, client: httpx.AsyncClient | None = None): self.client = client

    async def _request(self, path: str, params: dict):
        headers = {"Authorization": settings.onemap_token} if settings.onemap_token else {}
        if self.client: return await self.client.get(f"{settings.onemap_base_url}{path}", params=params, headers=headers)
        async with httpx.AsyncClient(timeout=10) as client: return await client.get(f"{settings.onemap_base_url}{path}", params=params, headers=headers)

    async def geocode(self, location: str) -> GeoPoint | None:
        response = await self._request("/common/elastic/search", {"searchVal": location, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1})
        response.raise_for_status(); results = response.json().get("results", [])
        if not results: return None
        return GeoPoint(float(results[0]["LATITUDE"]), float(results[0]["LONGITUDE"]))

    async def route(self, origin: GeoPoint, destination: GeoPoint, mode: TransportMode, when: datetime) -> RouteOutcome:
        if not settings.onemap_token: return RouteOutcome(None, "OneMap", "ONEMAP_TOKEN is not configured")
        route_type = {TransportMode.WALK: "walk", TransportMode.DRIVE: "drive", TransportMode.PUBLIC_TRANSPORT: "pt"}[mode]
        params = {"start": f"{origin.latitude},{origin.longitude}", "end": f"{destination.latitude},{destination.longitude}", "routeType": route_type}
        if mode == TransportMode.PUBLIC_TRANSPORT:
            params.update({"date": when.strftime("%Y-%m-%d"), "time": when.strftime("%H:%M:%S"), "mode": "TRANSIT", "maxWalkDistance": 1000})
        try:
            response = await self._request("/public/routingsvc/route", params); response.raise_for_status(); data = response.json()
            seconds = data.get("route_summary", {}).get("total_time") or data.get("plan", {}).get("itineraries", [{}])[0].get("duration")
            return RouteOutcome(math.ceil(float(seconds) / 60), "OneMap") if seconds is not None else RouteOutcome(None, "OneMap", "No route returned")
        except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
            return RouteOutcome(None, "OneMap", str(exc))

