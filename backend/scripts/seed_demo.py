"""Synchronise clearly-labelled development activities and venues.

The script is deliberately idempotent: it can enrich an existing demo
database after the sample catalogue grows without deleting user Sessions.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session, select

from app.core.database import create_db_and_tables, engine
from app.models import (
    ActivityType,
    SchedulingSession,
    SessionStatus,
    SupportStatus,
    Venue,
    VenueActivity,
    VenueCategory,
)


ACTIVITIES = {
    "badminton": ("SPORTS", "Badminton"),
    "football": ("SPORTS", "Football"),
    "basketball": ("SPORTS", "Basketball"),
    "picnic": ("OUTDOORS", "Picnic"),
    "board-games": ("LEISURE", "Board Games"),
    "bowling": ("LEISURE", "Bowling"),
}


def main() -> None:
    create_db_and_tables()
    catalogue = json.loads(
        (Path(__file__).resolve().parents[1] / "app" / "mock_data" / "venues.json").read_text(
            encoding="utf-8"
        )
    )["venues"]

    with Session(engine) as db:
        changed = False
        activities: dict[str, ActivityType] = {}
        for key, (category, name) in ACTIVITIES.items():
            activity = db.exec(select(ActivityType).where(ActivityType.name == name)).first()
            if activity is None:
                activity = ActivityType(category=category, name=name)
                db.add(activity)
                db.flush()
                changed = True
            activities[key] = activity

        for raw in catalogue:
            # The compact JSON catalogue stores one group-size value per
            # venue. Multi-sport centres use their football value (often 6),
            # but a badminton court is valid for two people. The SQL model is
            # venue-level, so use the least restrictive supported demo value.
            minimum_group_size = (
                2 if "badminton" in raw["activity_types"] else raw.get("min_group_size")
            )
            venue = db.exec(select(Venue).where(Venue.name == raw["name"])).first()
            if venue is None:
                venue = Venue(
                    name=raw["name"],
                    category=VenueCategory(raw["category"]),
                    address=f'{raw.get("address", raw["name"])} (demo)',
                    latitude=raw["lat"],
                    longitude=raw["lng"],
                    data_source="DEMO",
                    minimum_group_size=minimum_group_size,
                    optimal_group_size=raw.get("optimal_group_size"),
                    advance_booking_lead_minutes=raw.get("advance_booking_lead_minutes"),
                )
                db.add(venue)
                db.flush()
                changed = True
            elif venue.minimum_group_size != minimum_group_size:
                venue.minimum_group_size = minimum_group_size
                db.add(venue)
                changed = True

            for activity_key in raw["activity_types"]:
                activity = activities[activity_key]
                link = db.exec(
                    select(VenueActivity).where(
                        VenueActivity.venue_id == venue.venue_id,
                        VenueActivity.activity_type_id == activity.activity_type_id,
                    )
                ).first()
                if link is None:
                    db.add(
                        VenueActivity(
                            venue_id=venue.venue_id,
                            activity_type_id=activity.activity_type_id,
                            support_status=SupportStatus.SUPPORTED,
                            source_reference="mock_data/venues.json",
                        )
                    )
                    changed = True

        # Venue catalogue changes invalidate existing rankings just like a
        # Session response edit. The next organiser action will regenerate.
        if changed:
            for item in db.exec(
                select(SchedulingSession).where(SchedulingSession.status == SessionStatus.ACTIVE)
            ).all():
                item.source_revision += 1
                db.add(item)

        db.commit()
        print("Demo catalogue updated" if changed else "Demo catalogue already current")


if __name__ == "__main__":
    main()
