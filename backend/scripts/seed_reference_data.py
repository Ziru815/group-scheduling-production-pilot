"""Seed production-safe activity types without creating demo users or venues."""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.database import engine
from app.models import ActivityType


ACTIVITIES = (
    ("SPORTS", "Badminton"),
    ("SPORTS", "Football"),
    ("SPORTS", "Basketball"),
    ("OUTDOORS", "Picnic"),
    ("LEISURE", "Board Games"),
    ("LEISURE", "Bowling"),
)


def seed_reference_data(db: Session) -> int:
    changed = 0
    try:
        for category, name in ACTIVITIES:
            item = db.exec(select(ActivityType).where(ActivityType.name == name)).first()
            if item is None:
                db.add(ActivityType(category=category, name=name))
                changed += 1
            elif item.category != category or not item.is_active:
                item.category = category
                item.is_active = True
                db.add(item)
                changed += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return changed


def main() -> None:
    with Session(engine) as db:
        changed = seed_reference_data(db)
    print(f"reference_activity_types_changed={changed}")


if __name__ == "__main__":
    main()
