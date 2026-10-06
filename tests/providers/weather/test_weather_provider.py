from datetime import UTC, date, datetime

import httpx
import pytest

from rufas_config_api.domain import Location, Period
from rufas_config_api.providers.weather import WeatherProvider
from rufas_config_api.providers.weather.nasa_power import NasaPowerClient

BASE_URL = "https://power.test"
ENDPOINT = f"{BASE_URL}/api/temporal/daily/point"
RETRIEVED_AT = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
LOCATION = Location(-16.36, -49.49)
PERIOD = Period(date(2026, 9, 27), date(2026, 9, 28), date(2026, 12, 31))


@pytest.fixture
async def provider():
    async with httpx.AsyncClient() as http:
        client = NasaPowerClient(http, BASE_URL, timeout_seconds=5.0)
        yield WeatherProvider(client, lag_days=7, clock=lambda: RETRIEVED_AT)


async def test_builds_weather_csv(provider, respx_mock, nasa_payload):
    respx_mock.get(ENDPOINT).mock(
        return_value=httpx.Response(200, json=nasa_payload(PERIOD.start, PERIOD.end))
    )

    result = await provider.build(LOCATION, PERIOD)

    [weather_file] = result.files
    assert result.provider == "weather"
    assert weather_file.path == "weather.csv"
    assert weather_file.provider == "weather"
    assert weather_file.content.decode().splitlines() == [
        "year,jday,precip,high,low,avg,Hday,irrigation",
        "2026,270,1.23,30.5,18.25,24.0,20.13,0",
        "2026,271,1.23,30.5,18.25,24.0,20.13,0",
    ]


async def test_records_provenance(provider, respx_mock, nasa_payload):
    respx_mock.get(ENDPOINT).mock(
        return_value=httpx.Response(200, json=nasa_payload(PERIOD.start, PERIOD.end))
    )

    result = await provider.build(LOCATION, PERIOD)

    assert result.provenance == {
        "source": "NASA POWER",
        "endpoint": ENDPOINT,
        "query": {
            "parameters": "PRECTOTCORR,T2M_MAX,T2M_MIN,T2M,ALLSKY_SFC_SW_DWN",
            "community": "AG",
            "latitude": -16.36,
            "longitude": -49.49,
            "start": "20260927",
            "end": "20260928",
            "format": "JSON",
        },
        "requested_period": {"start": "2026-09-27", "end": "2026-12-31"},
        "effective_period": {"start": "2026-09-27", "end": "2026-09-28"},
        "truncated": True,
        "lag_days": 7,
        "api_version": "v2.10.0",
        "upstream_sources": ["FLASHFLUX", "GEOSIT", "POWER"],
        "fill_value": -999.0,
        "elevation_m": 807.47,
        "retrieved_at": "2026-10-05T12:00:00+00:00",
    }
