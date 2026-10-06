from collections.abc import Sequence
from typing import Any

import httpx

from rufas_config_api.domain import Location, Period
from rufas_config_api.errors import UpstreamError, UpstreamTimeoutError

DAILY_POINT_PATH = "/api/temporal/daily/point"
AGROCLIMATOLOGY_COMMUNITY = "AG"
DATE_FORMAT = "%Y%m%d"


class NasaPowerClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str, timeout_seconds: float) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    @property
    def endpoint_url(self) -> str:
        return f"{self._base_url}{DAILY_POINT_PATH}"

    def query_params(
        self, location: Location, period: Period, parameters: Sequence[str]
    ) -> dict[str, str | float]:
        return {
            "parameters": ",".join(parameters),
            "community": AGROCLIMATOLOGY_COMMUNITY,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "start": period.start.strftime(DATE_FORMAT),
            "end": period.end.strftime(DATE_FORMAT),
            "format": "JSON",
        }

    async def fetch_daily(
        self, location: Location, period: Period, parameters: Sequence[str]
    ) -> dict[str, Any]:
        response = await self._get(self.query_params(location, period, parameters))
        if response.is_error:
            raise UpstreamError(
                f"NASA POWER responded with HTTP {response.status_code}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as error:
            raise UpstreamError("NASA POWER returned an invalid JSON body") from error

    async def _get(self, params: dict[str, str | float]) -> httpx.Response:
        try:
            return await self._http.get(
                self.endpoint_url, params=params, timeout=self._timeout_seconds
            )
        except httpx.TimeoutException as error:
            raise UpstreamTimeoutError(self._timeout_seconds) from error
        except httpx.HTTPError as error:
            raise UpstreamError(f"Could not reach NASA POWER: {error}") from error
