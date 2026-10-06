from collections.abc import Mapping, Sequence
from typing import Any

from rufas_config_api.clock import Clock, utc_now
from rufas_config_api.domain import Location, PackageFile, Period, ProviderResult
from rufas_config_api.providers.weather.nasa_power import NasaPowerClient
from rufas_config_api.providers.weather.transform import (
    NASA_TO_RUFAS_COLUMNS,
    to_csv,
    to_rufas_rows,
)

ELEVATION_INDEX = 2


class WeatherProvider:
    name = "weather"
    FILE_NAME = "weather.csv"
    SOURCE = "NASA POWER"

    def __init__(self, client: NasaPowerClient, lag_days: int, clock: Clock = utc_now) -> None:
        self._client = client
        self._lag_days = lag_days
        self._clock = clock

    async def build(self, location: Location, period: Period) -> ProviderResult:
        parameters = tuple(NASA_TO_RUFAS_COLUMNS)
        payload = await self._client.fetch_daily(location, period, parameters)
        rows = to_rufas_rows(payload, period)
        weather_file = PackageFile(self.FILE_NAME, to_csv(rows), provider=self.name)
        provenance = self._provenance(location, period, parameters, payload)
        return ProviderResult(self.name, (weather_file,), provenance)

    def _provenance(
        self,
        location: Location,
        period: Period,
        parameters: Sequence[str],
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        header = payload.get("header", {})
        coordinates = payload.get("geometry", {}).get("coordinates", [])
        return {
            "source": self.SOURCE,
            "endpoint": self._client.endpoint_url,
            "query": self._client.query_params(location, period, parameters),
            "requested_period": {
                "start": period.start.isoformat(),
                "end": period.requested_end.isoformat(),
            },
            "effective_period": {
                "start": period.start.isoformat(),
                "end": period.end.isoformat(),
            },
            "truncated": period.truncated,
            "lag_days": self._lag_days,
            "api_version": header.get("api", {}).get("version"),
            "upstream_sources": header.get("sources", []),
            "fill_value": header.get("fill_value"),
            "elevation_m": coordinates[ELEVATION_INDEX]
            if len(coordinates) > ELEVATION_INDEX
            else None,
            "retrieved_at": self._clock().isoformat(),
        }
