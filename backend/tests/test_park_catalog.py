from __future__ import annotations

import os
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.adapters.nparks_geojson_adapter import ParkSourceFeature
from app.models.domain import (
    ActivityType,
    SchedulingSession,
    Venue,
    VenueActivity,
)
from app.models.enums import (
    GenerationStatus,
    SessionStatus,
    SupportStatus,
    VenueCategory,
    VenueVerificationStatus,
)
from app.services.park_catalog import (
    DATA_SOURCE,
    CatalogueSyncError,
    ParkCatalogSyncService,
    load_verified_picnic_parks,
    normalize_verified_parks,
)
from app.services.web_contract_service import _venue


BACKEND_ROOT = Path(__file__).parents[1]
ALLOWLIST_PATH = BACKEND_ROOT / "app" / "data" / "verified_public_picnic_parks.json"


def test_venue_model_has_nullable_meeting_point():
    column = Venue.__table__.c.meeting_point

    assert column.nullable is True
    assert column.type.length == 180


def test_meeting_point_migration_preserves_existing_sports_venue(tmp_path: Path):
    database = tmp_path / "migration.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database}"

    before = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "c9d4e5f6a7b8"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert before.returncode == 0, before.stderr

    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO venues (
                venue_id, name, category, address, latitude, longitude,
                data_source, is_active, verification_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "11111111111111111111111111111111",
                "Existing Sports Hall",
                "SPORTS_FACILITY",
                "Singapore",
                1.3,
                103.8,
                "TEST",
                1,
                "VERIFIED_PUBLIC",
            ),
        )
        connection.commit()

    after = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert after.returncode == 0, after.stderr

    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(venues)")}
        row = connection.execute(
            "SELECT name, category, meeting_point FROM venues"
        ).fetchone()
        connection.execute(
            "UPDATE venues SET meeting_point = ? WHERE name = ?",
            ("Park entrance", "Existing Sports Hall"),
        )
        stored = connection.execute(
            "SELECT meeting_point FROM venues WHERE name = ?",
            ("Existing Sports Hall",),
        ).fetchone()

    assert "meeting_point" in columns
    assert row == ("Existing Sports Hall", "SPORTS_FACILITY", None)
    assert stored == ("Park entrance",)


def raw_allowlist():
    return json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))


def source_features(entries=None):
    entries = entries or raw_allowlist()
    return [
        ParkSourceFeature(
            source_code=entry["source_code"],
            source_name=entry["source_name"],
            geometry_type="Polygon",
            coordinates=[[[103.8, 1.3], [103.81, 1.3], [103.8, 1.31]]],
        )
        for entry in entries
    ]


def test_verified_picnic_allowlist_has_twenty_route_ready_islandwide_entries():
    entries = raw_allowlist()

    assert len(entries) == 20
    assert len({entry["source_code"] for entry in entries}) == 20
    assert len({(entry["latitude"], entry["longitude"]) for entry in entries}) == 20
    assert {entry["region"] for entry in entries} == {
        "west",
        "north",
        "north-east",
        "central-south",
        "east",
    }
    for entry in entries:
        assert entry["source_name"].strip()
        assert entry["canonical_name"].strip()
        assert entry["meeting_point"].strip()
        assert entry["address"].strip()
        assert 1.1 <= entry["latitude"] <= 1.5
        assert 103.6 <= entry["longitude"] <= 104.1
        assert entry["verification_url"].startswith("https://")
        assert ".nparks.gov.sg/" in entry["verification_url"] or entry[
            "verification_url"
        ].startswith("https://www.nparks.gov.sg/")
        date.fromisoformat(entry["verified_on"])


def test_load_verified_picnic_parks_rejects_incomplete_duplicate_and_invalid_entries(
    tmp_path: Path,
):
    entries = raw_allowlist()

    for name, mutate, message in (
        ("incomplete", lambda rows: rows.pop(), "exactly 20"),
        (
            "duplicate-code",
            lambda rows: rows[1].update(source_code=rows[0]["source_code"]),
            "duplicate source code",
        ),
        (
            "duplicate-point",
            lambda rows: rows[1].update(
                latitude=rows[0]["latitude"], longitude=rows[0]["longitude"]
            ),
            "duplicate route point",
        ),
        (
            "outside-singapore",
            lambda rows: rows[0].update(latitude=51.5),
            "Singapore",
        ),
    ):
        changed = json.loads(json.dumps(entries))
        mutate(changed)
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        with pytest.raises(CatalogueSyncError, match=message):
            load_verified_picnic_parks(path)


def test_normalize_verified_parks_requires_every_exact_official_identity():
    allowlist = load_verified_picnic_parks()
    features = source_features()

    normalized = normalize_verified_parks(features, allowlist)

    assert len(normalized) == 20
    assert normalized[0].meeting_point
    with pytest.raises(CatalogueSyncError, match="missing"):
        normalize_verified_parks(features[:-1], allowlist)

    renamed = list(features)
    renamed[0] = ParkSourceFeature(
        source_code=renamed[0].source_code,
        source_name="RENAMED PARK",
        geometry_type=renamed[0].geometry_type,
        coordinates=renamed[0].coordinates,
    )
    with pytest.raises(CatalogueSyncError, match="name mismatch"):
        normalize_verified_parks(renamed, allowlist)


def park_engine():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return engine


def add_activity(db: Session, category: str, name: str) -> ActivityType:
    item = ActivityType(category=category, name=name)
    db.add(item)
    db.commit()
    return item


def add_active_picnic_session(db: Session, activity: ActivityType) -> SchedulingSession:
    now = datetime(2026, 10, 31, tzinfo=timezone.utc)
    item = SchedulingSession(
        name="Picnic",
        activity_type_id=activity.activity_type_id,
        date_range_start=now + timedelta(days=2),
        date_range_end=now + timedelta(days=3),
        timezone="Asia/Singapore",
        duration_minutes=60,
        response_deadline=now + timedelta(days=1),
        minimum_attendee_threshold=2,
        invitation_token="picnic-token",
        status=SessionStatus.ACTIVE,
    )
    db.add(item)
    db.commit()
    return item


def test_park_sync_inserts_updates_and_reapplies_idempotently():
    engine = park_engine()
    parks = normalize_verified_parks(source_features(), load_verified_picnic_parks())
    synced_at = datetime(2026, 10, 31, 8, tzinfo=timezone.utc)
    with Session(engine) as db:
        picnic = add_activity(db, "OUTDOORS", "Picnic")
        session = add_active_picnic_session(db, picnic)
        service = ParkCatalogSyncService()

        first = service.sync(db, parks, synced_at=synced_at)
        revision_after_first = db.get(SchedulingSession, session.session_id).source_revision
        second = service.sync(db, parks, synced_at=synced_at)

        stored = list(db.exec(select(Venue).where(Venue.data_source == DATA_SOURCE)).all())
        links = list(db.exec(select(VenueActivity)).all())
        assert first.inserted == 20
        assert first.verified == 20
        assert second == type(second)(verified=20)
        assert len(stored) == 20
        assert len(links) == 20
        assert all(link.activity_type_id == picnic.activity_type_id for link in links)
        assert all(link.support_status == SupportStatus.SUPPORTED for link in links)
        assert all(venue.category == VenueCategory.PARK for venue in stored)
        assert all(venue.verification_status == VenueVerificationStatus.VERIFIED_PUBLIC for venue in stored)
        assert all(venue.minimum_group_size is None for venue in stored)
        assert all(venue.optimal_group_size is None for venue in stored)
        assert all(venue.advance_booking_lead_minutes is None for venue in stored)
        assert revision_after_first == 2
        assert db.get(SchedulingSession, session.session_id).source_revision == 2


def test_park_sync_deactivates_only_obsolete_park_source_and_preserves_sports():
    engine = park_engine()
    parks = normalize_verified_parks(source_features(), load_verified_picnic_parks())
    with Session(engine) as db:
        picnic = add_activity(db, "OUTDOORS", "Picnic")
        badminton = add_activity(db, "SPORTS", "Badminton")
        sports = Venue(
            name="Sports Hall",
            category=VenueCategory.SPORTS_FACILITY,
            address="Singapore",
            latitude=1.3,
            longitude=103.8,
            data_source="DATA_GOV_SG_SPORT_FACILITIES",
            source_key="sports-source",
            verification_status=VenueVerificationStatus.VERIFIED_PUBLIC,
        )
        obsolete = Venue(
            name="Obsolete Park",
            category=VenueCategory.PARK,
            address="Singapore",
            latitude=1.31,
            longitude=103.81,
            data_source=DATA_SOURCE,
            source_key="obsolete",
            verification_status=VenueVerificationStatus.VERIFIED_PUBLIC,
        )
        db.add_all([sports, obsolete])
        db.flush()
        sports_link = VenueActivity(
            venue_id=sports.venue_id,
            activity_type_id=badminton.activity_type_id,
            support_status=SupportStatus.SUPPORTED,
            source_reference="official sports evidence",
        )
        db.add(sports_link)
        db.commit()
        sports_before = (
            sports.name,
            sports.is_active,
            sports.verification_status,
            sports_link.support_status,
            sports_link.source_reference,
        )

        result = ParkCatalogSyncService().sync(
            db, parks, synced_at=datetime(2026, 10, 31, tzinfo=timezone.utc)
        )

        db.refresh(sports)
        db.refresh(sports_link)
        db.refresh(obsolete)
        assert result.deactivated == 1
        assert obsolete.is_active is False
        assert sports_before == (
            sports.name,
            sports.is_active,
            sports.verification_status,
            sports_link.support_status,
            sports_link.source_reference,
        )
        assert picnic.activity_type_id in {
            link.activity_type_id
            for link in db.exec(select(VenueActivity)).all()
        }


def test_park_sync_retires_same_source_row_without_source_key_and_keeps_exact_catalogue():
    engine = park_engine()
    parks = normalize_verified_parks(source_features(), load_verified_picnic_parks())
    with Session(engine) as db:
        picnic = add_activity(db, "OUTDOORS", "Picnic")
        corrupt = Venue(
            name="Corrupt legacy park",
            category=VenueCategory.PARK,
            address="Singapore",
            latitude=1.32,
            longitude=103.82,
            data_source=DATA_SOURCE,
            source_key=None,
            verification_status=VenueVerificationStatus.VERIFIED_PUBLIC,
        )
        db.add(corrupt)
        db.flush()
        db.add(
            VenueActivity(
                venue_id=corrupt.venue_id,
                activity_type_id=picnic.activity_type_id,
                support_status=SupportStatus.SUPPORTED,
                source_reference="legacy evidence",
            )
        )
        db.commit()

        result = ParkCatalogSyncService().sync(
            db, parks, synced_at=datetime(2026, 10, 31, tzinfo=timezone.utc)
        )

        db.refresh(corrupt)
        source_rows = list(
            db.exec(select(Venue).where(Venue.data_source == DATA_SOURCE)).all()
        )
        active = [venue for venue in source_rows if venue.is_active]
        active_ids = {venue.venue_id for venue in active}
        active_links = [
            link
            for link in db.exec(select(VenueActivity)).all()
            if link.venue_id in active_ids
        ]
        assert result.deactivated == 1
        assert corrupt.is_active is False
        assert len(active) == 20
        assert {venue.source_key for venue in active} == {
            park.source_code for park in parks
        }
        assert len(active_links) == 20
        assert all(link.activity_type_id == picnic.activity_type_id for link in active_links)
        assert not list(
            db.exec(
                select(VenueActivity).where(VenueActivity.venue_id == corrupt.venue_id)
            ).all()
        )


def test_park_sync_rolls_back_tenth_write_and_preserves_last_good_rows(monkeypatch):
    engine = park_engine()
    parks = normalize_verified_parks(source_features(), load_verified_picnic_parks())
    with Session(engine) as db:
        add_activity(db, "OUTDOORS", "Picnic")
        service = ParkCatalogSyncService()
        service.sync(db, parks, synced_at=datetime(2026, 10, 30, tzinfo=timezone.utc))
        original = {
            venue.source_key: (venue.name, venue.latitude, venue.longitude, venue.is_active)
            for venue in db.exec(select(Venue).where(Venue.data_source == DATA_SOURCE)).all()
        }
        changed = [
            type(park)(
                **{
                    **park.__dict__,
                    "latitude": park.latitude + 0.0001,
                }
            )
            for park in parks
        ]
        original_flush = db.flush
        calls = 0

        def fail_tenth_write(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 10:
                raise RuntimeError("simulated tenth write failure")
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(db, "flush", fail_tenth_write)
        with pytest.raises(RuntimeError, match="tenth write"):
            service.sync(
                db,
                changed,
                synced_at=datetime(2026, 10, 31, tzinfo=timezone.utc),
            )
        monkeypatch.setattr(db, "flush", original_flush)
        db.expire_all()

        after = {
            venue.source_key: (venue.name, venue.latitude, venue.longitude, venue.is_active)
            for venue in db.exec(select(Venue).where(Venue.data_source == DATA_SOURCE)).all()
        }
        assert after == original


def test_browser_venue_projection_labels_nparks_and_meeting_point():
    park = Venue(
        venue_id=uuid4(),
        name="West Coast Park",
        category=VenueCategory.PARK,
        meeting_point="Central entrance",
        address="West Coast Highway",
        latitude=1.296,
        longitude=103.763,
        data_source=DATA_SOURCE,
        source_key="WJ500",
        last_synced_at=datetime(2026, 10, 31, tzinfo=timezone.utc),
        verification_status=VenueVerificationStatus.VERIFIED_PUBLIC,
    )

    projected = _venue(park)

    assert projected["meetingPoint"] == "Central entrance"
    assert projected["dataSource"] == "NParks via data.gov.sg"
    assert projected["category"] == "PARK"
