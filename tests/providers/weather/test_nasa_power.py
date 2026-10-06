from datetime import date

import httpx
import pytest

from rufas_config_api.domain import Location, Period
from rufas_config_api.errors import UpstreamError, UpstreamTimeoutError
from rufas_config_api.providers.weather.nasa_power import NasaPowerClient

BASE_URL = "https://power.test"
ENDPOINT = f"{BASE_URL}/api/temporal/daily/point"
LOCATION = Location(-16.36, -49.49)
PERIOD = Period(date(2024, 1, 1), date(2024, 1, 31), date(2024, 1, 31))
PARAMETERS = ("T2M", "PRECTOTCORR")


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http:
        yield NasaPowerClient(http, BASE_URL, timeout_seconds=5.0)


async def test_requests_daily_agroclimatology_point(client, respx_mock):
    route = respx_mock.get(ENDPOINT).mock(return_value=httpx.Response(200, json={"ok": True}))

    payload = await client.fetch_daily(LOCATION, PERIOD, PARAMETERS)

    assert payload == {"ok": True}
    assert dict(route.calls.last.request.url.params) == {
        "parameters": "T2M,PRECTOTCORR",
        "community": "AG",
        "latitude": "-16.36",
        "longitude": "-49.49",
        "start": "20240101",
        "end": "20240131",
        "format": "JSON",
    }


async def test_error_status_becomes_upstream_error(client, respx_mock):
    respx_mock.get(ENDPOINT).mock(return_value=httpx.Response(503))

    with pytest.raises(UpstreamError, match="HTTP 503") as raised:
        await client.fetch_daily(LOCATION, PERIOD, PARAMETERS)

    assert raised.value.status_code == 503


async def test_invalid_json_becomes_upstream_error(client, respx_mock):
    respx_mock.get(ENDPOINT).mock(return_value=httpx.Response(200, text="not json"))

    with pytest.raises(UpstreamError, match="invalid JSON"):
        await client.fetch_daily(LOCATION, PERIOD, PARAMETERS)


async def test_connection_failure_becomes_upstream_error(client, respx_mock):
    respx_mock.get(ENDPOINT).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(UpstreamError, match="Could not reach NASA POWER"):
        await client.fetch_daily(LOCATION, PERIOD, PARAMETERS)


async def test_timeout_becomes_upstream_timeout(client, respx_mock):
    respx_mock.get(ENDPOINT).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(UpstreamTimeoutError) as raised:
        await client.fetch_daily(LOCATION, PERIOD, PARAMETERS)

    assert raised.value.timeout_seconds == 5.0
