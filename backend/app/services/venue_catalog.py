"""Pure normalization and later persistence for the official venue catalogue."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256

from app.adapters.data_gov_sg_adapter import SourceFacilityRow


FACILITY_ACTIVITY_MAP = {
    "badminton court": "Badminton",
    "basketball court": "Basketball",
    "football field": "Football",
    "soccer field": "Football",
    "bowling alley": "Bowling",
    "bowling centre": "Bowling",
}
POSTAL_CODE_PATTERN = re.compile(r"^[0-9]{6}$")


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
        source_key = sha256(f"{matched_name}|{postal_code}".encode()).hexdigest()
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


def _collapse_whitespace(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _match_text(value: str) -> str:
    return _collapse_whitespace(value).casefold()


def _in_singapore(latitude: float, longitude: float) -> bool:
    return 1.1 <= latitude <= 1.5 and 103.6 <= longitude <= 104.1
