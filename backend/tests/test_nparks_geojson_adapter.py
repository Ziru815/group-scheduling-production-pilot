import json

import httpx
import pytest

from app.adapters.data_gov_sg_adapter import CatalogueSourceError
from app.adapters.nparks_geojson_adapter import (
    MAX_DOWNLOAD_BYTES,
    NPARKS_PARKS_DATASET_ID,
    DataGovSgParkAdapter,
)


POLL_PATH = f"/v1/public/api/datasets/{NPARKS_PARKS_DATASET_ID}/poll-download"
DOWNLOAD_URL = "https://s3.ap-southeast-1.amazonaws.com/blobs.data.gov.sg/parks.geojson?signature=test"


def feature(code="P001", name="West Coast Park", *, geometry=None):
    return {
        "type": "Feature",
        "properties": {"L_CODE": code, "NAME": name},
        "geometry": geometry
        or {
            "type": "Polygon",
            "coordinates": [[[103.76, 1.30], [103.77, 1.30], [103.76, 1.31], [103.76, 1.30]]],
        },
    }


def collection(features):
    return {"type": "FeatureCollection", "features": features}


def poll(url=DOWNLOAD_URL):
    return {"code": 0, "data": {"url": url}, "errorMsg": ""}


def adapter(handler, **overrides):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return DataGovSgParkAdapter(
        base_url="https://api-open.data.gov.sg",
        client=client,
        retry_delay_seconds=0,
        **overrides,
    )


def geojson_response(features):
    return httpx.Response(
        200,
        content=json.dumps(collection(features)).encode(),
        headers={"content-type": "application/geo+json"},
    )


@pytest.mark.asyncio
async def test_load_parks_polls_then_downloads_complete_geojson():
    requests = []
    multipolygon = {
        "type": "MultiPolygon",
        "coordinates": [[[[103.82, 1.35], [103.83, 1.35], [103.82, 1.36], [103.82, 1.35]]]],
    }

    def handler(request: httpx.Request):
        requests.append(request)
        if request.url.path == POLL_PATH:
            return httpx.Response(201, json=poll())
        return geojson_response(
            [feature(), feature("P002", "Bishan-Ang Mo Kio Park", geometry=multipolygon)]
        )

    source = adapter(handler)
    try:
        parks = await source.load_parks()
    finally:
        await source.aclose()

    assert [(park.source_code, park.source_name, park.geometry_type) for park in parks] == [
        ("P001", "West Coast Park", "Polygon"),
        ("P002", "Bishan-Ang Mo Kio Park", "MultiPolygon"),
    ]
    assert [request.url.path for request in requests] == [POLL_PATH, "/blobs.data.gov.sg/parks.geojson"]


@pytest.mark.asyncio
async def test_load_parks_sends_optional_api_key_only_to_poll():
    headers = []

    def handler(request: httpx.Request):
        headers.append(dict(request.headers))
        if request.url.path == POLL_PATH:
            return httpx.Response(201, json=poll())
        return geojson_response([feature()])

    source = adapter(handler, api_key="server-secret")
    try:
        await source.load_parks()
    finally:
        await source.aclose()

    assert headers[0]["x-api-key"] == "server-secret"
    assert "x-api-key" not in headers[1]


@pytest.mark.asyncio
async def test_load_parks_retries_429_and_5xx_then_succeeds():
    poll_attempts = 0

    def handler(request: httpx.Request):
        nonlocal poll_attempts
        if request.url.path == POLL_PATH:
            poll_attempts += 1
            if poll_attempts == 1:
                return httpx.Response(429)
            if poll_attempts == 2:
                return httpx.Response(503)
            return httpx.Response(201, json=poll())
        return geojson_response([feature()])

    source = adapter(handler, max_retries=2)
    try:
        parks = await source.load_parks()
    finally:
        await source.aclose()

    assert len(parks) == 1
    assert poll_attempts == 3


@pytest.mark.asyncio
async def test_load_parks_rejects_timeout_and_malformed_json():
    def timeout_handler(request: httpx.Request):
        raise httpx.ReadTimeout("slow", request=request)

    timed_out = adapter(timeout_handler, max_retries=0)
    try:
        with pytest.raises(CatalogueSourceError, match="ReadTimeout"):
            await timed_out.load_parks()
    finally:
        await timed_out.aclose()

    def malformed_handler(request: httpx.Request):
        if request.url.path == POLL_PATH:
            return httpx.Response(201, json=poll())
        return httpx.Response(200, text="not-json", headers={"content-type": "application/json"})

    malformed = adapter(malformed_handler)
    try:
        with pytest.raises(CatalogueSourceError, match="JSON"):
            await malformed.load_parks()
    finally:
        await malformed.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://s3.ap-southeast-1.amazonaws.com/blobs.data.gov.sg/parks.geojson",
        "https://s3.ap-southeast-1.amazonaws.com:444/blobs.data.gov.sg/parks.geojson",
        "https://user:password@s3.ap-southeast-1.amazonaws.com/blobs.data.gov.sg/parks.geojson",
        "https://s3.ap-southeast-1.amazonaws.com/blobs.data.gov.sg/parks.geojson#fragment",
        "https://example.com/blobs.data.gov.sg/parks.geojson",
        "https://s3.ap-southeast-1.amazonaws.com/other-bucket/parks.geojson",
    ],
)
async def test_load_parks_rejects_unsafe_download_url(url):
    source = adapter(lambda _request: httpx.Response(201, json=poll(url)))
    try:
        with pytest.raises(CatalogueSourceError, match="download URL"):
            await source.load_parks()
    finally:
        await source.aclose()


@pytest.mark.asyncio
async def test_load_parks_rejects_non_json_content_type_and_declared_oversize():
    def wrong_type(request: httpx.Request):
        if request.url.path == POLL_PATH:
            return httpx.Response(201, json=poll())
        return httpx.Response(200, content=b"{}", headers={"content-type": "text/html"})

    source = adapter(wrong_type)
    try:
        with pytest.raises(CatalogueSourceError, match="content type"):
            await source.load_parks()
    finally:
        await source.aclose()

    def octet_stream(request: httpx.Request):
        if request.url.path == POLL_PATH:
            return httpx.Response(201, json=poll())
        return httpx.Response(
            200,
            content=json.dumps(collection([feature()])).encode(),
            headers={"content-type": "application/octet-stream"},
        )

    source = adapter(octet_stream)
    try:
        with pytest.raises(CatalogueSourceError, match="content type"):
            await source.load_parks()
    finally:
        await source.aclose()

    def oversized(request: httpx.Request):
        if request.url.path == POLL_PATH:
            return httpx.Response(201, json=poll())
        return httpx.Response(
            200,
            content=b"",
            headers={"content-type": "application/json", "content-length": str(MAX_DOWNLOAD_BYTES + 1)},
        )

    source = adapter(oversized)
    try:
        with pytest.raises(CatalogueSourceError, match="size"):
            await source.load_parks()
    finally:
        await source.aclose()


@pytest.mark.asyncio
async def test_load_parks_accepts_observed_data_gov_binary_content_type():
    def handler(request: httpx.Request):
        if request.url.path == POLL_PATH:
            return httpx.Response(201, json=poll())
        return httpx.Response(
            200,
            content=json.dumps(collection([feature()])).encode(),
            headers={"content-type": "binary/octet-stream"},
        )

    source = adapter(handler)
    try:
        parks = await source.load_parks()
    finally:
        await source.aclose()

    assert [park.source_code for park in parks] == ["P001"]


class OversizedStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"x" * (MAX_DOWNLOAD_BYTES // 2 + 1)
        yield b"x" * (MAX_DOWNLOAD_BYTES // 2 + 1)


class BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'{"type":"FeatureCollection",'
        raise httpx.ReadError("stream disconnected")


@pytest.mark.asyncio
async def test_load_parks_rejects_streamed_oversize():
    def handler(request: httpx.Request):
        if request.url.path == POLL_PATH:
            return httpx.Response(201, json=poll())
        return httpx.Response(
            200,
            stream=OversizedStream(),
            headers={"content-type": "application/geo+json"},
        )

    source = adapter(handler)
    try:
        with pytest.raises(CatalogueSourceError, match="size"):
            await source.load_parks()
    finally:
        await source.aclose()


@pytest.mark.asyncio
async def test_load_parks_retries_midstream_failure_and_raises_catalogue_error():
    download_attempts = 0

    def handler(request: httpx.Request):
        nonlocal download_attempts
        if request.url.path == POLL_PATH:
            return httpx.Response(201, json=poll())
        download_attempts += 1
        return httpx.Response(
            200,
            stream=BrokenStream(),
            headers={"content-type": "application/geo+json"},
        )

    source = adapter(handler, max_retries=2)
    try:
        with pytest.raises(CatalogueSourceError, match="ReadError"):
            await source.load_parks()
    finally:
        await source.aclose()

    assert download_attempts == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"type": "Feature", "features": []}, "FeatureCollection"),
        (collection([]), "empty"),
        (collection([{"type": "Feature", "properties": {}, "geometry": feature()["geometry"]}]), "identity"),
        (collection([feature(code="", name="")]), "identity"),
        (collection([feature(code=123, name="West Coast Park")]), "identity"),
        (collection([feature(code="P001", name=123)]), "identity"),
        (collection([feature(), feature()]), "duplicate"),
        (collection([feature(geometry={"type": "Point", "coordinates": [103.8, 1.3]})]), "geometry"),
        (collection([feature(geometry={"type": "Polygon", "coordinates": "broken"})]), "coordinates"),
        (
            collection(
                [feature(geometry={"type": "Polygon", "coordinates": [[[103.8, 1.3], [103.81, 1.3], [103.8, 1.31]]]})]
            ),
            "coordinates",
        ),
        (
            collection(
                [feature(geometry={"type": "Polygon", "coordinates": [[[103.8, 1.3], [103.81, 1.3], [103.8, 1.31], [103.81, 1.3]]]})]
            ),
            "coordinates",
        ),
        (
            collection(
                [feature(geometry={"type": "Polygon", "coordinates": [[[104.2, 1.3], [104.2, 1.31], [104.21, 1.3], [104.2, 1.3]]]} )]
            ),
            "Singapore",
        ),
    ],
)
async def test_load_parks_rejects_schema_drift_and_incomplete_snapshot(body, message):
    def handler(request: httpx.Request):
        if request.url.path == POLL_PATH:
            return httpx.Response(201, json=poll())
        return httpx.Response(
            200,
            content=json.dumps(body).encode(),
            headers={"content-type": "application/json"},
        )

    source = adapter(handler)
    try:
        with pytest.raises(CatalogueSourceError, match=message):
            await source.load_parks()
    finally:
        await source.aclose()
