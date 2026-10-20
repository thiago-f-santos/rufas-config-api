from datetime import date

import h3
import pytest

from rufas_config_api.domain import Location, Period
from rufas_config_api.providers.soil import SoilProvider
from rufas_config_api.providers.soil.catalog import SoilCatalog
from rufas_config_api.providers.soil.search import haversine_km

LOCATION = Location(-16.68, -49.25)
PERIOD = Period(date(2020, 1, 1), date(2020, 12, 31), date(2020, 12, 31))


@pytest.fixture
def provider(soil_catalog_path):
    catalog = SoilCatalog.open(soil_catalog_path)
    yield SoilProvider(catalog, max_rings=80)
    catalog.close()


async def test_returns_profile_soil_json_unchanged(provider, soil_data_dir):
    result = await provider.build(LOCATION, PERIOD)

    [soil_file] = result.files
    expected = (soil_data_dir / "profiles" / "go_test_a" / "soil.json").read_bytes()
    assert result.provider == "soil"
    assert soil_file.path == "soil.json"
    assert soil_file.provider == "soil"
    assert soil_file.content == expected
    assert "solo genérico".encode() in soil_file.content
    assert soil_file.content.endswith(b"}\n")


async def test_records_provenance(provider):
    cell = h3.latlng_to_cell(-16.68, -49.25, 6)

    result = await provider.build(LOCATION, PERIOD)

    assert result.provenance == {
        "source": "rufas-config-api soil catalog",
        "method": "h3_ring_nearest",
        "h3": {"resolution": 6, "request_cell": cell, "profile_cell": cell, "ring": 0},
        "profile_id": "go_test_a",
        "profile_location": {"latitude": -16.68, "longitude": -49.25},
        "distance_km": 0.0,
        "profile_provenance": {
            "profile_id": "go_test_a",
            "location": {"latitude": -16.68, "longitude": -49.25},
        },
    }


async def test_records_rounded_distance_to_profile(provider):
    location = Location(-16.66, -49.27)

    result = await provider.build(location, PERIOD)

    assert result.provenance["profile_id"] == "go_test_a"
    assert result.provenance["distance_km"] == round(
        haversine_km(-16.66, -49.27, -16.68, -49.25), 3
    )
