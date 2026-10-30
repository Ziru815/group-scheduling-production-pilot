"""Strict poll-download reader for the official NParks park catalogue."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import math
from urllib.parse import urlsplit

import httpx

from app.adapters.data_gov_sg_adapter import CatalogueSourceError


NPARKS_PARKS_DATASET_ID = "d_77d7ec97be83d44f61b85454f844382f"
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
OFFICIAL_DOWNLOAD_HOSTS = frozenset({"s3.ap-southeast-1.amazonaws.com"})
OFFICIAL_DOWNLOAD_PATH_PREFIX = "/blobs.data.gov.sg/"
ACCEPTED_CONTENT_TYPES = frozenset(
    {
        "application/json",
        "application/geo+json",
        "application/vnd.geo+json",
        # data.gov.sg currently serves the signed GeoJSON blob with this MIME.
        # Host/path, byte-size, JSON schema, identity, and geometry checks still apply.
        "binary/octet-stream",
    }
)


@dataclass(frozen=True)
class ParkSourceFeature:
    source_code: str
    source_name: str
    geometry_type: str
    coordinates: object


class DataGovSgParkAdapter:
    def __init__(
        self,
        *,
        base_url: str = "https://api-open.data.gov.sg",
        dataset_id: str = NPARKS_PARKS_DATASET_ID,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        retry_delay_seconds: float = 3.5,
        max_download_bytes: int = MAX_DOWNLOAD_BYTES,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._dataset_id = dataset_id
        self._api_key = api_key
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._max_download_bytes = max_download_bytes
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def load_parks(self) -> list[ParkSourceFeature]:
        poll_url = (
            f"{self._base_url}/v1/public/api/datasets/"
            f"{self._dataset_id}/poll-download"
        )
        headers = {"x-api-key": self._api_key} if self._api_key else None
        poll_response = await self._get_with_retry(poll_url, headers=headers)
        poll_body = self._decode_json_object(poll_response.content, "poll response")
        download_url = self._download_url(poll_body)
        self._validate_download_url(download_url)

        body = await self._download_with_retry(download_url)
        payload = self._decode_json_object(body, "catalogue download")
        return self._parse_feature_collection(payload)

    async def _download_with_retry(self, url: str) -> bytes:
        for attempt in range(self._max_retries + 1):
            response: httpx.Response | None = None
            try:
                request = self._client.build_request("GET", url)
                response = await self._client.send(request, stream=True)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == self._max_retries:
                        raise CatalogueSourceError(
                            f"catalogue request returned HTTP {response.status_code}"
                        )
                elif response.status_code >= 400:
                    raise CatalogueSourceError(
                        f"catalogue request returned HTTP {response.status_code}"
                    )
                else:
                    self._validate_download_metadata(response)
                    return await self._read_bounded(response)
            except httpx.HTTPError as exc:
                if attempt == self._max_retries:
                    raise CatalogueSourceError(
                        f"catalogue request failed: {type(exc).__name__}"
                    ) from exc
            finally:
                if response is not None:
                    await response.aclose()
            if self._retry_delay_seconds:
                await asyncio.sleep(self._retry_delay_seconds * (attempt + 1))
        raise AssertionError("retry loop exhausted")

    async def _get_with_retry(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        stream: bool = False,
    ) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                request = self._client.build_request("GET", url, headers=headers)
                response = await self._client.send(request, stream=stream)
            except httpx.HTTPError as exc:
                if attempt == self._max_retries:
                    raise CatalogueSourceError(
                        f"catalogue request failed: {type(exc).__name__}"
                    ) from exc
            else:
                if response.status_code != 429 and response.status_code < 500:
                    if response.status_code >= 400:
                        await response.aclose()
                        raise CatalogueSourceError(
                            f"catalogue request returned HTTP {response.status_code}"
                        )
                    return response
                await response.aclose()
                if attempt == self._max_retries:
                    raise CatalogueSourceError(
                        f"catalogue request returned HTTP {response.status_code}"
                    )
            if self._retry_delay_seconds:
                await asyncio.sleep(self._retry_delay_seconds * (attempt + 1))
        raise AssertionError("retry loop exhausted")

    @staticmethod
    def _decode_json_object(body: bytes, context: str) -> dict:
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CatalogueSourceError(f"{context} was not valid JSON") from exc
        if not isinstance(payload, dict):
            raise CatalogueSourceError(f"{context} JSON must be an object")
        return payload

    @staticmethod
    def _download_url(body: dict) -> str:
        data = body.get("data")
        url = data.get("url") if isinstance(data, dict) else None
        if body.get("code") != 0 or not isinstance(url, str) or not url:
            raise CatalogueSourceError("poll response omitted a download URL")
        return url

    @staticmethod
    def _validate_download_url(url: str) -> None:
        parsed = urlsplit(url)
        try:
            port = parsed.port
        except ValueError as exc:
            raise CatalogueSourceError(
                "poll response returned an unsafe download URL"
            ) from exc
        if (
            parsed.scheme != "https"
            or parsed.hostname not in OFFICIAL_DOWNLOAD_HOSTS
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or bool(parsed.fragment)
            or not parsed.path.startswith(OFFICIAL_DOWNLOAD_PATH_PREFIX)
        ):
            raise CatalogueSourceError("poll response returned an unsafe download URL")

    def _validate_download_metadata(self, response: httpx.Response) -> None:
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in ACCEPTED_CONTENT_TYPES:
            raise CatalogueSourceError("catalogue download has an invalid content type")
        declared = response.headers.get("content-length")
        if declared is not None:
            try:
                declared_size = int(declared)
            except ValueError as exc:
                raise CatalogueSourceError("catalogue download size metadata is invalid") from exc
            if declared_size < 0 or declared_size > self._max_download_bytes:
                raise CatalogueSourceError("catalogue download exceeds the size limit")

    async def _read_bounded(self, response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self._max_download_bytes:
                raise CatalogueSourceError("catalogue download exceeds the size limit")
            chunks.append(chunk)
        return b"".join(chunks)

    @classmethod
    def _parse_feature_collection(cls, payload: dict) -> list[ParkSourceFeature]:
        if payload.get("type") != "FeatureCollection":
            raise CatalogueSourceError("catalogue must be a GeoJSON FeatureCollection")
        raw_features = payload.get("features")
        if not isinstance(raw_features, list) or not raw_features:
            raise CatalogueSourceError("official catalogue unexpectedly returned empty")

        parks: list[ParkSourceFeature] = []
        seen_codes: set[str] = set()
        for raw in raw_features:
            if not isinstance(raw, dict) or raw.get("type") != "Feature":
                raise CatalogueSourceError("catalogue feature schema is invalid")
            properties = raw.get("properties")
            if not isinstance(properties, dict):
                raise CatalogueSourceError("catalogue feature identity is missing")
            raw_source_code = properties.get("L_CODE")
            raw_source_name = properties.get("NAME")
            if not isinstance(raw_source_code, str) or not isinstance(
                raw_source_name, str
            ):
                raise CatalogueSourceError("catalogue feature identity is missing")
            source_code = raw_source_code.strip()
            source_name = raw_source_name.strip()
            if not source_code or not source_name:
                raise CatalogueSourceError("catalogue feature identity is missing")
            if source_code in seen_codes:
                raise CatalogueSourceError("catalogue contains a duplicate source identity")
            seen_codes.add(source_code)

            geometry = raw.get("geometry")
            if not isinstance(geometry, dict):
                raise CatalogueSourceError("catalogue feature geometry is invalid")
            geometry_type = geometry.get("type")
            coordinates = geometry.get("coordinates")
            cls._validate_geometry(geometry_type, coordinates)
            parks.append(
                ParkSourceFeature(
                    source_code=source_code,
                    source_name=source_name,
                    geometry_type=geometry_type,
                    coordinates=coordinates,
                )
            )
        return parks

    @classmethod
    def _validate_geometry(cls, geometry_type: object, coordinates: object) -> None:
        if geometry_type not in {"Polygon", "MultiPolygon"}:
            raise CatalogueSourceError("catalogue feature has unsupported geometry")
        polygons = [coordinates] if geometry_type == "Polygon" else coordinates
        if not isinstance(polygons, list) or not polygons:
            raise CatalogueSourceError("catalogue feature has invalid coordinates")
        for polygon in polygons:
            if not isinstance(polygon, list) or not polygon:
                raise CatalogueSourceError("catalogue feature has invalid coordinates")
            for ring in polygon:
                if (
                    not isinstance(ring, list)
                    or len(ring) < 4
                    or ring[0] != ring[-1]
                ):
                    raise CatalogueSourceError("catalogue feature has invalid coordinates")
                for position in ring:
                    cls._validate_position(position)

    @staticmethod
    def _validate_position(position: object) -> None:
        if not isinstance(position, list) or len(position) < 2:
            raise CatalogueSourceError("catalogue feature has invalid coordinates")
        try:
            longitude = float(position[0])
            latitude = float(position[1])
        except (TypeError, ValueError) as exc:
            raise CatalogueSourceError("catalogue feature has invalid coordinates") from exc
        if not math.isfinite(latitude) or not math.isfinite(longitude):
            raise CatalogueSourceError("catalogue feature has invalid coordinates")
        if not (1.1 <= latitude <= 1.5 and 103.6 <= longitude <= 104.1):
            raise CatalogueSourceError("catalogue feature has coordinates outside Singapore")
