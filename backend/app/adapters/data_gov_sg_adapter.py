"""Strict reader for Sport Singapore's Sport Facilities dataset."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx


SPORT_FACILITIES_RESOURCE_ID = "d_2cfb0867cdeb2b7303068995699dc33b"
REQUIRED_COLUMNS = {
    "_id",
    "VenueName",
    "PostalCode",
    "Latitude",
    "Longitude",
    "SportsFacility",
}


class CatalogueSourceError(Exception):
    """The upstream catalogue was unavailable, incomplete, or incompatible."""


@dataclass(frozen=True)
class SourceFacilityRow:
    source_row_id: int
    venue_name: str
    postal_code: str
    latitude: float
    longitude: float
    sports_facility: str


class DataGovSgAdapter:
    def __init__(
        self,
        *,
        base_url: str = "https://data.gov.sg",
        resource_id: str = SPORT_FACILITIES_RESOURCE_ID,
        client: httpx.AsyncClient | None = None,
        page_size: int = 1000,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        retry_delay_seconds: float = 3.5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._resource_id = resource_id
        self._page_size = page_size
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def load_facilities(self) -> list[SourceFacilityRow]:
        rows: list[SourceFacilityRow] = []
        seen_row_ids: set[int] = set()
        seen_urls: set[str] = set()
        next_url = f"{self._base_url}/api/action/datastore_search"
        next_params: dict[str, str] | None = {
            "resource_id": self._resource_id,
            "limit": str(self._page_size),
        }
        expected_total: int | None = None

        while True:
            request_key = str(
                httpx.URL(next_url, params=next_params)
                if next_params is not None
                else httpx.URL(next_url)
            )
            if request_key in seen_urls:
                raise CatalogueSourceError("catalogue pagination returned a duplicate page")
            seen_urls.add(request_key)

            response = await self._get_with_retry(next_url, params=next_params)
            body = self._decode_body(response)
            result = body.get("result")
            if body.get("success") is not True or not isinstance(result, dict):
                raise CatalogueSourceError("catalogue reported an unsuccessful response")

            self._validate_schema(result)
            try:
                page_total = int(result["total"])
                records = result["records"]
            except (KeyError, TypeError, ValueError) as exc:
                raise CatalogueSourceError("catalogue response metadata is invalid") from exc
            if not isinstance(records, list) or page_total < 0:
                raise CatalogueSourceError("catalogue response metadata is invalid")
            if expected_total is None:
                expected_total = page_total
            elif expected_total != page_total:
                raise CatalogueSourceError("catalogue total changed during pagination")

            for raw in records:
                item = self._parse_row(raw)
                if item.source_row_id in seen_row_ids:
                    raise CatalogueSourceError("catalogue pagination returned a duplicate source row")
                seen_row_ids.add(item.source_row_id)
                rows.append(item)

            if len(rows) == expected_total:
                return rows
            if len(rows) > expected_total:
                raise CatalogueSourceError("catalogue returned more rows than its declared total")

            links = result.get("_links")
            next_link = links.get("next") if isinstance(links, dict) else None
            if not isinstance(next_link, str) or not next_link:
                raise CatalogueSourceError("catalogue response was truncated before the declared total")
            candidate = urljoin(f"{self._base_url}/", next_link)
            if urlsplit(candidate).netloc != urlsplit(self._base_url).netloc:
                raise CatalogueSourceError("catalogue pagination pointed to an unexpected host")
            next_url = candidate
            next_params = None

    async def _get_with_retry(
        self,
        url: str,
        *,
        params: dict[str, str] | None,
    ) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                if attempt == self._max_retries:
                    raise CatalogueSourceError(
                        f"catalogue request failed: {type(exc).__name__}"
                    ) from exc
            else:
                if response.status_code != 429 and response.status_code < 500:
                    if response.status_code >= 400:
                        raise CatalogueSourceError(f"catalogue request returned HTTP {response.status_code}")
                    return response
                if attempt == self._max_retries:
                    raise CatalogueSourceError(
                        f"catalogue request returned HTTP {response.status_code}"
                    )
            if self._retry_delay_seconds:
                await asyncio.sleep(self._retry_delay_seconds * (attempt + 1))
        raise AssertionError("retry loop exhausted")

    @staticmethod
    def _decode_body(response: httpx.Response) -> dict:
        try:
            body = response.json()
        except ValueError as exc:
            raise CatalogueSourceError("catalogue response was not valid JSON") from exc
        if not isinstance(body, dict):
            raise CatalogueSourceError("catalogue response JSON must be an object")
        return body

    @staticmethod
    def _validate_schema(result: dict) -> None:
        fields = result.get("fields")
        if not isinstance(fields, list):
            raise CatalogueSourceError("catalogue response omitted its field schema")
        available = {field.get("id") for field in fields if isinstance(field, dict)}
        missing = sorted(REQUIRED_COLUMNS - available)
        if missing:
            raise CatalogueSourceError(
                f"catalogue field schema is missing: {', '.join(missing)}"
            )

    @staticmethod
    def _parse_row(raw: object) -> SourceFacilityRow:
        if not isinstance(raw, dict):
            raise CatalogueSourceError("catalogue row must be an object")
        try:
            row_id = int(raw["_id"])
            latitude = float(raw["Latitude"])
            longitude = float(raw["Longitude"])
        except KeyError as exc:
            raise CatalogueSourceError(f"catalogue row is missing {exc.args[0]}") from exc
        except (TypeError, ValueError) as exc:
            coordinate = "Latitude" if _cannot_parse_number(raw.get("Latitude")) else "Longitude"
            raise CatalogueSourceError(f"catalogue row has invalid {coordinate}") from exc
        return SourceFacilityRow(
            source_row_id=row_id,
            venue_name=str(raw.get("VenueName") or ""),
            postal_code=str(raw.get("PostalCode") or ""),
            latitude=latitude,
            longitude=longitude,
            sports_facility=str(raw.get("SportsFacility") or ""),
        )


def _cannot_parse_number(value: object) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return True
    return False
