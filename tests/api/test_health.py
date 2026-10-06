from fastapi.testclient import TestClient

from rufas_config_api.config import Settings
from rufas_config_api.main import create_app


def test_health_reports_ok():
    with TestClient(create_app(Settings())) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
