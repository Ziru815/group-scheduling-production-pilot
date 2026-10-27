from uuid import UUID
from fastapi import HTTPException
from sqlmodel import Session

from app.adapters.ports import CalendarPort
from app.models import CalendarConnection, ConnectionStatus, Participant, UserAccount
from app.repositories import CalendarRepository
from app.services.authorization_service import require_member


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

