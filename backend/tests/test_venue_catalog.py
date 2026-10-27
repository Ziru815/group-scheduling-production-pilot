from app.adapters.data_gov_sg_adapter import SourceFacilityRow
from app.services.venue_catalog import normalize_facilities


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
