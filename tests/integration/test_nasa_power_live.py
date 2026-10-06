from datetime import date

import httpx
import pytest

from rufas_config_api.domain import Location, Period
from rufas_config_api.providers.weather import WeatherProvider
from rufas_config_api.providers.weather.nasa_power import NasaPowerClient

pytestmark = pytest.mark.integration


async def test_fetches_one_month_from_nasa_power():
    january = Period(date(2024, 1, 1), date(2024, 1, 31), date(2024, 1, 31))
    async with httpx.AsyncClient() as http:
        client = NasaPowerClient(http, "https://power.larc.nasa.gov", timeout_seconds=60)
        result = await WeatherProvider(client, lag_days=7).build(Location(-16.36, -49.49), january)

    lines = result.files[0].content.decode().splitlines()
    assert lines[0] == "year,jday,precip,high,low,avg,Hday,irrigation"
    assert len(lines) == 1 + 31
