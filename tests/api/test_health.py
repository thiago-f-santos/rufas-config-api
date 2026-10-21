from fastapi.testclient import TestClient

from rufas_config_api.config import Settings
from rufas_config_api.main import create_app


def test_health_reports_ok(soil_catalog_path):
    with TestClient(
        create_app(
            Settings(
                soil_catalog_path=soil_catalog_path,
                database_url="sqlite:///:memory:",
            )
        )
    ) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_startup_succeeds_without_soil_catalog(tmp_path):
    app = create_app(
        Settings(
            soil_catalog_path=tmp_path / "x.sqlite",
            database_url="sqlite:///:memory:",
        )
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert app.state.soil_catalog is None
