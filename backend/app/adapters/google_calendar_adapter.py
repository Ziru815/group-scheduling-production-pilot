"""Google Calendar boundary.

The service layer is complete, but this adapter intentionally refuses calls until the
team approves OAuth scopes and a credential vault. Never persist refresh tokens in the
CalendarConnection row; store only a credential reference.
"""
from datetime import datetime


class GoogleCalendarAdapter:
    async def free_busy(self, credential_reference: str, start: datetime, end: datetime):
        raise RuntimeError("Google Calendar credential vault and approved scopes are not configured")

    async def upsert_event(self, credential_reference: str, idempotency_key: str, title: str, start: datetime, end: datetime) -> str:
        raise RuntimeError("Google Calendar write scope is not approved/configured")

    async def delete_event(self, credential_reference: str, provider_event_id: str) -> None:
        raise RuntimeError("Google Calendar write scope is not approved/configured")

