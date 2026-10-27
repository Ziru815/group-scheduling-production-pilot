import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from app.adapters.data_gov_sg_adapter import SourceFacilityRow
from app.models.domain import Venue
from app.models.enums import VenueCategory, VenueVerificationStatus
from app.services.venue_catalog import normalize_facilities, venue_source_key


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
