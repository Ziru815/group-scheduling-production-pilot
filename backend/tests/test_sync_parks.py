from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.adapters.nparks_geojson_adapter import ParkSourceFeature
from app.models import ActivityType, Venue
from app.services.park_catalog import DATA_SOURCE
from scripts.sync_parks import normalization_counts, run


ALLOWLIST = Path(__file__).parents[1] / "app" / "data" / "verified_public_picnic_parks.json"


def features():
    entries = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    curated = [
        ParkSourceFeature(
            source_code=entry["source_code"],
            source_name=entry["source_name"],
            geometry_type="Polygon",
            coordinates=[[[103.8, 1.3], [103.81, 1.3], [103.8, 1.31]]],
        )
        for entry in entries
    ]
    return curated + [
        ParkSourceFeature(
            source_code="UNVERIFIED",
            source_name="UNVERIFIED PARK",
            geometry_type="Polygon",
            coordinates=[[[103.8, 1.3], [103.81, 1.3], [103.8, 1.31]]],
        )
    ]


class FakeSource:
    def __init__(self):
        self.closed = False

    async def load_parks(self):
        return features()

    async def aclose(self):
        self.closed = True


def test_normalization_counts_are_aggregate_only():
    counts = normalization_counts(features(), matched_count=20, curated_count=20)

    assert counts == {
        "source_features": 21,
        "curated_parks": 20,
        "rejected_features": 1,
        "matched_parks": 20,
    }


@pytest.mark.asyncio
async def test_dry_run_prints_counts_without_opening_database(capsys):
    source = FakeSource()

    def database_must_not_open(_url):
        raise AssertionError("dry-run opened a database")

    await run(apply=False, source=source, engine_factory=database_must_not_open)

    assert source.closed is True
    assert capsys.readouterr().out.strip() == (
        "source_features=21 curated_parks=20 rejected_features=1 matched_parks=20"
    )


@pytest.mark.asyncio
async def test_apply_requires_database_url_after_validating_source(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    source = FakeSource()

    with pytest.raises(SystemExit, match="DATABASE_URL"):
        await run(apply=True, source=source)

    assert source.closed is True


@pytest.mark.asyncio
async def test_apply_commits_twenty_and_is_idempotent_without_sensitive_output(
    monkeypatch, capsys
):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(ActivityType(category="OUTDOORS", name="Picnic"))
        db.commit()
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    await run(apply=True, source=FakeSource(), engine_factory=lambda _url: engine)
    await run(apply=True, source=FakeSource(), engine_factory=lambda _url: engine)

    output = capsys.readouterr().out
    with Session(engine) as db:
        parks = list(db.exec(select(Venue).where(Venue.data_source == DATA_SOURCE)).all())
    assert len(parks) == 20
    assert "inserted=20 updated=0 deactivated=0 verified=20" in output
    assert "inserted=0 updated=0 deactivated=0 verified=20" in output
    for forbidden in (
        "server-secret",
        "participant",
        "West Coast Highway",
        "1.296153",
        "103.762999",
    ):
        assert forbidden not in output
