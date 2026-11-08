"""Validation and atomic persistence for verified public Picnic parks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
from urllib.parse import urlsplit

from sqlmodel import Session, delete, select

from app.adapters.nparks_geojson_adapter import ParkSourceFeature
from app.models import (
    ActivityType,
    SchedulingSession,
    SessionStatus,
    SupportStatus,
    Venue,
    VenueActivity,
    VenueCategory,
    VenueVerificationStatus,
)
from app.repositories import RecommendationRepository


DATA_SOURCE = "DATA_GOV_SG_NPARKS_PARKS"
ALLOWLIST_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "verified_public_picnic_parks.json"
)
REGIONS = frozenset({"west", "north", "north-east", "central-south", "east"})


class CatalogueSyncError(Exception):
    """The verified park snapshot could not be safely constructed or committed."""


@dataclass(frozen=True)
class CuratedPicnicPark:
    source_code: str
    source_name: str
    canonical_name: str
    meeting_point: str
    address: str
    latitude: float
    longitude: float
    verification_url: str
    verified_on: date
    region: str


@dataclass(frozen=True)
class NormalizedPark:
    source_code: str
    name: str
    meeting_point: str
    address: str
    latitude: float
    longitude: float
    verification_url: str
    verified_on: date
    region: str


@dataclass(frozen=True)
class ParkSyncResult:
    inserted: int = 0
    updated: int = 0
    deactivated: int = 0
    verified: int = 0


def load_verified_picnic_parks(
    path: Path = ALLOWLIST_PATH,
) -> dict[str, CuratedPicnicPark]:
    try:
        raw_entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogueSyncError("park allowlist is unavailable or invalid") from exc
    if not isinstance(raw_entries, list) or len(raw_entries) != 20:
        raise CatalogueSyncError("park allowlist must contain exactly 20 entries")

    entries: dict[str, CuratedPicnicPark] = {}
    route_points: set[tuple[float, float]] = set()
    try:
        for raw in raw_entries:
            if not isinstance(raw, dict):
                raise CatalogueSyncError("park allowlist entry must be an object")
            item = CuratedPicnicPark(
                source_code=_required_text(raw, "source_code"),
                source_name=_required_text(raw, "source_name"),
                canonical_name=_required_text(raw, "canonical_name"),
                meeting_point=_required_text(raw, "meeting_point"),
                address=_required_text(raw, "address"),
                latitude=float(raw["latitude"]),
                longitude=float(raw["longitude"]),
                verification_url=_required_text(raw, "verification_url"),
                verified_on=date.fromisoformat(_required_text(raw, "verified_on")),
                region=_required_text(raw, "region"),
            )
            if item.source_code in entries:
                raise CatalogueSyncError("park allowlist contains a duplicate source code")
            point = (item.latitude, item.longitude)
            if point in route_points:
                raise CatalogueSyncError("park allowlist contains a duplicate route point")
            if not _in_singapore(item.latitude, item.longitude):
                raise CatalogueSyncError("park allowlist route point is outside Singapore")
            parsed_url = urlsplit(item.verification_url)
            if (
                parsed_url.scheme != "https"
                or parsed_url.hostname is None
                or not (
                    parsed_url.hostname == "nparks.gov.sg"
                    or parsed_url.hostname.endswith(".nparks.gov.sg")
                )
            ):
                raise CatalogueSyncError("park allowlist evidence URL is not official NParks HTTPS")
            if item.region not in REGIONS:
                raise CatalogueSyncError("park allowlist contains an unknown region")
            entries[item.source_code] = item
            route_points.add(point)
    except (KeyError, TypeError, ValueError) as exc:
        raise CatalogueSyncError("park allowlist entry schema is invalid") from exc

    if {item.region for item in entries.values()} != REGIONS:
        raise CatalogueSyncError("park allowlist does not cover all required regions")
    return entries


def normalize_verified_parks(
    features: Sequence[ParkSourceFeature],
    allowlist: Mapping[str, CuratedPicnicPark],
) -> list[NormalizedPark]:
    by_code = {feature.source_code: feature for feature in features}
    missing = sorted(set(allowlist) - set(by_code))
    if missing:
        raise CatalogueSyncError(
            "official snapshot is missing curated park identities: " + ", ".join(missing)
        )

    parks: list[NormalizedPark] = []
    for source_code, evidence in sorted(allowlist.items()):
        feature = by_code[source_code]
        if feature.source_name != evidence.source_name:
            raise CatalogueSyncError(
                f"official park name mismatch for {source_code}: {feature.source_name!r}"
            )
        parks.append(
            NormalizedPark(
                source_code=source_code,
                name=evidence.canonical_name,
                meeting_point=evidence.meeting_point,
                address=evidence.address,
                latitude=evidence.latitude,
                longitude=evidence.longitude,
                verification_url=evidence.verification_url,
                verified_on=evidence.verified_on,
                region=evidence.region,
            )
        )
    if len(parks) != 20:
        raise CatalogueSyncError("normalized park catalogue must contain exactly 20 parks")
    return parks


class ParkCatalogSyncService:
    def __init__(self, *, data_source: str = DATA_SOURCE) -> None:
        self._data_source = data_source

    def sync(
        self,
        db: Session,
        parks: Sequence[NormalizedPark],
        *,
        synced_at: datetime,
    ) -> ParkSyncResult:
        if len(parks) != 20 or len({park.source_code for park in parks}) != 20:
            raise CatalogueSyncError("park sync requires exactly 20 unique parks")

        inserted = updated = deactivated = 0
        catalogue_changed = False
        try:
            picnic = db.exec(
                select(ActivityType).where(
                    ActivityType.name == "Picnic",
                    ActivityType.is_active == True,  # noqa: E712
                )
            ).first()
            if picnic is None:
                raise CatalogueSyncError("missing active Picnic ActivityType row")

            source_rows = list(
                db.exec(
                    select(Venue).where(Venue.data_source == self._data_source)
                ).all()
            )
            existing = {
                venue.source_key: venue
                for venue in source_rows
                if venue.source_key is not None
            }
            incoming_codes = {park.source_code for park in parks}

            for park in parks:
                venue = existing.get(park.source_code)
                if venue is None:
                    venue = Venue(
                        name=park.name,
                        category=VenueCategory.PARK,
                        meeting_point=park.meeting_point,
                        address=park.address,
                        latitude=park.latitude,
                        longitude=park.longitude,
                        data_source=self._data_source,
                        source_key=park.source_code,
                        last_synced_at=synced_at,
                        is_active=True,
                        verification_status=VenueVerificationStatus.VERIFIED_PUBLIC,
                    )
                    db.add(venue)
                    db.flush()
                    inserted += 1
                    row_changed = True
                else:
                    desired = (
                        park.name,
                        VenueCategory.PARK,
                        park.meeting_point,
                        park.address,
                        park.latitude,
                        park.longitude,
                        True,
                        VenueVerificationStatus.VERIFIED_PUBLIC,
                        None,
                        None,
                        None,
                    )
                    current = (
                        venue.name,
                        venue.category,
                        venue.meeting_point,
                        venue.address,
                        venue.latitude,
                        venue.longitude,
                        venue.is_active,
                        venue.verification_status,
                        venue.minimum_group_size,
                        venue.optimal_group_size,
                        venue.advance_booking_lead_minutes,
                    )
                    row_changed = current != desired
                    if row_changed:
                        (
                            venue.name,
                            venue.category,
                            venue.meeting_point,
                            venue.address,
                            venue.latitude,
                            venue.longitude,
                            venue.is_active,
                            venue.verification_status,
                            venue.minimum_group_size,
                            venue.optimal_group_size,
                            venue.advance_booking_lead_minutes,
                        ) = desired
                        venue.last_synced_at = synced_at
                        db.add(venue)
                        db.flush()
                        updated += 1

                links = list(
                    db.exec(
                        select(VenueActivity).where(
                            VenueActivity.venue_id == venue.venue_id
                        )
                    ).all()
                )
                link_is_current = (
                    len(links) == 1
                    and links[0].activity_type_id == picnic.activity_type_id
                    and links[0].support_status == SupportStatus.SUPPORTED
                    and links[0].source_reference == park.verification_url
                )
                if not link_is_current:
                    db.exec(
                        delete(VenueActivity).where(
                            VenueActivity.venue_id == venue.venue_id
                        )
                    )
                    db.add(
                        VenueActivity(
                            venue_id=venue.venue_id,
                            activity_type_id=picnic.activity_type_id,
                            support_status=SupportStatus.SUPPORTED,
                            source_reference=park.verification_url,
                        )
                    )
                    db.flush()
                    if not row_changed and venue.source_key in existing:
                        updated += 1
                catalogue_changed = catalogue_changed or row_changed or not link_is_current

            for venue in source_rows:
                if venue.source_key in incoming_codes:
                    continue
                if venue.is_active:
                    venue.is_active = False
                    venue.last_synced_at = synced_at
                    db.add(venue)
                    db.flush()
                    deactivated += 1
                    catalogue_changed = True
                retired_links = list(
                    db.exec(
                        select(VenueActivity).where(
                            VenueActivity.venue_id == venue.venue_id
                        )
                    ).all()
                )
                if retired_links:
                    db.exec(
                        delete(VenueActivity).where(
                            VenueActivity.venue_id == venue.venue_id
                        )
                    )
                    db.flush()
                    catalogue_changed = True

            active_source_rows = [
                venue
                for venue in db.exec(
                    select(Venue).where(Venue.data_source == self._data_source)
                ).all()
                if venue.is_active
            ]
            active_ids = {venue.venue_id for venue in active_source_rows}
            active_links = [
                link
                for link in db.exec(select(VenueActivity)).all()
                if link.venue_id in active_ids
            ]
            if (
                len(active_source_rows) != 20
                or {venue.source_key for venue in active_source_rows}
                != incoming_codes
                or any(
                    venue.category != VenueCategory.PARK
                    or venue.verification_status
                    != VenueVerificationStatus.VERIFIED_PUBLIC
                    for venue in active_source_rows
                )
                or len(active_links) != 20
                or any(
                    link.activity_type_id != picnic.activity_type_id
                    or link.support_status != SupportStatus.SUPPORTED
                    for link in active_links
                )
            ):
                raise CatalogueSyncError(
                    "park sync postcondition requires exactly 20 active verified Picnic parks"
                )

            if catalogue_changed:
                recommendations = RecommendationRepository(db)
                sessions = list(
                    db.exec(
                        select(SchedulingSession).where(
                            SchedulingSession.activity_type_id == picnic.activity_type_id,
                            SchedulingSession.status == SessionStatus.ACTIVE,
                        )
                    ).all()
                )
                for item in sessions:
                    item.source_revision += 1
                    item.updated_at = synced_at
                    db.add(item)
                    recommendations.invalidate(item.session_id)

            db.commit()
        except Exception:
            db.rollback()
            raise

        return ParkSyncResult(
            inserted=inserted,
            updated=updated,
            deactivated=deactivated,
            verified=len(parks),
        )


def _required_text(raw: Mapping[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CatalogueSyncError(f"park allowlist entry has invalid {key}")
    return value.strip()


def _in_singapore(latitude: float, longitude: float) -> bool:
    return 1.1 <= latitude <= 1.5 and 103.6 <= longitude <= 104.1
