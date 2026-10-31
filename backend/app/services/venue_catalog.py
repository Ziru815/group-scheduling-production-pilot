"""Pure normalization and later persistence for the official venue catalogue."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path

from sqlmodel import Session, delete, select

from app.adapters.ports import Geocoder
from app.adapters.data_gov_sg_adapter import SourceFacilityRow
from app.models import (
    ActivityType,
    SupportStatus,
    Venue,
    VenueActivity,
    VenueCategory,
    VenueVerificationStatus,
)
from app.recommender.types import GeocodeStatus


FACILITY_ACTIVITY_MAP = {
    "badminton court": "Badminton",
    "basketball court": "Basketball",
    "football field": "Football",
    "soccer field": "Football",
    "bowling alley": "Bowling",
    "bowling centre": "Bowling",
}
POSTAL_CODE_PATTERN = re.compile(r"^[0-9]{6}$")
DATA_SOURCE = "DATA_GOV_SG_SPORT_FACILITIES"
ALLOWLIST_PATH = Path(__file__).resolve().parents[1] / "data" / "verified_public_sports_venues.json"


class CatalogueSyncError(Exception):
    """The complete catalogue could not be committed safely."""


@dataclass(frozen=True)
class NormalizedVenue:
    source_key: str
    name: str
    postal_code: str
    latitude: float
    longitude: float
    activities: tuple[str, ...]
    minimum_group_size: int | None = None
    optimal_group_size: int | None = None
    advance_booking_lead_minutes: int | None = None


@dataclass(frozen=True)
class VerifiedVenueEvidence:
    source_key: str
    source_name: str
    postal_code: str
    canonical_name: str
    verification_url: str
    verified_on: date
    verified_activities: tuple[str, ...] | None = None


@dataclass(frozen=True)
class VenueSyncResult:
    inserted: int = 0
    updated: int = 0
    deactivated: int = 0
    verified: int = 0


def normalize_facilities(rows: Iterable[SourceFacilityRow]) -> list[NormalizedVenue]:
    grouped: dict[tuple[str, str], list[SourceFacilityRow]] = defaultdict(list)
    activities: dict[tuple[str, str], set[str]] = defaultdict(set)

    for row in rows:
        display_name = _collapse_whitespace(row.venue_name)
        postal_code = _collapse_whitespace(row.postal_code)
        if (
            not display_name
            or not POSTAL_CODE_PATTERN.fullmatch(postal_code)
            or not _in_singapore(row.latitude, row.longitude)
        ):
            continue
        key = (_match_text(display_name), postal_code)
        activity = FACILITY_ACTIVITY_MAP.get(_match_text(row.sports_facility))
        if activity is None:
            continue
        grouped[key].append(row)
        activities[key].add(activity)

    venues: list[NormalizedVenue] = []
    for (matched_name, postal_code), source_rows in grouped.items():
        representative = min(source_rows, key=lambda item: item.source_row_id)
        source_key = venue_source_key(matched_name, postal_code)
        venues.append(
            NormalizedVenue(
                source_key=source_key,
                name=_collapse_whitespace(representative.venue_name),
                postal_code=postal_code,
                latitude=representative.latitude,
                longitude=representative.longitude,
                activities=tuple(sorted(activities[(matched_name, postal_code)])),
            )
        )
    return sorted(venues, key=lambda venue: venue.source_key)


def venue_source_key(name: str, postal_code: str) -> str:
    """Return the stable source identity shared by normalization and curation."""
    normalized_name = _match_text(name)
    normalized_postal = _collapse_whitespace(postal_code)
    return sha256(f"{normalized_name}|{normalized_postal}".encode()).hexdigest()


def load_verified_venue_allowlist(
    path: Path = ALLOWLIST_PATH,
) -> dict[str, VerifiedVenueEvidence]:
    raw_entries = json.loads(path.read_text(encoding="utf-8"))
    entries: dict[str, VerifiedVenueEvidence] = {}
    for raw in raw_entries:
        item = VerifiedVenueEvidence(
            source_key=raw["source_key"],
            source_name=raw["source_name"],
            postal_code=raw["postal_code"],
            canonical_name=raw["canonical_name"],
            verification_url=raw["verification_url"],
            verified_on=date.fromisoformat(raw["verified_on"]),
            verified_activities=(
                tuple(raw["verified_activities"])
                if "verified_activities" in raw
                else None
            ),
        )
        expected_key = venue_source_key(item.source_name, item.postal_code)
        if item.source_key != expected_key:
            raise CatalogueSyncError(
                f"allowlist source key does not match {item.source_name!r}"
            )
        if item.source_key in entries:
            raise CatalogueSyncError("allowlist contains a duplicate source key")
        entries[item.source_key] = item
    return entries


async def enrich_venue_addresses(
    venues: Sequence[NormalizedVenue],
    geocoder: Geocoder,
) -> dict[str, str]:
    """Return OneMap labels only when the match repeats the requested postal code."""
    addresses: dict[str, str] = {}
    for postal_code in sorted({venue.postal_code for venue in venues}):
        result = await geocoder.geocode(postal_code)
        if result.status is not GeocodeStatus.VALID:
            continue
        exact = next(
            (match for match in result.matches if match.postal_code == postal_code),
            None,
        )
        if exact is not None and exact.label.strip():
            addresses[postal_code] = exact.label.strip()
    return addresses


class VenueCatalogSyncService:
    def __init__(
        self,
        allowlist: Mapping[str, VerifiedVenueEvidence],
        *,
        data_source: str = DATA_SOURCE,
    ) -> None:
        self._allowlist = dict(allowlist)
        self._data_source = data_source

    def sync(
        self,
        db: Session,
        venues: Sequence[NormalizedVenue],
        *,
        synced_at: datetime,
        address_by_postal: Mapping[str, str] | None = None,
    ) -> VenueSyncResult:
        """Replace one complete source snapshot and commit it as one transaction."""
        address_by_postal = address_by_postal or {}
        inserted = updated = deactivated = verified = 0
        try:
            activity_names = sorted(
                {activity for venue in venues for activity in venue.activities}
            )
            activity_rows = {
                item.name: item
                for item in db.exec(
                    select(ActivityType).where(ActivityType.name.in_(activity_names))
                ).all()
            }
            missing = [name for name in activity_names if name not in activity_rows]
            if missing:
                raise CatalogueSyncError(
                    "missing ActivityType rows: " + ", ".join(missing)
                )

            existing = {
                item.source_key: item
                for item in db.exec(
                    select(Venue).where(Venue.data_source == self._data_source)
                ).all()
                if item.source_key is not None
            }
            incoming_keys: set[str] = set()
            for source in venues:
                if source.source_key in incoming_keys:
                    raise CatalogueSyncError(
                        f"duplicate normalized source key: {source.source_key}"
                    )
                incoming_keys.add(source.source_key)
                evidence = self._allowlist.get(source.source_key)
                venue = existing.get(source.source_key)
                if venue is None:
                    venue = Venue(
                        name=source.name,
                        category=VenueCategory.SPORTS_FACILITY,
                        address="",
                        postal_code=source.postal_code,
                        latitude=source.latitude,
                        longitude=source.longitude,
                        data_source=self._data_source,
                        source_key=source.source_key,
                    )
                    db.add(venue)
                    inserted += 1
                else:
                    updated += 1

                venue.name = evidence.canonical_name if evidence else source.name
                venue.address = address_by_postal.get(
                    source.postal_code,
                    f"{venue.name}, Singapore {source.postal_code}",
                )
                venue.postal_code = source.postal_code
                venue.latitude = source.latitude
                venue.longitude = source.longitude
                venue.last_synced_at = synced_at
                venue.is_active = True
                venue.verification_status = (
                    VenueVerificationStatus.VERIFIED_PUBLIC
                    if evidence
                    else VenueVerificationStatus.UNVERIFIED
                )
                if evidence:
                    verified += 1
                venue.minimum_group_size = source.minimum_group_size
                venue.optimal_group_size = source.optimal_group_size
                venue.advance_booking_lead_minutes = source.advance_booking_lead_minutes
                db.add(venue)
                db.flush()

                db.exec(
                    delete(VenueActivity).where(
                        VenueActivity.venue_id == venue.venue_id
                    )
                )
                supported_activities = set(source.activities)
                if evidence and evidence.verified_activities is not None:
                    supported_activities = set(evidence.verified_activities)
                db.add_all(
                    [
                        VenueActivity(
                            venue_id=venue.venue_id,
                            activity_type_id=activity_rows[name].activity_type_id,
                            support_status=(
                                SupportStatus.SUPPORTED
                                if name in supported_activities
                                else SupportStatus.UNAVAILABLE
                            ),
                            source_reference=(
                                evidence.verification_url
                                if evidence and name in supported_activities
                                else "data.gov.sg Sport Facilities"
                            ),
                        )
                        for name in source.activities
                    ]
                )

            for source_key, venue in existing.items():
                if source_key not in incoming_keys and venue.is_active:
                    venue.is_active = False
                    venue.last_synced_at = synced_at
                    db.add(venue)
                    deactivated += 1

            db.commit()
        except Exception:
            db.rollback()
            raise
        return VenueSyncResult(
            inserted=inserted,
            updated=updated,
            deactivated=deactivated,
            verified=verified,
        )


def _collapse_whitespace(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _match_text(value: str) -> str:
    return _collapse_whitespace(value).casefold()


def _in_singapore(latitude: float, longitude: float) -> bool:
    return 1.1 <= latitude <= 1.5 and 103.6 <= longitude <= 104.1
