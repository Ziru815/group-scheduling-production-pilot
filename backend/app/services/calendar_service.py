from uuid import UUID
from fastapi import HTTPException
from sqlmodel import Session, select

from app.adapters.google_calendar_adapter import CalendarAuthorizationExpired, CalendarProviderUnavailable
from app.adapters.ports import CalendarPort
from app.core.config import settings
from app.models import CalendarConnection, CalendarEvent, ConnectionStatus, EventStatus, EventType, Participant, SchedulingSession, UserAccount
from app.repositories import CalendarRepository
from app.services.authorization_service import require_member
from app.services.calendar_credentials import CalendarCredentialVault


class CalendarService:
    """Optional Calendar consent state; provider tokens live in an external vault."""
    @staticmethod
    def connect(db: Session, user: UserAccount, session_id: UUID, credential_reference: str, granted_scopes: list[str]):
        member = require_member(db, session_id, user); repo = CalendarRepository(db); connection = repo.connection(member.participant_id)
        if connection is None: connection = CalendarConnection(participant_id=member.participant_id)
        connection.connection_status = ConnectionStatus.CONNECTED; connection.credential_reference = credential_reference; connection.granted_scopes = " ".join(sorted(set(granted_scopes)))
        repo.save(connection); db.commit(); return connection

    @staticmethod
    def disconnect(db: Session, user: UserAccount, session_id: UUID):
        member = require_member(db, session_id, user); repo = CalendarRepository(db); connection = repo.connection(member.participant_id)
        if connection is None: return
        connection.connection_status = ConnectionStatus.DISCONNECTED; connection.credential_reference = None; connection.granted_scopes = ""
        db.add(connection); db.commit()

    @staticmethod
    def connect_user(
        db: Session,
        user: UserAccount,
        *,
        subject: str,
        refresh_token: str | None,
        granted_scopes: list[str],
    ) -> str:
        if subject != user.provider_user_id:
            raise HTTPException(409, "Choose the same Google account used to sign in")
        if not settings.google_calendar_credential_key:
            raise HTTPException(503, "Google Calendar credential storage is unavailable")
        vault = CalendarCredentialVault(db, settings.google_calendar_credential_key)
        credential = vault.store(user.account_id, refresh_token, granted_scopes)
        reference = vault.reference(credential.credential_id)
        scopes = " ".join(sorted(set(granted_scopes)))
        participants = list(db.exec(select(Participant).where(Participant.user_account_id == user.account_id)).all())
        repo = CalendarRepository(db)
        for participant in participants:
            connection = repo.connection(participant.participant_id)
            if connection is None:
                connection = CalendarConnection(participant_id=participant.participant_id)
            connection.connection_status = ConnectionStatus.CONNECTED
            connection.credential_reference = reference
            connection.granted_scopes = scopes
            db.add(connection)
        db.commit()
        return reference

    @staticmethod
    def attach_connected_user(
        db: Session,
        user: UserAccount,
        participant: Participant,
    ) -> CalendarConnection | None:
        repo = CalendarRepository(db)
        credential = repo.credential_for_user(user.account_id)
        if (
            credential is None
            or credential.status != ConnectionStatus.CONNECTED
            or not credential.encrypted_refresh_token
        ):
            return None
        connection = repo.connection(participant.participant_id)
        if connection is None:
            connection = CalendarConnection(participant_id=participant.participant_id)
        connection.connection_status = ConnectionStatus.CONNECTED
        connection.credential_reference = CalendarCredentialVault.reference(credential.credential_id)
        connection.granted_scopes = credential.granted_scopes
        db.add(connection)
        return connection

    @staticmethod
    def user_status(db: Session, user: UserAccount) -> ConnectionStatus:
        credential = CalendarRepository(db).credential_for_user(user.account_id)
        if credential is not None:
            return credential.status
        legacy = db.exec(
            select(CalendarConnection)
            .join(Participant, Participant.participant_id == CalendarConnection.participant_id)
            .where(Participant.user_account_id == user.account_id)
        ).first()
        return legacy.connection_status if legacy is not None else ConnectionStatus.DISCONNECTED

    @staticmethod
    async def disconnect_user(
        db: Session,
        user: UserAccount,
        adapter: CalendarPort | None = None,
    ) -> None:
        credential = CalendarRepository(db).credential_for_user(user.account_id)
        reference = (
            CalendarCredentialVault.reference(credential.credential_id)
            if credential is not None and credential.encrypted_refresh_token
            else None
        )
        connections = list(
            db.exec(
                select(CalendarConnection)
                .join(Participant, Participant.participant_id == CalendarConnection.participant_id)
                .where(Participant.user_account_id == user.account_id)
            ).all()
        )
        connection_ids = {connection.connection_id for connection in connections}
        events = list(
            db.exec(
                select(CalendarEvent).where(
                    CalendarEvent.calendar_connection_id.in_(connection_ids),
                    CalendarEvent.event_type == EventType.TENTATIVE_HOLD,
                    CalendarEvent.event_status != EventStatus.DELETED,
                )
            ).all()
        ) if connection_ids else []
        cleanup = [
            (event.event_id, event.provider_event_id)
            for event in events
            if event.provider_event_id
        ]
        db.commit()
        try:
            if adapter is not None and reference is not None:
                for event_id, provider_event_id in cleanup:
                    try:
                        await adapter.delete_event(reference, provider_event_id)
                        event = db.get(CalendarEvent, event_id)
                        if event is not None:
                            event.event_status = EventStatus.DELETED
                            event.last_error = None
                            db.add(event)
                            db.commit()
                    except Exception:
                        db.rollback()
                        event = db.get(CalendarEvent, event_id)
                        if event is not None:
                            event.event_status = EventStatus.ERROR
                            event.last_error = "Google Calendar cleanup failed during disconnect"
                            db.add(event)
                            db.commit()
                try:
                    await adapter.revoke(reference)
                except Exception:
                    db.rollback()
        finally:
            CalendarCredentialVault.disconnect_record(db, user.account_id)
            for connection_id in connection_ids:
                connection = db.get(CalendarConnection, connection_id)
                if connection is None:
                    continue
                connection.connection_status = ConnectionStatus.DISCONNECTED
                connection.credential_reference = None
                connection.granted_scopes = ""
                db.add(connection)
            db.commit()

    @staticmethod
    def mark_expired(db: Session, credential_reference: str) -> None:
        credential_id = CalendarCredentialVault._credential_id(credential_reference)
        credential = CalendarRepository(db).credential(credential_id)
        if credential is not None:
            credential.status = ConnectionStatus.EXPIRED
            db.add(credential)
        for connection in db.exec(
            select(CalendarConnection).where(CalendarConnection.credential_reference == credential_reference)
        ).all():
            connection.connection_status = ConnectionStatus.EXPIRED
            db.add(connection)
        db.commit()

    @staticmethod
    async def import_busy(
        db: Session,
        user: UserAccount,
        session_id: UUID,
        adapter: CalendarPort,
    ):
        member = require_member(db, session_id, user)
        item = db.get(SchedulingSession, session_id)
        if item is None:
            raise HTTPException(404, "Session not found")
        repo = CalendarRepository(db)
        credential = repo.credential_for_user(user.account_id)
        connection = repo.connection(member.participant_id)
        if credential is None or credential.status != ConnectionStatus.CONNECTED:
            raise HTTPException(409, "Calendar is not connected")
        reference = CalendarCredentialVault.reference(credential.credential_id)
        if connection is None:
            connection = CalendarConnection(participant_id=member.participant_id)
        connection.connection_status = ConnectionStatus.CONNECTED
        connection.credential_reference = reference
        connection.granted_scopes = credential.granted_scopes
        range_start = item.date_range_start
        range_end = item.date_range_end
        timezone_name = item.timezone
        db.add(connection)
        db.commit()
        try:
            return await adapter.free_busy(
                reference,
                range_start,
                range_end,
                timezone_name,
            )
        except CalendarAuthorizationExpired as exc:
            CalendarService.mark_expired(db, reference)
            raise HTTPException(409, "Calendar is not connected; reconnect Google Calendar") from exc
        except CalendarProviderUnavailable:
            return None

    @staticmethod
    async def delete_owned_event(
        db: Session,
        adapter: CalendarPort,
        event_id: UUID,
    ) -> None:
        event = db.get(CalendarEvent, event_id)
        if event is None:
            raise HTTPException(404, "Calendar event record not found")
        if not event.provider_event_id:
            raise HTTPException(409, "Calendar event has no owned provider event ID")
        connection = db.get(CalendarConnection, event.calendar_connection_id)
        if connection is None or not connection.credential_reference:
            raise HTTPException(409, "Calendar connection is not available")
        await adapter.delete_event(connection.credential_reference, event.provider_event_id)
        event.event_status = EventStatus.DELETED
        event.last_error = None
        db.add(event)
        db.commit()

