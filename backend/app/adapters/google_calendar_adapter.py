"""Privacy-minimal Google Calendar HTTP adapter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import quote

import httpx

from app.adapters.ports import CalendarBusyInterval, CalendarEventInput
from app.services.calendar_credentials import CalendarCredentialError


GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_FREEBUSY_ENDPOINT = "https://www.googleapis.com/calendar/v3/freeBusy"
GOOGLE_CALENDARS_ENDPOINT = "https://www.googleapis.com/calendar/v3/calendars"
GOOGLE_TOKEN_REVOCATION_ENDPOINT = "https://oauth2.googleapis.com/revoke"


class CalendarProviderUnavailable(Exception):
    """A transient or sanitized Google Calendar provider failure."""


class CalendarAuthorizationExpired(Exception):
    """The user must reconnect Google Calendar."""


class GoogleCalendarAdapter:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        http_client: httpx.AsyncClient,
        refresh_token_resolver: Callable[[str], str],
        calendar_id_resolver: Callable[[str], str | None],
        calendar_id_saver: Callable[[str, str | None], None],
        mark_expired: Callable[[str], None] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.http_client = http_client
        self.refresh_token_resolver = refresh_token_resolver
        self.calendar_id_resolver = calendar_id_resolver
        self.calendar_id_saver = calendar_id_saver
        self.mark_expired = mark_expired
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._token_cache: dict[str, tuple[str, datetime]] = {}

    async def free_busy(
        self,
        credential_reference: str,
        start: datetime,
        end: datetime,
        timezone_name: str,
    ) -> tuple[CalendarBusyInterval, ...]:
        access_token = await self._access_token(credential_reference)
        try:
            response = await self.http_client.post(
                GOOGLE_FREEBUSY_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "timeMin": _aware_utc(start).isoformat(),
                    "timeMax": _aware_utc(end).isoformat(),
                    "timeZone": timezone_name,
                    "items": [{"id": "primary"}],
                },
            )
        except httpx.HTTPError as exc:
            raise CalendarProviderUnavailable("Google Calendar is temporarily unavailable") from exc
        if response.status_code == 401:
            self._expire(credential_reference)
            raise CalendarAuthorizationExpired("Please reconnect Google Calendar to continue")
        if response.status_code >= 400:
            raise CalendarProviderUnavailable("Google Calendar is temporarily unavailable")
        try:
            raw = response.json().get("calendars", {}).get("primary", {}).get("busy", [])
        except (TypeError, ValueError) as exc:
            raise CalendarProviderUnavailable("Google Calendar returned an invalid response") from exc
        return _clip_and_merge(raw, _aware_utc(start), _aware_utc(end))

    async def ensure_app_calendar(self, credential_reference: str, timezone_name: str) -> str:
        existing = self._calendar_id(credential_reference)
        if existing:
            return existing
        access_token = await self._access_token(credential_reference)
        response = await self._request(
            "POST",
            GOOGLE_CALENDARS_ENDPOINT,
            access_token=access_token,
            json={"summary": "Group Scheduler", "timeZone": timezone_name},
        )
        self._raise_for_provider(response, credential_reference)
        try:
            calendar_id = response.json()["id"]
        except (KeyError, TypeError, ValueError) as exc:
            raise CalendarProviderUnavailable("Google Calendar returned an invalid response") from exc
        if not isinstance(calendar_id, str) or not calendar_id:
            raise CalendarProviderUnavailable("Google Calendar returned an invalid response")
        self._save_calendar_id(credential_reference, calendar_id)
        return calendar_id

    async def upsert_event(
        self,
        credential_reference: str,
        idempotency_key: str,
        event: CalendarEventInput,
    ) -> str:
        provider_event_id = sha256(idempotency_key.encode()).hexdigest()[:32]
        payload = {
            "id": provider_event_id,
            "summary": event.title,
            "start": {"dateTime": event.start.isoformat(), "timeZone": event.timezone},
            "end": {"dateTime": event.end.isoformat(), "timeZone": event.timezone},
            "visibility": "private",
            "status": "tentative" if event.transparency == "transparent" else "confirmed",
            "transparency": event.transparency,
            "extendedProperties": {"private": event.private_metadata},
        }
        if event.location:
            payload["location"] = event.location

        for attempt in range(2):
            calendar_id = await self.ensure_app_calendar(credential_reference, event.timezone)
            access_token = await self._access_token(credential_reference)
            collection_url = self._events_url(calendar_id)
            response = await self._request("POST", collection_url, access_token=access_token, json=payload)
            if response.status_code == 404 and attempt == 0:
                self._save_calendar_id(credential_reference, None)
                continue
            if response.status_code == 409:
                response = await self._request(
                    "PUT",
                    f"{collection_url}/{provider_event_id}",
                    access_token=access_token,
                    json=payload,
                )
            self._raise_for_provider(response, credential_reference)
            return provider_event_id
        raise CalendarProviderUnavailable("Google Calendar application calendar is unavailable")

    async def delete_event(self, credential_reference: str, provider_event_id: str) -> None:
        calendar_id = self._calendar_id(credential_reference)
        if not calendar_id:
            return
        access_token = await self._access_token(credential_reference)
        response = await self._request(
            "DELETE",
            f"{self._events_url(calendar_id)}/{quote(provider_event_id, safe='')}",
            access_token=access_token,
        )
        if response.status_code == 404:
            return
        self._raise_for_provider(response, credential_reference)

    async def revoke(self, credential_reference: str) -> None:
        refresh_token = self._refresh_token(credential_reference)
        try:
            response = await self.http_client.post(
                GOOGLE_TOKEN_REVOCATION_ENDPOINT,
                data={"token": refresh_token},
            )
        except httpx.HTTPError as exc:
            raise CalendarProviderUnavailable("Google Calendar is temporarily unavailable") from exc
        if response.status_code >= 500:
            raise CalendarProviderUnavailable("Google Calendar is temporarily unavailable")

    async def aclose(self) -> None:
        await self.http_client.aclose()

    async def _access_token(self, credential_reference: str) -> str:
        cached = self._token_cache.get(credential_reference)
        now = self.now()
        if cached is not None and now < cached[1]:
            return cached[0]
        refresh_token = self._refresh_token(credential_reference)
        try:
            response = await self.http_client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
        except httpx.HTTPError as exc:
            raise CalendarProviderUnavailable("Google Calendar is temporarily unavailable") from exc
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.status_code == 400 and payload.get("error") == "invalid_grant":
            self._expire(credential_reference)
            raise CalendarAuthorizationExpired("Please reconnect Google Calendar to continue")
        if response.status_code >= 400:
            raise CalendarProviderUnavailable("Google Calendar is temporarily unavailable")
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise CalendarProviderUnavailable("Google Calendar returned an invalid response")
        try:
            expires_in = int(payload.get("expires_in", 3600))
        except (TypeError, ValueError):
            expires_in = 3600
        self._token_cache[credential_reference] = (
            access_token,
            now + timedelta(seconds=max(0, expires_in - 60)),
        )
        return access_token

    def _expire(self, credential_reference: str) -> None:
        self._token_cache.pop(credential_reference, None)
        if self.mark_expired is not None:
            self.mark_expired(credential_reference)

    def _refresh_token(self, credential_reference: str) -> str:
        try:
            return self.refresh_token_resolver(credential_reference)
        except CalendarCredentialError as exc:
            raise CalendarAuthorizationExpired(
                "Please reconnect Google Calendar to continue"
            ) from exc

    def _calendar_id(self, credential_reference: str) -> str | None:
        try:
            return self.calendar_id_resolver(credential_reference)
        except CalendarCredentialError as exc:
            raise CalendarAuthorizationExpired(
                "Please reconnect Google Calendar to continue"
            ) from exc

    def _save_calendar_id(self, credential_reference: str, calendar_id: str | None) -> None:
        try:
            self.calendar_id_saver(credential_reference, calendar_id)
        except CalendarCredentialError as exc:
            raise CalendarAuthorizationExpired(
                "Please reconnect Google Calendar to continue"
            ) from exc

    async def _request(self, method: str, url: str, *, access_token: str, json: dict | None = None) -> httpx.Response:
        try:
            return await self.http_client.request(
                method,
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=json,
            )
        except httpx.HTTPError as exc:
            raise CalendarProviderUnavailable("Google Calendar is temporarily unavailable") from exc

    def _raise_for_provider(self, response: httpx.Response, credential_reference: str) -> None:
        if response.status_code == 401:
            self._expire(credential_reference)
            raise CalendarAuthorizationExpired("Please reconnect Google Calendar to continue")
        if response.status_code >= 400:
            raise CalendarProviderUnavailable("Google Calendar is temporarily unavailable")

    @staticmethod
    def _events_url(calendar_id: str) -> str:
        return f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events"


def _clip_and_merge(raw: object, start: datetime, end: datetime) -> tuple[CalendarBusyInterval, ...]:
    parsed: list[CalendarBusyInterval] = []
    if not isinstance(raw, list):
        return ()
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            item_start = _parse_datetime(item["start"])
            item_end = _parse_datetime(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        clipped_start = max(start, item_start)
        clipped_end = min(end, item_end)
        if clipped_start < clipped_end:
            parsed.append(CalendarBusyInterval(clipped_start, clipped_end))
    parsed.sort(key=lambda item: (item.start, item.end))
    merged: list[CalendarBusyInterval] = []
    for item in parsed:
        if merged and item.start <= merged[-1].end:
            merged[-1] = CalendarBusyInterval(merged[-1].start, max(merged[-1].end, item.end))
        else:
            merged.append(item)
    return tuple(merged)


def _parse_datetime(value: str) -> datetime:
    return _aware_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
