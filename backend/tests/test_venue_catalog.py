import json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app.adapters.data_gov_sg_adapter import SourceFacilityRow
from app.adapters.ports import AddressMatch, GeocodeResult
from app.models.domain import ActivityType, Venue, VenueActivity
from app.models.enums import (
    SupportStatus,
    VenueCategory,
    VenueVerificationStatus,
)
from app.recommender.types import Coordinates, GeocodeStatus
from app.repositories.aggregates import VenueRepository
from app.services.venue_catalog import (
    CatalogueSyncError,
    VenueCatalogSyncService,
    enrich_venue_addresses,
    load_verified_venue_allowlist,
    normalize_facilities,
    venue_source_key,
)
from scripts.sync_venues import normalization_counts


ALLOWLIST_PATH = (
    Path(__file__).parents[1] / "app" / "data" / "verified_public_sports_venues.json"
)


def source_row(row_id=1, **overrides):
    values = {
        "source_row_id": row_id,
        "venue_name": "Bishan Sports Hall",
        "postal_code": "579783",
        "latitude": 1.3547,
        "longitude": 103.8507,
        "sports_facility": "Badminton Court",
    }
    values.update(overrides)
    return SourceFacilityRow(**values)


def test_normalizer_rejects_blank_identity_fields():
    venues = normalize_facilities(
        [
            source_row(1, venue_name="   "),
            source_row(2, postal_code="-"),
            source_row(3, postal_code="NIL"),
            source_row(4, postal_code="12345"),
            source_row(5, latitude=0.5),
            source_row(6, longitude=120.0),
        ]
    )

    assert venues == []


def test_normalizer_groups_name_postal_case_variants():
    venues = normalize_facilities(
        [
            source_row(2, venue_name=" bishan   SPORTS hall ", sports_facility="Basketball Court"),
            source_row(1, venue_name="BISHAN SPORTS HALL", sports_facility="Badminton Court"),
        ]
    )

    assert len(venues) == 1
    assert venues[0].name == "BISHAN SPORTS HALL"
    assert venues[0].postal_code == "579783"
    assert venues[0].activities == ("Badminton", "Basketball")


def test_normalizer_collects_recognized_activities():
    venue = normalize_facilities(
        [
            source_row(1, sports_facility="Badminton Court"),
            source_row(2, sports_facility="Basketball Court"),
            source_row(3, sports_facility="Soccer Field"),
            source_row(4, sports_facility="Bowling Centre"),
        ]
    )[0]

    assert venue.activities == ("Badminton", "Basketball", "Bowling", "Football")
    assert venue.minimum_group_size is None
    assert venue.optimal_group_size is None
    assert venue.advance_booking_lead_minutes is None


def test_normalizer_ignores_unknown_facilities():
    assert normalize_facilities([source_row(sports_facility="Private Residents Lounge")]) == []

    [venue] = normalize_facilities(
        [
            source_row(1, sports_facility="Private Residents Lounge"),
            source_row(2, sports_facility="Badminton Court"),
        ]
    )
    assert venue.activities == ("Badminton",)


def test_normalization_counts_distinguish_rows_from_collapsed_venues():
    rows = [
        source_row(1, sports_facility="Badminton Court"),
        source_row(2, sports_facility="Basketball Court"),
        source_row(3, sports_facility="Unknown Facility"),
        source_row(4, postal_code="-"),
    ]

    counts = normalization_counts(rows, normalize_facilities(rows))

    assert counts == {
        "source_rows": 4,
        "recognized_rows": 2,
        "rejected_rows": 2,
        "normalized_venues": 1,
    }


def test_source_key_is_stable_across_row_order():
    first = source_row(1, venue_name="Bishan Sports Hall", sports_facility="Badminton Court")
    second = source_row(2, venue_name="BISHAN SPORTS HALL", sports_facility="Basketball Court")

    forward = normalize_facilities([first, second])
    reverse = normalize_facilities([second, first])

    assert forward == reverse
    assert len(forward[0].source_key) == 64


def test_venue_model_defaults_real_rows_to_unverified():
    venue = Venue(
        name="Bishan Sport Centre",
        category=VenueCategory.SPORTS_FACILITY,
        address="5 Bishan Street 14 Singapore 579783",
        postal_code="579783",
        latitude=1.356,
        longitude=103.851,
        data_source="DATA_GOV_SG_SPORT_FACILITIES",
        source_key=venue_source_key("Bishan Sport Centre", "579783"),
    )

    assert venue.verification_status == VenueVerificationStatus.UNVERIFIED
    assert venue.is_active is True
    assert venue.last_synced_at is None
    assert venue.minimum_group_size is None
    assert venue.optimal_group_size is None
    assert venue.advance_booking_lead_minutes is None


def test_venue_model_enforces_unique_source_identity():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    source_key = venue_source_key("Bishan Sport Centre", "579783")

    with Session(engine) as session:
        for name in ("Bishan Sport Centre", "Duplicate Bishan"):
            session.add(
                Venue(
                    name=name,
                    category=VenueCategory.SPORTS_FACILITY,
                    address="5 Bishan Street 14 Singapore 579783",
                    postal_code="579783",
                    latitude=1.356,
                    longitude=103.851,
                    data_source="DATA_GOV_SG_SPORT_FACILITIES",
                    source_key=source_key,
                )
            )
        with pytest.raises(IntegrityError):
            session.commit()


def test_verified_venue_allowlist_has_complete_official_evidence():
    entries = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))

    assert len(entries) >= 8
    assert len({entry["source_key"] for entry in entries}) == len(entries)
    for entry in entries:
        assert entry["source_key"] == venue_source_key(
            entry["source_name"], entry["postal_code"]
        )
        assert entry["canonical_name"].strip()
        assert entry["verification_url"].startswith(
            "https://www.activesgcircle.gov.sg/"
        )
        date.fromisoformat(entry["verified_on"])


def test_verified_venue_allowlist_excludes_closed_toa_payoh_centre():
    entries = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))

    assert all("toa payoh" not in entry["canonical_name"].casefold() for entry in entries)


def catalogue_engine():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return engine


def normalized_bishan(*, latitude=1.356, longitude=103.851):
    return normalize_facilities(
        [
            source_row(
                venue_name="Bishan Sport Centre",
                latitude=latitude,
                longitude=longitude,
            )
        ]
    )[0]


def add_activities(session, *names):
    rows = [ActivityType(category="SPORTS", name=name) for name in names]
    session.add_all(rows)
    session.commit()
    return rows


def test_sync_inserts_verified_venue_and_is_idempotent():
    engine = catalogue_engine()
    synced_at = datetime(2026, 10, 28, 8, tzinfo=timezone.utc)
    with Session(engine) as session:
        [badminton] = add_activities(session, "Badminton")
        service = VenueCatalogSyncService(load_verified_venue_allowlist())

        first = service.sync(session, [normalized_bishan()], synced_at=synced_at)
        second = service.sync(session, [normalized_bishan()], synced_at=synced_at)

        venues = list(session.exec(select(Venue)).all())
        links = list(session.exec(select(VenueActivity)).all())
        assert first.inserted == 1
        assert second.inserted == 0
        assert len(venues) == 1
        assert venues[0].name == "Bishan Sport Hall"
        assert venues[0].postal_code == "579783"
        assert venues[0].verification_status == VenueVerificationStatus.VERIFIED_PUBLIC
        assert venues[0].last_synced_at.replace(tzinfo=timezone.utc) == synced_at
        assert links[0].activity_type_id == badminton.activity_type_id


def test_sync_updates_coordinates_and_keeps_unknown_metadata_null():
    engine = catalogue_engine()
    with Session(engine) as session:
        add_activities(session, "Badminton")
        service = VenueCatalogSyncService(load_verified_venue_allowlist())
        service.sync(
            session,
            [normalized_bishan(latitude=1.35, longitude=103.85)],
            synced_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
        )

        result = service.sync(
            session,
            [normalized_bishan(latitude=1.36, longitude=103.86)],
            synced_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
        )

        [venue] = list(session.exec(select(Venue)).all())
        assert result.updated == 1
        assert (venue.latitude, venue.longitude) == (1.36, 103.86)
        assert venue.minimum_group_size is None
        assert venue.optimal_group_size is None
        assert venue.advance_booking_lead_minutes is None


def test_sync_keeps_non_allowlisted_venue_unverified():
    engine = catalogue_engine()
    unknown = normalize_facilities(
        [source_row(venue_name="Unknown Public-Looking Hall", postal_code="123456")]
    )[0]
    with Session(engine) as session:
        add_activities(session, "Badminton")
        VenueCatalogSyncService(load_verified_venue_allowlist()).sync(
            session,
            [unknown],
            synced_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
        )

        [venue] = list(session.exec(select(Venue)).all())
        assert venue.verification_status == VenueVerificationStatus.UNVERIFIED
        assert venue.is_active is True


def test_sync_deactivates_missing_without_deleting():
    engine = catalogue_engine()
    with Session(engine) as session:
        add_activities(session, "Badminton")
        service = VenueCatalogSyncService(load_verified_venue_allowlist())
        service.sync(
            session,
            [normalized_bishan()],
            synced_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
        )
        venue_id = session.exec(select(Venue)).one().venue_id

        result = service.sync(
            session,
            [],
            synced_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
        )

        venue = session.get(Venue, venue_id)
        assert result.deactivated == 1
        assert venue is not None
        assert venue.is_active is False


def test_sync_rolls_back_when_an_activity_type_is_missing():
    engine = catalogue_engine()
    multi_sport = normalize_facilities(
        [
            source_row(1, sports_facility="Badminton Court"),
            source_row(2, sports_facility="Basketball Court"),
        ]
    )[0]
    with Session(engine) as session:
        add_activities(session, "Badminton")

        with pytest.raises(CatalogueSyncError, match="Basketball"):
            VenueCatalogSyncService(load_verified_venue_allowlist()).sync(
                session,
                [multi_sport],
                synced_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
            )

        assert list(session.exec(select(Venue)).all()) == []


def test_sync_rolls_back_partial_upsert_and_preserves_last_good_catalogue(monkeypatch):
    engine = catalogue_engine()
    with Session(engine) as session:
        add_activities(session, "Badminton")
        service = VenueCatalogSyncService(load_verified_venue_allowlist())
        service.sync(
            session,
            [normalized_bishan(latitude=1.35, longitude=103.85)],
            synced_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
        )
        original_flush = session.flush
        flush_calls = 0

        def fail_during_upsert(*args, **kwargs):
            nonlocal flush_calls
            flush_calls += 1
            if flush_calls == 1:
                raise RuntimeError("simulated database failure")
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", fail_during_upsert)
        with pytest.raises(RuntimeError, match="simulated database failure"):
            service.sync(
                session,
                [normalized_bishan(latitude=1.36, longitude=103.86)],
                synced_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
            )

        monkeypatch.setattr(session, "flush", original_flush)
        session.expire_all()
        [venue] = list(session.exec(select(Venue)).all())
        assert (venue.latitude, venue.longitude) == (1.35, 103.85)
        assert venue.is_active is True


class FakeGeocoder:
    async def geocode(self, query):
        assert query == "579783"
        return GeocodeResult(
            status=GeocodeStatus.VALID,
            matches=(
                AddressMatch(
                    label="5 BISHAN STREET 14 SINGAPORE 579783",
                    postal_code="579783",
                    coordinates=Coordinates(1.356, 103.851),
                ),
            ),
        )


@pytest.mark.asyncio
async def test_enrich_venue_addresses_uses_matching_onemap_postal_code():
    result = await enrich_venue_addresses([normalized_bishan()], FakeGeocoder())

    assert result == {"579783": "5 BISHAN STREET 14 SINGAPORE 579783"}


def test_repository_requires_verified_active_venue_in_live_mode():
    engine = catalogue_engine()
    with Session(engine) as session:
        [badminton] = add_activities(session, "Badminton")
        venues = [
            Venue(
                venue_id=uuid4(),
                name="Verified active",
                category=VenueCategory.SPORTS_FACILITY,
                address="Singapore",
                latitude=1.3,
                longitude=103.8,
                data_source="TEST",
                source_key="a" * 64,
                is_active=True,
                verification_status=VenueVerificationStatus.VERIFIED_PUBLIC,
            ),
            Venue(
                venue_id=uuid4(),
                name="Unverified active",
                category=VenueCategory.SPORTS_FACILITY,
                address="Singapore",
                latitude=1.3,
                longitude=103.8,
                data_source="TEST",
                source_key="b" * 64,
                is_active=True,
                verification_status=VenueVerificationStatus.UNVERIFIED,
            ),
            Venue(
                venue_id=uuid4(),
                name="Verified inactive",
                category=VenueCategory.SPORTS_FACILITY,
                address="Singapore",
                latitude=1.3,
                longitude=103.8,
                data_source="TEST",
                source_key="c" * 64,
                is_active=False,
                verification_status=VenueVerificationStatus.VERIFIED_PUBLIC,
            ),
        ]
        session.add_all(venues)
        session.flush()
        session.add_all(
            [
                VenueActivity(
                    venue_id=venue.venue_id,
                    activity_type_id=badminton.activity_type_id,
                    support_status=SupportStatus.SUPPORTED,
                )
                for venue in venues
            ]
        )
        session.commit()

        demo_names = {
            item.name
            for item in VenueRepository(session).supported_for_activity(
                badminton.activity_type_id,
                require_verified=False,
            )
        }
        live_names = {
            item.name
            for item in VenueRepository(session).supported_for_activity(
                badminton.activity_type_id,
                require_verified=True,
            )
        }

        assert demo_names == {"Verified active", "Unverified active", "Verified inactive"}
        assert live_names == {"Verified active"}
