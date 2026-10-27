"""OneMap adapter, against a fake transport (no network)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from app.adapters.onemap import OneMapAdapter
from app.adapters.ports import Geocoder, Router
from app.recommender.types import GeocodeStatus, RoutingStatus, TransportMode

from .conftest import AMK, BISHAN, SGT

BASE = "https://onemap.test"


def adapter(handler, **kwargs) -> OneMapAdapter:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OneMapAdapter(base_url=BASE, client=client, **kwargs)


SEARCH_HIT = {
    "found": 1,
    "results": [
        {
            "SEARCHVAL": "BISHAN MRT STATION",
            "ADDRESS": "200 BISHAN ROAD BISHAN MRT STATION SINGAPORE 579827",
            "POSTAL": "579827",
            "LATITUDE": "1.35092",
            "LONGITUDE": "103.84825",
        }
    ],
}


def test_adapter_satisfies_ports():
    a = adapter(lambda r: httpx.Response(200))
    assert isinstance(a, Geocoder) and isinstance(a, Router)


def test_geocode_valid(run):
    def handler(req: httpx.Request):
        assert req.url.path == "/api/common/elastic/search"
        assert req.url.params["searchVal"] == "579827"
        assert req.url.params["returnGeom"] == "Y"
        return httpx.Response(200, json=SEARCH_HIT)

    result = run(adapter(handler).geocode(" 579827 "))
    assert result.status is GeocodeStatus.VALID
    [m] = result.matches
    assert m.postal_code == "579827" and abs(m.coordinates.lat - 1.35092) < 1e-9


def test_geocode_no_match_is_invalid(run):
    result = run(adapter(lambda r: httpx.Response(200, json={"found": 0, "results": []})).geocode("zzz"))
    assert result.status is GeocodeStatus.INVALID


def test_geocode_outage_is_unavailable(run):
    def down(req):
        raise httpx.ConnectError("down", request=req)

    assert run(adapter(down).geocode("579827")).status is GeocodeStatus.UNAVAILABLE
    assert run(adapter(lambda r: httpx.Response(503)).geocode("579827")).status is GeocodeStatus.UNAVAILABLE


def test_route_walk_uses_bearer_token_and_rounds_up(run):
    seen = {}

    def handler(req: httpx.Request):
        seen["auth"] = req.headers["Authorization"]
        seen["params"] = dict(req.url.params)
        return httpx.Response(200, json={"route_summary": {"total_time": 601, "total_distance": 800}})

    r = run(adapter(handler, token="tok").route(BISHAN, AMK, TransportMode.WALK, datetime(2026, 11, 7, 9, tzinfo=SGT)))
    assert r.status is RoutingStatus.AVAILABLE and r.minutes == 11
    assert seen["auth"] == "Bearer tok"
    assert seen["params"]["routeType"] == "walk"
    assert seen["params"]["start"] == f"{BISHAN.lat},{BISHAN.lng}"
    assert "date" not in seen["params"]


def test_route_public_transport_sends_singapore_date_and_time(run):
    seen = {}

    def handler(req: httpx.Request):
        seen.update(req.url.params)
        return httpx.Response(200, json={"plan": {"itineraries": [{"duration": 1500}, {"duration": 1320}]}})

    depart_utc = datetime(2026, 11, 7, 1, 30, tzinfo=timezone.utc)  # 09:30 in Singapore
    r = run(adapter(handler, token="t").route(BISHAN, AMK, TransportMode.PUBLIC_TRANSPORT, depart_utc))
    assert r.minutes == 22  # quickest itinerary
    assert seen["routeType"] == "pt" and seen["mode"] == "TRANSIT"
    assert seen["date"] == "11-07-2026" and seen["time"] == "09:30:00"


def test_route_failures_map_to_statuses(run):
    when = datetime(2026, 11, 7, 9, tzinfo=SGT)

    def go(handler):
        return run(adapter(handler, token="t").route(BISHAN, AMK, TransportMode.DRIVE, when))

    assert go(lambda r: httpx.Response(500)).status is RoutingStatus.UNAVAILABLE
    assert go(lambda r: httpx.Response(429)).status is RoutingStatus.UNAVAILABLE
    assert go(lambda r: httpx.Response(400, json={"error": "bad"})).status is RoutingStatus.ERROR
    assert go(lambda r: httpx.Response(200, json={"status_message": "no route"})).status is RoutingStatus.ERROR
    assert go(lambda r: httpx.Response(200, text="<html>")).status is RoutingStatus.ERROR


def test_route_without_credentials_is_unavailable(run):
    r = run(adapter(lambda req: httpx.Response(200)).route(BISHAN, AMK, TransportMode.WALK, datetime.now(SGT)))
    assert r.status is RoutingStatus.UNAVAILABLE


def test_token_is_fetched_once_and_reused(run):
    calls = {"token": 0, "route": 0}
    expiry = (datetime.now(timezone.utc) + timedelta(days=3)).timestamp()

    def handler(req: httpx.Request):
        if req.url.path == "/api/auth/post/getToken":
            calls["token"] += 1
            return httpx.Response(200, json={"access_token": "fresh", "expiry_timestamp": str(int(expiry))})
        calls["route"] += 1
        assert req.headers["Authorization"] == "Bearer fresh"
        return httpx.Response(200, json={"route_summary": {"total_time": 60}})

    a = adapter(handler, email="team@example.com", password="secret")
    when = datetime(2026, 11, 7, 9, tzinfo=SGT)

    async def three():
        for _ in range(3):
            await a.route(BISHAN, AMK, TransportMode.WALK, when)

    run(three())
    assert calls == {"token": 1, "route": 3}


def test_rejected_token_is_dropped_for_next_call(run):
    state = {"tokens": 0}

    def handler(req: httpx.Request):
        if req.url.path.endswith("getToken"):
            state["tokens"] += 1
            return httpx.Response(200, json={"access_token": f"t{state['tokens']}", "expiry_timestamp": "9999999999"})
        return httpx.Response(401) if req.headers["Authorization"] == "Bearer t1" else httpx.Response(
            200, json={"route_summary": {"total_time": 120}}
        )

    a = adapter(handler, email="e", password="p")
    when = datetime(2026, 11, 7, 9, tzinfo=SGT)

    async def twice():
        return [await a.route(BISHAN, AMK, TransportMode.WALK, when) for _ in range(2)]

    first, second = run(twice())
    assert first.status is RoutingStatus.UNAVAILABLE
    assert second.status is RoutingStatus.AVAILABLE and second.minutes == 2
