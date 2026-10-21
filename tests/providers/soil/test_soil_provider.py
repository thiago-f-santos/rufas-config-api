import json

import h3
import pytest

from rufas_config_api.domain import Location
from rufas_config_api.domain.soil import SoilProfileDomain
from rufas_config_api.providers.soil import SoilProvider, SoilService
from rufas_config_api.providers.soil.adapters.sqlite_memory import SqliteMemorySoilRepository
from rufas_config_api.providers.soil.search import haversine_km

LOCATION = Location(-16.68, -49.25)


@pytest.fixture
async def provider():
    repo = SqliteMemorySoilRepository()
    repo.init_db()
    cell = h3.latlng_to_cell(-16.68, -49.25, 6)
    await repo.add_coverage_cells([cell], region="GO_DF")
    profile = SoilProfileDomain(
        id="go_test_a",
        name="Latossolo Teste",
        latitude=-16.68,
        longitude=-49.25,
        h3_cell=cell,
        soil_data={"_nota": "solo genérico", "profile_id": "go_test_a"},
        provenance={"source": "test", "profile_id": "go_test_a"},
    )
    await repo.save_profile(profile)
    await repo.map_cell_to_profile(cell, "go_test_a")
    service = SoilService(repo, max_distance_km=300.0, warning_distance_km=50.0)
    yield SoilProvider(service)
    repo.close()


@pytest.mark.asyncio
async def test_returns_profile_soil_json(provider):
    result = await provider.build(LOCATION)

    [soil_file] = result.files
    assert result.provider == "soil"
    assert soil_file.path == "soil.json"
    assert soil_file.provider == "soil"
    assert json.loads(soil_file.content) == {"_nota": "solo genérico", "profile_id": "go_test_a"}


@pytest.mark.asyncio
async def test_records_provenance(provider):
    cell = h3.latlng_to_cell(-16.68, -49.25, 6)

    result = await provider.build(LOCATION)

    assert result.provenance == {
        "source": "rufas-config-api dynamic soil database",
        "match_type": "exact",
        "h3": {"resolution": 6, "request_cell": cell, "profile_cell": cell},
        "profile_id": "go_test_a",
        "distance_km": 0.0,
        "warning": None,
        "profile_provenance": {"source": "test", "profile_id": "go_test_a"},
    }


@pytest.mark.asyncio
async def test_records_rounded_distance_and_fallback(provider):
    # Location slightly away from profile cell, in an adjacent cell within coverage
    location = Location(-16.55, -49.25)
    req_cell = h3.latlng_to_cell(location.latitude, location.longitude, 6)
    await provider._soil_service.repo.add_coverage_cells([req_cell], region="GO_DF")

    result = await provider.build(location)

    assert result.provenance["profile_id"] == "go_test_a"
    assert result.provenance["match_type"] == "fallback_nearest"
    assert result.provenance["distance_km"] == round(
        haversine_km(-16.55, -49.25, -16.68, -49.25), 3
    )
    assert result.provenance["h3"]["request_cell"] == req_cell
    assert result.provenance["h3"]["profile_cell"] == h3.latlng_to_cell(-16.68, -49.25, 6)
