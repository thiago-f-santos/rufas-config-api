import io
import json
import zipfile
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from rufas_config_api.api.dependencies import get_today
from rufas_config_api.config import Settings
from rufas_config_api.main import create_app

BASE_URL = "https://power.test"
NASA_ENDPOINT = f"{BASE_URL}/api/temporal/daily/point"
TODAY = date(2026, 10, 5)
QUERY = {"latitude": -16.36, "longitude": -49.49, "start_year": 2020, "end_year": 2020}


@pytest.fixture
def client(respx_mock, soil_catalog_path):
    settings = Settings(
        nasa_power_base_url=BASE_URL,
        nasa_timeout_seconds=5,
        soil_catalog_path=soil_catalog_path,
    )
    app = create_app(settings)
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


def mock_nasa(respx_mock, response: httpx.Response | None = None, side_effect=None):
    return respx_mock.get(NASA_ENDPOINT).mock(return_value=response, side_effect=side_effect)


def read_zip(response) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_returns_zip_with_rufas_inputs(client, respx_mock, nasa_payload):
    payload = nasa_payload(date(2020, 1, 1), date(2020, 12, 31))
    mock_nasa(respx_mock, httpx.Response(200, json=payload))

    response = client.get("/inputs", params=QUERY)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="rufas_inputs_-16.36_-49.49_2020_2020.zip"'
    )
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == [
            "manifest.json",
            "provenance.json",
            "soil.json",
            "weather.csv",
        ]
        weather_lines = archive.read("weather.csv").decode().splitlines()
        provenance = json.loads(archive.read("provenance.json"))
    assert weather_lines[0] == "year,jday,precip,high,low,avg,Hday,irrigation"
    assert len(weather_lines) == 1 + 366
    assert provenance["request"]["include"] == ["weather", "soil"]


def test_repeated_include_selects_weather(client, respx_mock, nasa_payload):
    payload = nasa_payload(date(2020, 1, 1), date(2020, 12, 31))
    mock_nasa(respx_mock, httpx.Response(200, json=payload))

    response = client.get("/inputs", params={**QUERY, "include": ["weather", "weather"]})

    assert response.status_code == 200


def test_unknown_include_is_rejected(client):
    response = client.get("/inputs", params={**QUERY, "include": ["animal"]})

    assert response.status_code == 422
    assert response.json() == {"detail": {"unknown": ["animal"], "available": ["weather", "soil"]}}


def test_soil_only(client, respx_mock, soil_data_dir):
    params = {**QUERY, "latitude": -16.68, "longitude": -49.25, "include": ["soil"]}

    response = client.get("/inputs", params=params)

    assert response.status_code == 200
    files = read_zip(response)
    assert sorted(files) == ["manifest.json", "provenance.json", "soil.json"]
    assert (
        files["soil.json"] == (soil_data_dir / "profiles" / "go_test_a" / "soil.json").read_bytes()
    )
    provenance = json.loads(files["provenance.json"])
    assert provenance["request"]["include"] == ["soil"]
    assert provenance["providers"]["soil"]["profile_id"] == "go_test_a"
    assert respx_mock.calls.call_count == 0


def test_soil_outside_coverage_is_rejected(client):
    params = {**QUERY, "latitude": -12.97, "longitude": -38.5, "include": ["soil"]}

    response = client.get("/inputs", params=params)

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "message": "Location is outside the soil catalog coverage (GO+DF)",
            "latitude": -12.97,
            "longitude": -38.5,
            "coverage": "GO+DF",
        }
    }


@pytest.mark.parametrize(
    "overrides",
    [{"latitude": 91}, {"longitude": -181}, {"start_year": 1980}, {"end_year": 2027}],
)
def test_invalid_query_is_rejected(client, overrides):
    response = client.get("/inputs", params={**QUERY, **overrides})

    assert response.status_code == 422


def test_missing_upstream_values_are_rejected(client, respx_mock, nasa_payload):
    payload = nasa_payload(
        date(2020, 1, 1), date(2020, 12, 31), missing=[(date(2020, 12, 31), "T2M")]
    )
    mock_nasa(respx_mock, httpx.Response(200, json=payload))

    response = client.get("/inputs", params=QUERY)

    assert response.status_code == 422
    assert response.json()["detail"]["missing"] == [{"date": "2020-12-31", "variables": ["T2M"]}]


def test_upstream_failure_is_a_bad_gateway(client, respx_mock):
    mock_nasa(respx_mock, httpx.Response(500))

    response = client.get("/inputs", params=QUERY)

    assert response.status_code == 502


def test_upstream_timeout_is_a_gateway_timeout(client, respx_mock):
    mock_nasa(respx_mock, side_effect=httpx.ReadTimeout("slow"))

    response = client.get("/inputs", params=QUERY)

    assert response.status_code == 504
