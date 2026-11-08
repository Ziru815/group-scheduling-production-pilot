"""Central policy for activity types that can be used in production.

Reference activity rows remain stable for historical Sessions.  New Sessions
and mutations, however, are allowed only while the activity has at least one
active, verified venue relationship in production.
"""

from uuid import UUID

from sqlmodel import Session, select

from app.core.config import settings
from app.models import ActivityType, SchedulingSession
from app.repositories import VenueRepository


class ActivityUnavailableError(Exception):
    def __init__(self, field_name: str | None = None):
        self.field_name = field_name
        super().__init__(
            "This activity is not currently supported by a verified venue."
        )


def production_support_required() -> bool:
    return settings.app_environment == "production" and not settings.use_mock_providers


def activity_is_supported(
    db: Session,
    activity_type_id: UUID,
    *,
    require_verified: bool,
) -> bool:
    activity = db.get(ActivityType, activity_type_id)
    if activity is None or not activity.is_active:
        return False
    return not require_verified or VenueRepository(db).has_verified_support(activity_type_id)


def supported_activity_categories(
    db: Session,
    *,
    require_verified: bool,
) -> list[dict]:
    activities = list(
        db.exec(
            select(ActivityType)
            .where(ActivityType.is_active == True)  # noqa: E712
            .order_by(ActivityType.category, ActivityType.name)
        ).all()
    )
    if require_verified:
        repo = VenueRepository(db)
        activities = [
            activity
            for activity in activities
            if repo.has_verified_support(activity.activity_type_id)
        ]
    grouped: dict[str, list[dict]] = {}
    for activity in activities:
        grouped.setdefault(activity.category.title(), []).append(
            {"id": activity.activity_type_id, "name": activity.name}
        )
    return [{"category": category, "types": values} for category, values in grouped.items()]


def supported_activity_types(db: Session, *, require_verified: bool) -> list[ActivityType]:
    activities = list(
        db.exec(
            select(ActivityType)
            .where(ActivityType.is_active == True)  # noqa: E712
            .order_by(ActivityType.category, ActivityType.name)
        ).all()
    )
    if not require_verified:
        return activities
    repo = VenueRepository(db)
    return [
        activity
        for activity in activities
        if repo.has_verified_support(activity.activity_type_id)
    ]


def require_creatable_activity(
    db: Session,
    activity_type_id: UUID,
    *,
    require_verified: bool,
) -> ActivityType:
    activity = db.get(ActivityType, activity_type_id)
    if (
        activity is None
        or not activity.is_active
        or (require_verified and not VenueRepository(db).has_verified_support(activity_type_id))
    ):
        raise ActivityUnavailableError("activityTypeId")
    return activity


def require_mutable_activity(
    db: Session,
    item: SchedulingSession,
    *,
    require_verified: bool,
) -> None:
    if not activity_is_supported(
        db,
        item.activity_type_id,
        require_verified=require_verified,
    ):
        raise ActivityUnavailableError()
