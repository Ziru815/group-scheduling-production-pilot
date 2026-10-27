"""Fetch, validate, and optionally apply the official SportSG catalogue."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import os

from sqlmodel import Session, create_engine

from app.adapters.data_gov_sg_adapter import DataGovSgAdapter
from app.adapters.onemap import OneMapAdapter
from app.core.config import settings
from app.services.venue_catalog import (
    VenueCatalogSyncService,
    enrich_venue_addresses,
    load_verified_venue_allowlist,
    normalize_facilities,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="validate and print counts only")
    mode.add_argument("--apply", action="store_true", help="commit one complete catalogue snapshot")
    return parser.parse_args()


async def run(*, apply: bool) -> None:
    source = DataGovSgAdapter(base_url=settings.data_gov_sg_base_url)
    try:
        normalized = normalize_facilities(await source.load_facilities())
    finally:
        await source.aclose()

    allowlist = load_verified_venue_allowlist()
    verified_count = sum(item.source_key in allowlist for item in normalized)
    print(
        f"normalized={len(normalized)} verified={verified_count} "
        f"unverified={len(normalized) - verified_count}"
    )
    if not apply:
        return

    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is required with --apply")

    base_url = settings.onemap_base_url.rstrip("/")
    if base_url.endswith("/api"):
        base_url = base_url[:-4]
    geocoder = OneMapAdapter(
        email=settings.onemap_email,
        password=settings.onemap_password,
        token=settings.onemap_token,
        base_url=base_url,
    )
    try:
        addresses = await enrich_venue_addresses(normalized, geocoder)
    finally:
        await geocoder.aclose()

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with Session(engine) as db:
        result = VenueCatalogSyncService(allowlist).sync(
            db,
            normalized,
            synced_at=datetime.now(timezone.utc),
            address_by_postal=addresses,
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
