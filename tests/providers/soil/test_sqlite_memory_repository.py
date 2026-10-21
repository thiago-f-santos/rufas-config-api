import asyncio

import pytest

from rufas_config_api.domain.soil import SoilProfileDomain
from rufas_config_api.providers.soil.adapters.sqlite_memory import SqliteMemorySoilRepository
from rufas_config_api.providers.soil.repository import SoilRepository


@pytest.fixture
def repo():
    r = SqliteMemorySoilRepository()
    r.init_db()
    yield r
    r.close()


@pytest.mark.asyncio
async def test_sqlite_memory_coverage_and_exact_match(repo):
    await repo.add_coverage_cells(["868261977ffffff"], region="GO_DF")
    assert await repo.is_in_coverage("868261977ffffff") is True
    assert await repo.is_in_coverage("868261970000000") is False

    profile = SoilProfileDomain(
        id="test_lv_01",
        name="Latossolo Teste",
        latitude=-16.5,
        longitude=-49.2,
        h3_cell="868261977ffffff",
        soil_data={"soil_layers": []},
        provenance={"source": "test"},
    )
    await repo.save_profile(profile)
    await repo.map_cell_to_profile("868261977ffffff", "test_lv_01")

    exact = await repo.get_profile_by_cell("868261977ffffff")
    assert exact is not None
    assert exact.id == "test_lv_01"
    assert exact.name == "Latossolo Teste"
    assert exact.latitude == -16.5
    assert exact.longitude == -49.2
    assert exact.soil_data == {"soil_layers": []}
    assert exact.provenance == {"source": "test"}


@pytest.mark.asyncio
async def test_sqlite_memory_nearest_fallback(repo):
    profile = SoilProfileDomain(
        id="test_lv_01",
        name="Latossolo Teste",
        latitude=-16.5,
        longitude=-49.2,
        h3_cell="868261977ffffff",
        soil_data={"soil_layers": []},
        provenance={"source": "test"},
    )
    await repo.save_profile(profile)

    # Search from a nearby location (-16.55, -49.25)
    match = await repo.find_nearest(-16.55, -49.25, max_distance_km=50.0)
    assert match is not None
    p, dist = match
    assert p.id == "test_lv_01"
    assert 0 < dist < 20.0

    # Search with max_distance_km too small to reach the profile
    too_far = await repo.find_nearest(-16.55, -49.25, max_distance_km=5.0)
    assert too_far is None


@pytest.mark.asyncio
async def test_sqlite_memory_get_profile_by_id(repo):
    profile = SoilProfileDomain(
        id="p_unique_01",
        name="Perfil Unico",
        latitude=-15.0,
        longitude=-47.0,
        h3_cell="868261900ffffff",
        soil_data={"clay": 0.5},
        provenance={"source": "manual"},
    )
    await repo.save_profile(profile)

    found = await repo.get_profile_by_id("p_unique_01")
    assert found is not None
    assert found.id == "p_unique_01"
    assert found.name == "Perfil Unico"
    assert found.soil_data == {"clay": 0.5}

    not_found = await repo.get_profile_by_id("non_existent_id")
    assert not_found is None


@pytest.mark.asyncio
async def test_sqlite_memory_delete_profile_cascades_mappings(repo):
    profile = SoilProfileDomain(
        id="p_to_delete",
        name="Perfil Para Deletar",
        latitude=-16.0,
        longitude=-48.0,
        h3_cell="868261911ffffff",
        soil_data={},
        provenance={},
    )
    await repo.save_profile(profile)
    await repo.map_cell_to_profile("868261911ffffff", "p_to_delete")

    assert await repo.get_profile_by_id("p_to_delete") is not None
    assert await repo.get_profile_by_cell("868261911ffffff") is not None

    deleted = await repo.delete_profile("p_to_delete")
    assert deleted is True

    # Check that profile is gone
    assert await repo.get_profile_by_id("p_to_delete") is None
    # Check that cell mapping cascaded
    assert await repo.get_profile_by_cell("868261911ffffff") is None

    # Deleting again returns False
    assert await repo.delete_profile("p_to_delete") is False


@pytest.mark.asyncio
async def test_sqlite_memory_update_profile(repo):
    p1 = SoilProfileDomain(
        id="p_update",
        name="Versao 1",
        latitude=-16.0,
        longitude=-48.0,
        h3_cell="868261911ffffff",
        soil_data={"v": 1},
        provenance={"author": "A"},
    )
    await repo.save_profile(p1)

    p2 = SoilProfileDomain(
        id="p_update",
        name="Versao 2",
        latitude=-16.1,
        longitude=-48.1,
        h3_cell="868261922ffffff",
        soil_data={"v": 2},
        provenance={"author": "B"},
    )
    await repo.save_profile(p2)

    updated = await repo.get_profile_by_id("p_update")
    assert updated is not None
    assert updated.name == "Versao 2"
    assert updated.latitude == -16.1
    assert updated.longitude == -48.1
    assert updated.h3_cell == "868261922ffffff"
    assert updated.soil_data == {"v": 2}
    assert updated.provenance == {"author": "B"}


@pytest.mark.asyncio
async def test_sqlite_memory_remapping_cell(repo):
    p1 = SoilProfileDomain(
        id="p1",
        name="P1",
        latitude=-16.0,
        longitude=-48.0,
        h3_cell="cell_shared",
        soil_data={},
        provenance={},
    )
    p2 = SoilProfileDomain(
        id="p2",
        name="P2",
        latitude=-16.1,
        longitude=-48.1,
        h3_cell="cell_shared",
        soil_data={},
        provenance={},
    )
    await repo.save_profile(p1)
    await repo.save_profile(p2)

    await repo.map_cell_to_profile("cell_shared", "p1")
    assert (await repo.get_profile_by_cell("cell_shared")).id == "p1"

    await repo.map_cell_to_profile("cell_shared", "p2")
    assert (await repo.get_profile_by_cell("cell_shared")).id == "p2"


@pytest.mark.asyncio
async def test_sqlite_memory_unmap_cell(repo):
    p = SoilProfileDomain(
        id="p_unmap",
        name="P Unmap",
        latitude=-16.0,
        longitude=-48.0,
        h3_cell="cell_unmap",
        soil_data={},
        provenance={},
    )
    await repo.save_profile(p)
    await repo.map_cell_to_profile("cell_unmap", "p_unmap")
    assert (await repo.get_profile_by_cell("cell_unmap")) is not None

    unmapped = await repo.unmap_cell_from_profile("cell_unmap", "p_unmap")
    assert unmapped is True
    assert (await repo.get_profile_by_cell("cell_unmap")) is None

    # Unmapping non-existent mapping returns False
    assert await repo.unmap_cell_from_profile("cell_unmap", "p_unmap") is False


@pytest.mark.asyncio
async def test_sqlite_memory_protocol_conformance(repo):
    assert isinstance(repo, SoilRepository)


@pytest.mark.asyncio
async def test_sqlite_memory_concurrent_access(repo):
    profiles = [
        SoilProfileDomain(
            id=f"concurrent_{i}",
            name=f"Profile {i}",
            latitude=-16.0 + (i * 0.01),
            longitude=-48.0 + (i * 0.01),
            h3_cell=f"cell_{i}",
            soil_data={"idx": i},
            provenance={},
        )
        for i in range(10)
    ]

    await asyncio.gather(*(repo.save_profile(p) for p in profiles))
    results = await asyncio.gather(*(repo.get_profile_by_id(f"concurrent_{i}") for i in range(10)))
    assert all(r is not None for r in results)
    assert [r.id for r in results] == [f"concurrent_{i}" for i in range(10)]


@pytest.mark.asyncio
async def test_sqlite_memory_context_managers():
    with SqliteMemorySoilRepository() as sync_repo:
        assert sync_repo is not None

    async with SqliteMemorySoilRepository() as async_repo:
        assert await async_repo.find_nearest(-16.0, -48.0, 100.0) is None
        assert await async_repo.get_profile_by_cell("nonexistent") is None
