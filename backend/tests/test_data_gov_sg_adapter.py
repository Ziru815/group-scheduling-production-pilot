import httpx
import pytest

from app.adapters.data_gov_sg_adapter import (
    CatalogueSourceError,
    DataGovSgAdapter,
    SPORT_FACILITIES_RESOURCE_ID,
)


FIELDS = [
    {"id": "VenueName", "type": "text"},
    {"id": "PostalCode", "type": "text"},
    {"id": "Latitude", "type": "numeric"},
    {"id": "Longitude", "type": "numeric"},
    {"id": "SportsFacility", "type": "text"},
    {"id": "_id", "type": "int4"},
]


def row(row_id=1, **overrides):
    values = {
        "_id": row_id,
        "VenueName": "BISHAN SPORTS HALL",
        "PostalCode": "579783",
        "Latitude": "1.3547",
        "Longitude": "103.8507",
        "SportsFacility": "Badminton Court",
    }
    values.update(overrides)
    return values


def page(records, *, total=None, next_link=None, fields=FIELDS, success=True):
    result = {
        "resource_id": SPORT_FACILITIES_RESOURCE_ID,
        "fields": fields,
        "records": records,
        "total": len(records) if total is None else total,
        "limit": 1000,
        "_links": {"start": "/api/action/datastore_search"},
    }
    if next_link is not None:
        result["_links"]["next"] = next_link
    return {"success": success, "result": result}


def adapter(handler, **overrides):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return DataGovSgAdapter(
        base_url="https://data.test",
        client=client,
        retry_delay_seconds=0,
        **overrides,
    )


@pytest.mark.asyncio
async def test_load_facilities_follows_multiple_pages():
    requests = []

    def handler(request: httpx.Request):
        requests.append(str(request.url))
        if request.url.params.get("offset") == "2":
            return httpx.Response(200, json=page([row(3)], total=3))
        assert request.url.params["resource_id"] == SPORT_FACILITIES_RESOURCE_ID
        assert request.url.params["limit"] == "2"
        return httpx.Response(
            200,
            json=page(
                [row(1), row(2, SportsFacility="Basketball Court")],
                total=3,
                next_link=(
                    f"/api/action/datastore_search?resource_id={SPORT_FACILITIES_RESOURCE_ID}"
                    "&offset=2&limit=2"
                ),
            ),
        )

    source = adapter(handler, page_size=2)
    try:
        rows = await source.load_facilities()
    finally:
        await source.aclose()

    assert [item.source_row_id for item in rows] == [1, 2, 3]
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_load_facilities_preserves_query_in_three_next_links():
    def handler(request: httpx.Request):
        offset = int(request.url.params.get("offset", "0"))
        next_link = None
        if offset < 2:
            next_link = (
                f"/api/action/datastore_search?resource_id={SPORT_FACILITIES_RESOURCE_ID}"
                f"&offset={offset + 1}&limit=1"
            )
        return httpx.Response(
            200,
            json=page([row(offset + 1)], total=3, next_link=next_link),
        )

    source = adapter(handler, page_size=1)
    try:
        rows = await source.load_facilities()
    finally:
        await source.aclose()

    assert [item.source_row_id for item in rows] == [1, 2, 3]


@pytest.mark.asyncio
async def test_load_facilities_rejects_success_false():
    source = adapter(lambda _request: httpx.Response(200, json=page([], success=False)))
    try:
        with pytest.raises(CatalogueSourceError, match="unsuccessful"):
            await source.load_facilities()
    finally:
        await source.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 500, 503])
async def test_load_facilities_retries_bounded_provider_failures(status):
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(status)

    source = adapter(handler, max_retries=2)
    try:
        with pytest.raises(CatalogueSourceError, match=f"HTTP {status}"):
            await source.load_facilities()
    finally:
        await source.aclose()

    assert calls == 3


@pytest.mark.asyncio
async def test_load_facilities_maps_timeout_to_source_error():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    source = adapter(handler, max_retries=1)
    try:
        with pytest.raises(CatalogueSourceError, match="ReadTimeout"):
            await source.load_facilities()
    finally:
        await source.aclose()


@pytest.mark.asyncio
async def test_load_facilities_rejects_malformed_json():
    source = adapter(lambda _request: httpx.Response(200, text="<html>not json</html>"))
    try:
        with pytest.raises(CatalogueSourceError, match="JSON"):
            await source.load_facilities()
    finally:
        await source.aclose()


@pytest.mark.asyncio
async def test_load_facilities_rejects_missing_required_columns():
    missing = [field for field in FIELDS if field["id"] != "PostalCode"]
    source = adapter(lambda _request: httpx.Response(200, json=page([row()], fields=missing)))
    try:
        with pytest.raises(CatalogueSourceError, match="PostalCode"):
            await source.load_facilities()
    finally:
        await source.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [("Latitude", "north"), ("Longitude", None)],
)
async def test_load_facilities_rejects_invalid_numeric_coordinates(field, value):
    source = adapter(
        lambda _request: httpx.Response(200, json=page([row(**{field: value})]))
    )
    try:
        with pytest.raises(CatalogueSourceError, match=field):
            await source.load_facilities()
    finally:
        await source.aclose()


@pytest.mark.asyncio
async def test_load_facilities_rejects_duplicate_page_rows():
    def handler(request):
        if request.url.params.get("offset") == "1":
            return httpx.Response(200, json=page([row(1)], total=2))
        return httpx.Response(
            200,
            json=page(
                [row(1)],
                total=2,
                next_link=(
                    f"/api/action/datastore_search?resource_id={SPORT_FACILITIES_RESOURCE_ID}"
                    "&offset=1&limit=1"
                ),
            ),
        )

    source = adapter(handler, page_size=1)
    try:
        with pytest.raises(CatalogueSourceError, match="duplicate"):
            await source.load_facilities()
    finally:
        await source.aclose()


@pytest.mark.asyncio
async def test_load_facilities_rejects_truncated_response():
    source = adapter(lambda _request: httpx.Response(200, json=page([row(1)], total=2)))
    try:
        with pytest.raises(CatalogueSourceError, match="truncated"):
            await source.load_facilities()
    finally:
        await source.aclose()
