"""Straight-line geometry used only for Venue shortlisting (FR-C4).

Final travel scoring always uses routing durations, never these distances
(NFR-8, SRS 5.5 "Straight-line distance supports Venue shortlisting only").
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from app.recommender.types import Coordinates

EARTH_RADIUS_KM = 6371.0088


def haversine_km(a: Coordinates, b: Coordinates) -> float:
    """Great-circle distance between two points, in kilometres."""
    lat1, lng1, lat2, lng2 = map(math.radians, (a.lat, a.lng, b.lat, b.lng))
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def centroid(points: Iterable[Coordinates]) -> Coordinates | None:
    """Geographic Centroid of the given points, or ``None`` if there are none.

    Uses the 3-D mean of unit vectors, which stays correct for any spread of
    points. For a Singapore-sized area it agrees with a plain lat/lng average
    to well under a metre.
    """
    x = y = z = 0.0
    n = 0
    for p in points:
        lat, lng = math.radians(p.lat), math.radians(p.lng)
        x += math.cos(lat) * math.cos(lng)
        y += math.cos(lat) * math.sin(lng)
        z += math.sin(lat)
        n += 1
    if n == 0:
        return None
    x, y, z = x / n, y / n, z / n
    lng = math.atan2(y, x)
    lat = math.atan2(z, math.hypot(x, y))
    return Coordinates(lat=math.degrees(lat), lng=math.degrees(lng))
