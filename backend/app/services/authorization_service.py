from uuid import UUID
from fastapi import HTTPException
from sqlmodel import Session

from app.models import Participant, ParticipantRole, UserAccount
from app.repositories import ParticipantRepository


def require_member(db: Session, session_id: UUID, user: UserAccount) -> Participant:
    member = ParticipantRepository(db).membership(session_id, user.account_id)
    if member is None:
        raise HTTPException(status_code=403, detail="Session membership required")
    return member


def require_organiser(db: Session, session_id: UUID, user: UserAccount) -> Participant:
    member = require_member(db, session_id, user)
    if member.role != ParticipantRole.ORGANISER:
        raise HTTPException(status_code=403, detail="Organiser permission required")
    return member

