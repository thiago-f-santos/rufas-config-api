import h3
import pytest
from fastapi.testclient import TestClient

from rufas_config_api.config import Settings
from rufas_config_api.main import create_app


@pytest.fixture
def test_app(soil_catalog_path):
    settings = Settings(
        soil_catalog_path=soil_catalog_path,
        database_url="sqlite:///:memory:",
    )
    return create_app(settings)


@pytest.fixture
def client(test_app):
    with TestClient(test_app) as test_client:
        yield test_client


def _valid_soil_payload(
    profile_id: str = "new_farm_01",
    latitude: float = -17.49,
    longitude: float = -51.39,
) -> dict:
    return {
        "id": profile_id,
        "name": "Fazenda Boa Esperança",
        "latitude": latitude,
        "longitude": longitude,
        "soil_data": {
            "soil_layers": [
                {
                    "bottom_depth": 20,
                    "clay_fraction": 0.60,
                    "silt_fraction": 0.20,
                    "sand_fraction": 0.20,
                    "bulk_density": 1.2,
                    "saturated_hydraulic_conductivity": 100.0,
                    "wilting_point_water_concentration": 0.15,
                    "field_capacity_water_concentration": 0.25,
                    "saturation_point_water_concentration": 0.45,
                }
            ]
        },
        "provenance": {"source": "manual entry"},
    }


def test_create_soil_profile_auto_maps_h3_cell(client, test_app):
    payload = _valid_soil_payload()
    response = client.post("/soils/profiles", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "new_farm_01"
    expected_cell = h3.latlng_to_cell(-17.49, -51.39, 6)
    assert data["h3_cell"] == expected_cell
    assert data["name"] == "Fazenda Boa Esperança"
    assert data["latitude"] == -17.49
    assert data["longitude"] == -51.39
    assert len(data["soil_data"]["soil_layers"]) == 1
    assert data["provenance"] == {"source": "manual entry"}

    # Verify lookup by ID
    get_res = client.get("/soils/profiles/new_farm_01")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == "new_farm_01"


def test_create_soil_profile_extra_fields_preserved(client):
    payload = _valid_soil_payload("extra_fields_profile")
    payload["soil_data"]["extra_property"] = "custom_soil_param"
    payload["soil_data"]["soil_layers"][0]["pH"] = 6.5
    payload["provenance"]["author"] = "Agronomist 1"

    response = client.post("/soils/profiles", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["soil_data"]["extra_property"] == "custom_soil_param"
    assert data["soil_data"]["soil_layers"][0]["pH"] == 6.5
    assert data["provenance"]["author"] == "Agronomist 1"


def test_create_soil_profile_validation_error_fractions_sum(client):
    payload = _valid_soil_payload("invalid_fractions")
    # Fractions sum = 0.50 + 0.20 + 0.20 = 0.90 (diff > 0.01)
    payload["soil_data"]["soil_layers"][0]["clay_fraction"] = 0.50

    response = client.post("/soils/profiles", json=payload)
    assert response.status_code == 422


def test_create_soil_profile_fractions_tolerance_boundaries(client):
    # Sum = 0.99 (diff 0.01) -> Valid
    payload_99 = _valid_soil_payload("tol_099")
    payload_99["soil_data"]["soil_layers"][0]["clay_fraction"] = 0.59
    assert client.post("/soils/profiles", json=payload_99).status_code == 201

    # Sum = 1.01 (diff 0.01) -> Valid
    payload_101 = _valid_soil_payload("tol_101")
    payload_101["soil_data"]["soil_layers"][0]["clay_fraction"] = 0.61
    assert client.post("/soils/profiles", json=payload_101).status_code == 201

    # Sum = 0.98 (diff 0.02) -> Invalid
    payload_98 = _valid_soil_payload("tol_098")
    payload_98["soil_data"]["soil_layers"][0]["clay_fraction"] = 0.58
    assert client.post("/soils/profiles", json=payload_98).status_code == 422

    # Sum = 1.02 (diff 0.02) -> Invalid
    payload_102 = _valid_soil_payload("tol_102")
    payload_102["soil_data"]["soil_layers"][0]["clay_fraction"] = 0.62
    assert client.post("/soils/profiles", json=payload_102).status_code == 422


def test_create_soil_profile_validation_error_moisture_order(client):
    # Case 1: wilting_point >= field_capacity
    payload1 = _valid_soil_payload("invalid_moisture_1")
    payload1["soil_data"]["soil_layers"][0]["wilting_point_water_concentration"] = 0.30
    payload1["soil_data"]["soil_layers"][0]["field_capacity_water_concentration"] = 0.25
    response1 = client.post("/soils/profiles", json=payload1)
    assert response1.status_code == 422

    # Case 2: field_capacity >= saturation_point
    payload2 = _valid_soil_payload("invalid_moisture_2")
    payload2["soil_data"]["soil_layers"][0]["field_capacity_water_concentration"] = 0.50
    payload2["soil_data"]["soil_layers"][0]["saturation_point_water_concentration"] = 0.45
    response2 = client.post("/soils/profiles", json=payload2)
    assert response2.status_code == 422

    # Case 3: wilting_point <= 0
    payload3 = _valid_soil_payload("invalid_moisture_3")
    payload3["soil_data"]["soil_layers"][0]["wilting_point_water_concentration"] = 0.0
    response3 = client.post("/soils/profiles", json=payload3)
    assert response3.status_code == 422


def test_create_soil_profile_validation_error_empty_layers(client):
    payload = _valid_soil_payload("empty_layers")
    payload["soil_data"]["soil_layers"] = []
    response = client.post("/soils/profiles", json=payload)
    assert response.status_code == 422


def test_create_soil_profile_validation_error_coordinates(client):
    payload = _valid_soil_payload("bad_coords")
    payload["latitude"] = 95.0
    response = client.post("/soils/profiles", json=payload)
    assert response.status_code == 422

    payload["latitude"] = -17.49
    payload["longitude"] = 200.0
    response2 = client.post("/soils/profiles", json=payload)
    assert response2.status_code == 422


def test_get_soil_profile_not_found(client):
    response = client.get("/soils/profiles/non_existent_profile")
    assert response.status_code == 404


def test_update_soil_profile_success(client):
    payload = _valid_soil_payload("update_test_farm", latitude=-16.50, longitude=-49.30)
    res = client.post("/soils/profiles", json=payload)
    assert res.status_code == 201

    old_cell = res.json()["h3_cell"]
    assert old_cell == h3.latlng_to_cell(-16.50, -49.30, 6)

    # Update name and coordinates
    new_lat = -17.80
    new_lon = -50.90
    update_payload = {
        "name": "Fazenda Boa Esperança (Atualizada)",
        "latitude": new_lat,
        "longitude": new_lon,
    }
    update_res = client.put("/soils/profiles/update_test_farm", json=update_payload)
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["name"] == "Fazenda Boa Esperança (Atualizada)"
    assert updated_data["latitude"] == new_lat
    assert updated_data["longitude"] == new_lon
    new_cell = h3.latlng_to_cell(new_lat, new_lon, 6)
    assert updated_data["h3_cell"] == new_cell
    assert updated_data["h3_cell"] != old_cell

    # Check GET returns the updated profile
    get_res = client.get("/soils/profiles/update_test_farm")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Fazenda Boa Esperança (Atualizada)"


def test_update_soil_profile_without_lat_lon_preserves_cell(client):
    payload = _valid_soil_payload("update_no_coords", latitude=-16.50, longitude=-49.30)
    res = client.post("/soils/profiles", json=payload)
    assert res.status_code == 201

    old_cell = res.json()["h3_cell"]

    update_res = client.put(
        "/soils/profiles/update_no_coords",
        json={"name": "Apenas Novo Nome"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Apenas Novo Nome"
    assert update_res.json()["h3_cell"] == old_cell
    assert update_res.json()["latitude"] == -16.50
    assert update_res.json()["longitude"] == -49.30


def test_update_soil_profile_not_found(client):
    update_payload = {"name": "Nome Fantasma"}
    response = client.put("/soils/profiles/non_existent_profile", json=update_payload)
    assert response.status_code == 404


def test_delete_soil_profile_success(client):
    payload = _valid_soil_payload("delete_test_farm")
    res = client.post("/soils/profiles", json=payload)
    assert res.status_code == 201

    delete_res = client.delete("/soils/profiles/delete_test_farm")
    assert delete_res.status_code == 204

    get_res = client.get("/soils/profiles/delete_test_farm")
    assert get_res.status_code == 404


def test_delete_soil_profile_not_found(client):
    response = client.delete("/soils/profiles/non_existent_profile")
    assert response.status_code == 404
