"""Fetch, validate, and optionally apply the verified NParks park catalogue."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
import os

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.adapters.nparks_geojson_adapter import DataGovSgParkAdapter, ParkSourceFeature
from app.core.config import settings
from app.services.park_catalog import (
    ParkCatalogSyncService,
    load_verified_picnic_parks,
    normalize_verified_parks,
)


def normalization_counts(
    source_features: Sequence[ParkSourceFeature],
    *,
    matched_count: int,
    curated_count: int,
) -> dict[str, int]:
    return {
        "source_features": len(source_features),
        "curated_parks": curated_count,
        "rejected_features": len(source_features) - matched_count,
        "matched_parks": matched_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="validate and print counts only")
    mode.add_argument("--apply", action="store_true", help="commit the complete verified park snapshot")
    return parser.parse_args()


async def run(
    *,
    apply: bool,
    source: DataGovSgParkAdapter | None = None,
    engine_factory: Callable[[str], Engine] = create_engine,
) -> None:
    catalogue = source or DataGovSgParkAdapter(api_key=settings.data_gov_sg_api_key)
    try:
        source_features = await catalogue.load_parks()
    finally:
        await catalogue.aclose()

    allowlist = load_verified_picnic_parks()
    parks = normalize_verified_parks(source_features, allowlist)
    counts = normalization_counts(
        source_features,
        matched_count=len(parks),
        curated_count=len(allowlist),
    )
    print(" ".join(f"{name}={value}" for name, value in counts.items()))
    if not apply:
        return

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required with --apply")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    engine = engine_factory(database_url)
    with Session(engine) as db:
        result = ParkCatalogSyncService().sync(
            db,
            parks,
            synced_at=datetime.now(timezone.utc),
        )
    print(
        f"inserted={result.inserted} updated={result.updated} "
        f"deactivated={result.deactivated} verified={result.verified}"
    )


def main() -> None:
    args = parse_args()
    asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    main()
