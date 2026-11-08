from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.adapters.google_calendar_adapter import (
    CalendarAuthorizationExpired,
    CalendarProviderUnavailable,
    GoogleCalendarAdapter,
)
from app.adapters.ports import CalendarEventInput
from app.services.calendar_credentials import CalendarCredentialError


START = datetime(2030, 11, 7, 1, 0, tzinfo=timezone.utc)
END = datetime(2030, 11, 7, 5, 0, tzinfo=timezone.utc)


def _adapter(handler, *, expired=None, now=None):
    return GoogleCalendarAdapter(
        client_id="client.apps.googleusercontent.com",
        client_secret="google-secret",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        refresh_token_resolver=lambda reference: "refresh-token" if reference == "db:credential" else "wrong",
        mark_expired=expired,
        now=now or (lambda: START),
        calendar_id_resolver=lambda _reference: None,
        calendar_id_saver=lambda _reference, _calendar_id: None,
    )


@pytest.mark.asyncio
async def test_free_busy_refreshes_once_caches_access_token_and_queries_only_primary():
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "short-lived-access", "expires_in": 3600})
        assert request.url.path == "/calendar/v3/freeBusy"
        assert request.headers["authorization"] == "Bearer short-lived-access"
        assert request.read() is not None
        body = __import__("json").loads(request.content)
        assert body == {
            "timeMin": "2030-11-07T01:00:00+00:00",
            "timeMax": "2030-11-07T05:00:00+00:00",
            "timeZone": "Asia/Singapore",
            "items": [{"id": "primary"}],
        }
        return httpx.Response(200, json={"calendars": {"primary": {"busy": []}}})

    adapter = _adapter(handler)
    try:
        assert await adapter.free_busy("db:credential", START, END, "Asia/Singapore") == ()
        assert await adapter.free_busy("db:credential", START, END, "Asia/Singapore") == ()
        assert [request.url.path for request in requests].count("/token") == 1
        assert not any("events" in request.url.path for request in requests)
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_free_busy_clips_merges_and_ignores_non_time_fields():
    def handler(request: httpx.Request):
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "access", "expires_in": 3600})
        return httpx.Response(
            200,
            json={
                "calendars": {
                    "primary": {
                        "busy": [
                            {"start": "2030-11-07T00:30:00Z", "end": "2030-11-07T02:00:00Z", "summary": "private title"},
                            {"start": "2030-11-07T01:45:00Z", "end": "2030-11-07T03:00:00Z", "location": "private place"},
                            {"start": "2030-11-07T04:30:00Z", "end": "2030-11-07T06:00:00Z"},
                            {"start": "bad", "end": "also-bad"},
                        ]
                    }
                },
                "groups": {"ignored": {"calendars": ["other@example.com"]}},
            },
        )

    adapter = _adapter(handler)
    try:
        busy = await adapter.free_busy("db:credential", START, END, "Asia/Singapore")
        assert [(row.start, row.end) for row in busy] == [
            (START, datetime(2030, 11, 7, 3, 0, tzinfo=timezone.utc)),
            (datetime(2030, 11, 7, 4, 30, tzinfo=timezone.utc), END),
        ]
        assert all(not hasattr(row, "summary") and not hasattr(row, "location") for row in busy)
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_token_cache_refreshes_inside_expiry_safety_margin():
    refreshes = 0
    current = START

    def handler(request: httpx.Request):
        nonlocal refreshes
        if request.url.path == "/token":
            refreshes += 1
            return httpx.Response(200, json={"access_token": f"access-{refreshes}", "expires_in": 120})
        return httpx.Response(200, json={"calendars": {"primary": {"busy": []}}})

    adapter = _adapter(handler, now=lambda: current)
    try:
        await adapter.free_busy("db:credential", START, END, "Asia/Singapore")
        current = START + timedelta(seconds=61)
        await adapter.free_busy("db:credential", START, END, "Asia/Singapore")
        assert refreshes == 2
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_invalid_grant_marks_credential_expired_without_exposing_response():
    expired = []
    adapter = _adapter(
        lambda _request: httpx.Response(400, json={"error": "invalid_grant", "error_description": "secret provider detail"}),
        expired=expired.append,
    )
    try:
        with pytest.raises(CalendarAuthorizationExpired, match="reconnect") as caught:
            await adapter.free_busy("db:credential", START, END, "Asia/Singapore")
        assert expired == ["db:credential"]
        assert "secret provider detail" not in str(caught.value)
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_credential_lookup_failure_is_normalized_without_provider_call():
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        return httpx.Response(500)

    adapter = GoogleCalendarAdapter(
        client_id="client",
        client_secret="secret",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        refresh_token_resolver=lambda _reference: (_ for _ in ()).throw(
            CalendarCredentialError("encrypted provider detail")
        ),
        calendar_id_resolver=lambda _reference: "group@example.com",
        calendar_id_saver=lambda _reference, _value: None,
        now=lambda: START,
    )
    try:
        with pytest.raises(CalendarAuthorizationExpired, match="reconnect") as caught:
            await adapter.free_busy("db:credential", START, END, "Asia/Singapore")
        assert "encrypted provider detail" not in str(caught.value)
        assert requests == []
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["timeout", 429, 500])
async def test_provider_timeout_rate_limit_and_server_error_are_unavailable(outcome):
    def handler(_request: httpx.Request):
        if outcome == "timeout":
            raise httpx.ReadTimeout("provider detail")
        return httpx.Response(outcome, json={"error": {"message": "provider detail"}})

    adapter = _adapter(handler)
    try:
        with pytest.raises(CalendarProviderUnavailable, match="unavailable") as caught:
            await adapter.free_busy("db:credential", START, END, "Asia/Singapore")
        assert "provider detail" not in str(caught.value)
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_ensure_app_calendar_creates_group_scheduler_once_and_persists_id():
    saved = []
    calendar_id = None
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "access", "expires_in": 3600})
        assert request.url.path == "/calendar/v3/calendars"
        assert __import__("json").loads(request.content) == {"summary": "Group Scheduler", "timeZone": "Asia/Singapore"}
        return httpx.Response(200, json={"id": "group-scheduler@example.com"})

    adapter = GoogleCalendarAdapter(
        client_id="client",
        client_secret="secret",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        refresh_token_resolver=lambda _reference: "refresh",
        calendar_id_resolver=lambda _reference: calendar_id,
        calendar_id_saver=lambda reference, value: saved.append((reference, value)),
        now=lambda: START,
    )
    try:
        assert await adapter.ensure_app_calendar("db:credential", "Asia/Singapore") == "group-scheduler@example.com"
        assert saved == [("db:credential", "group-scheduler@example.com")]
        assert len([request for request in requests if request.url.path == "/calendar/v3/calendars"]) == 1
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("transparency", "expected_status", "location"),
    [("transparent", "tentative", None), ("opaque", "confirmed", "5 Bishan Street 14")],
)
async def test_upsert_event_uses_private_payload_deterministic_id_and_correct_transparency(transparency, expected_status, location):
    payloads = []
    paths = []
    raw_paths = []

    def handler(request: httpx.Request):
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "access", "expires_in": 3600})
        paths.append(request.url.path)
        raw_paths.append(request.url.raw_path)
        payloads.append(__import__("json").loads(request.content))
        return httpx.Response(200, json={"id": payloads[-1]["id"]})

    adapter = GoogleCalendarAdapter(
        client_id="client",
        client_secret="secret",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        refresh_token_resolver=lambda _reference: "refresh",
        calendar_id_resolver=lambda _reference: "group-calendar@example.com",
        calendar_id_saver=lambda _reference, _value: None,
        now=lambda: START,
    )
    event = CalendarEventInput(
        title="Group activity: Badminton",
        start=START,
        end=END,
        timezone="Asia/Singapore",
        transparency=transparency,
        location=location,
        private_metadata={"session_id": "session-1", "event_type": expected_status},
    )
    try:
        first = await adapter.upsert_event("db:credential", "connection:session:slot:kind", event)
        second = await adapter.upsert_event("db:credential", "connection:session:slot:kind", event)
        assert first == second
        assert len(first) == 32 and set(first) <= set("0123456789abcdef")
        assert all(path == "/calendar/v3/calendars/group-calendar@example.com/events" for path in paths)
        assert all(b"group-calendar%40example.com" in path for path in raw_paths)
        assert all(payload["id"] == first for payload in payloads)
        assert payloads[0]["visibility"] == "private"
        assert payloads[0]["transparency"] == transparency
        assert payloads[0]["status"] == expected_status
        assert payloads[0]["extendedProperties"] == {"private": event.private_metadata}
        assert payloads[0]["start"] == {"dateTime": START.isoformat(), "timeZone": "Asia/Singapore"}
        assert payloads[0].get("location") == location
        assert "attendees" not in payloads[0]
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_upsert_updates_same_event_on_conflict_and_recreates_missing_app_calendar_once():
    stored_id = "deleted-calendar@example.com"
    saves = []
    event_posts = 0

    def resolve(_reference):
        return stored_id

    def save(_reference, value):
        nonlocal stored_id
        stored_id = value
        saves.append(value)

    def handler(request: httpx.Request):
        nonlocal event_posts
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "access", "expires_in": 3600})
        if request.url.path == "/calendar/v3/calendars":
            return httpx.Response(200, json={"id": "replacement@example.com"})
        if request.method == "POST" and "/events" in request.url.path:
            event_posts += 1
            if "deleted-calendar" in request.url.path:
                return httpx.Response(404)
            if event_posts == 3:
                return httpx.Response(409)
            return httpx.Response(200, json={"id": __import__("json").loads(request.content)["id"]})
        if request.method == "PUT":
            return httpx.Response(200, json={"id": request.url.path.rsplit("/", 1)[-1]})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    adapter = GoogleCalendarAdapter(
        client_id="client",
        client_secret="secret",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        refresh_token_resolver=lambda _reference: "refresh",
        calendar_id_resolver=resolve,
        calendar_id_saver=save,
        now=lambda: START,
    )
    event = CalendarEventInput("Hold", START, END, "Asia/Singapore", "transparent", None, {"kind": "hold"})
    try:
        event_id = await adapter.upsert_event("db:credential", "stable-key", event)
        assert saves == [None, "replacement@example.com"]
        assert stored_id == "replacement@example.com"
        assert await adapter.upsert_event("db:credential", "stable-key", event) == event_id
        assert event_posts == 3
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_delete_treats_missing_event_as_success_and_revoke_sends_only_token():
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "access", "expires_in": 3600})
        if request.url.host == "oauth2.googleapis.com" and request.url.path == "/revoke":
            assert parse_qs(request.content.decode()) == {"token": ["refresh-secret"]}
            return httpx.Response(200)
        return httpx.Response(404)

    from urllib.parse import parse_qs

    adapter = GoogleCalendarAdapter(
        client_id="client",
        client_secret="secret",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        refresh_token_resolver=lambda _reference: "refresh-secret",
        calendar_id_resolver=lambda _reference: "group@example.com",
        calendar_id_saver=lambda _reference, _value: None,
        now=lambda: START,
    )
    try:
        await adapter.delete_event("db:credential", "owned-event-id")
        await adapter.revoke("db:credential")
        assert any(request.method == "DELETE" and request.url.path.endswith("/events/owned-event-id") for request in requests)
    finally:
        await adapter.aclose()
