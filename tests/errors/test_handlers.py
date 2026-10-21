from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rufas_config_api.errors import (
    InvalidPeriodError,
    MissingDataError,
    MissingValue,
    OutOfCoverageError,
    RufasConfigError,
    SoilCatalogError,
    UnknownProviderError,
    UpstreamError,
    UpstreamTimeoutError,
)
from rufas_config_api.errors.handlers import register_error_handlers


def client_raising(error: Exception) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise error

    return TestClient(app)


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (InvalidPeriodError("end_year is in the future"), 422, "end_year is in the future"),
        (
            UnknownProviderError(["soil"], ["weather"]),
            422,
            {"unknown": ["soil"], "available": ["weather"]},
        ),
        (
            UpstreamError("NASA POWER responded with HTTP 503", status_code=503),
            502,
            {"message": "NASA POWER responded with HTTP 503", "upstream_status": 503},
        ),
        (
            UpstreamTimeoutError(60.0),
            504,
            {"message": "NASA POWER did not respond within 60.0 seconds", "timeout_seconds": 60.0},
        ),
        (
            OutOfCoverageError(-12.97, -38.5, "GO+DF"),
            422,
            {
                "message": "Location is outside the soil catalog coverage (GO+DF)",
                "latitude": -12.97,
                "longitude": -38.5,
                "coverage": "GO+DF",
            },
        ),
        (RufasConfigError("unexpected"), 500, "Internal error while generating inputs"),
        (SoilCatalogError("x"), 500, "Internal error while generating inputs"),
    ],
)
def test_domain_errors_are_translated_to_http(error, status_code, detail):
    response = client_raising(error).get("/boom")

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_missing_data_lists_days_and_variables():
    error = MissingDataError([MissingValue(date(2026, 9, 30), ("T2M", "T2M_MAX"))])

    response = client_raising(error).get("/boom")

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "message": "Upstream has no data for 1 day(s) in the requested period",
            "missing": [{"date": "2026-09-30", "variables": ["T2M", "T2M_MAX"]}],
        }
    }


def test_no_profile_in_range_returns_404():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from rufas_config_api.errors.handlers import register_error_handlers
    from rufas_config_api.errors.request_errors import NoProfileInRangeError

    app = FastAPI()
    register_error_handlers(app)

    @app.get("/test-404")
    def endpoint():
        raise NoProfileInRangeError(-13.5, -46.5, 300.0)

    client = TestClient(app)
    response = client.get("/test-404")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["message"] == "No soil profile within maximum search radius"
    assert data["detail"]["latitude"] == -13.5
    assert data["detail"]["longitude"] == -46.5
    assert data["detail"]["max_distance_km"] == 300.0
