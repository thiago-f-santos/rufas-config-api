import h3
import pytest

from rufas_config_api.domain import Location
from rufas_config_api.domain.soil import SoilProfileDomain
from rufas_config_api.errors import NoProfileInRangeError, OutOfCoverageError
from rufas_config_api.providers.soil.adapters.sqlite_memory import SqliteMemorySoilRepository
from rufas_config_api.providers.soil.service import SoilService


@pytest.fixture
async def service():
    repo = SqliteMemorySoilRepository()
    repo.init_db()
    rio_verde_cell = h3.latlng_to_cell(-17.49, -51.39, 6)
    await repo.add_coverage_cells([rio_verde_cell], region="GO_DF")
    profile = SoilProfileDomain(
        id="go_lv_01",
        name="Rio Verde LV",
        latitude=-17.49,
        longitude=-51.39,
        h3_cell=rio_verde_cell,
        soil_data={"soil_layers": []},
        provenance={"source": "test"},
    )
    await repo.save_profile(profile)
    await repo.map_cell_to_profile(rio_verde_cell, "go_lv_01")
    srv = SoilService(repo, max_distance_km=300.0, warning_distance_km=50.0)
    yield srv
    repo.close()


@pytest.mark.asyncio
async def test_tier1_exact_match(service: SoilService):
    match = await service.resolve_soil(Location(-17.49, -51.39))
    assert match.profile.id == "go_lv_01"
    assert match.match_type == "exact"
    assert match.distance_km == 0.0
    assert match.warning is None
    expected_cell = h3.latlng_to_cell(-17.49, -51.39, 6)
    assert match.request_cell == expected_cell


@pytest.mark.asyncio
async def test_out_of_coverage(service: SoilService):
    with pytest.raises(OutOfCoverageError) as exc_info:
        await service.resolve_soil(Location(-12.97, -38.50))  # Salvador, BA
    assert exc_info.value.latitude == -12.97
    assert exc_info.value.longitude == -38.50
    assert exc_info.value.coverage == "GO_DF"


@pytest.mark.asyncio
async def test_no_profile_in_range(service: SoilService):
    repo = service.repo
    far_lat, far_lon = -10.0, -45.0
    far_cell = h3.latlng_to_cell(far_lat, far_lon, 6)
    await repo.add_coverage_cells([far_cell], region="GO_DF")
    with pytest.raises(NoProfileInRangeError) as exc_info:
        await service.resolve_soil(Location(far_lat, far_lon))
    assert exc_info.value.latitude == far_lat
    assert exc_info.value.longitude == far_lon
    assert exc_info.value.max_distance_km == 300.0


@pytest.mark.asyncio
async def test_tier2_fallback_without_warning(service: SoilService):
    repo = service.repo
    nearby_lat, nearby_lon = -17.55, -51.45
    nearby_cell = h3.latlng_to_cell(nearby_lat, nearby_lon, 6)
    await repo.add_coverage_cells([nearby_cell], region="GO_DF")

    match = await service.resolve_soil(Location(nearby_lat, nearby_lon))
    assert match.profile.id == "go_lv_01"
    assert match.match_type == "fallback_nearest"
    assert 0.0 < match.distance_km <= 50.0
    assert match.warning is None
    assert match.request_cell == nearby_cell


@pytest.mark.asyncio
async def test_tier2_fallback_with_warning(service: SoilService):
    repo = service.repo
    farther_lat, farther_lon = -16.60, -51.39
    farther_cell = h3.latlng_to_cell(farther_lat, farther_lon, 6)
    await repo.add_coverage_cells([farther_cell], region="GO_DF")

    match = await service.resolve_soil(Location(farther_lat, farther_lon))
    assert match.profile.id == "go_lv_01"
    assert match.match_type == "fallback_nearest"
    assert match.distance_km > 50.0
    assert match.warning == (
        f"Nearest profile is {match.distance_km:.1f} km away; "
        "local soil characteristics may differ."
    )
    assert match.request_cell == farther_cell


def test_repo_property(service: SoilService):
    assert service.repo is not None
    assert service.repo.is_in_coverage is not None
    assert service.max_distance_km == 300.0
    assert service.warning_distance_km == 50.0
    assert service.resolution == 6


def test_soil_service_exported_from_package():
    from rufas_config_api.providers.soil import SoilService as ExportedService

    assert ExportedService is SoilService


@pytest.mark.asyncio
async def test_fallback_selects_closest_candidate(service: SoilService):
    repo = service.repo
    # Add second profile closer to Rio Verde's neighbor
    closer_profile = SoilProfileDomain(
        id="go_lv_02",
        name="Rio Verde LV Closer",
        latitude=-17.54,
        longitude=-51.44,
        h3_cell=h3.latlng_to_cell(-17.54, -51.44, 6),
        soil_data={"soil_layers": []},
        provenance={"source": "test"},
    )
    await repo.save_profile(closer_profile)

    target_lat, target_lon = -17.55, -51.45
    target_cell = h3.latlng_to_cell(target_lat, target_lon, 6)
    await repo.add_coverage_cells([target_cell], region="GO_DF")

    match = await service.resolve_soil(Location(target_lat, target_lon))
    assert match.profile.id == "go_lv_02"
    assert match.match_type == "fallback_nearest"
    assert match.distance_km < 5.0
