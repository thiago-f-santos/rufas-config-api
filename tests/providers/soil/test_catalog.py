import sqlite3
from concurrent.futures import ThreadPoolExecutor

import h3
import pytest

from rufas_config_api.errors import SoilCatalogUnavailableError
from rufas_config_api.providers.soil.catalog import CatalogProfile, SoilCatalog

SALVADOR = (-12.97, -38.5)


def cell_of(latitude: float, longitude: float) -> str:
    return h3.latlng_to_cell(latitude, longitude, 6)


@pytest.fixture
def catalog(soil_catalog_path):
    catalog = SoilCatalog.open(soil_catalog_path)
    yield catalog
    catalog.close()


def test_reads_meta(catalog):
    assert catalog.resolution == 6
    assert catalog.region == "GO+DF"


def test_profiles_in_returns_profile_with_original_bytes(catalog, soil_data_dir):
    cell = cell_of(-16.68, -49.25)

    profiles = catalog.profiles_in([cell])

    assert profiles == [
        CatalogProfile(
            id="go_test_a",
            latitude=-16.68,
            longitude=-49.25,
            h3_cell=cell,
            soil_json=(soil_data_dir / "profiles" / "go_test_a" / "soil.json").read_bytes(),
            provenance={
                "profile_id": "go_test_a",
                "location": {"latitude": -16.68, "longitude": -49.25},
            },
        )
    ]


def test_profiles_in_orders_by_id(catalog):
    cells = [cell_of(-17.79, -50.92), cell_of(-16.70, -49.40), cell_of(-16.68, -49.25)]

    assert [profile.id for profile in catalog.profiles_in(cells)] == [
        "go_test_a",
        "go_test_b",
        "go_test_c",
    ]


def test_profiles_in_with_no_cells_is_empty(catalog):
    assert catalog.profiles_in([]) == []


def test_in_coverage(catalog):
    assert catalog.in_coverage(cell_of(-17.79, -50.92))
    assert not catalog.in_coverage(cell_of(*SALVADOR))


def test_missing_file_is_unavailable(tmp_path):
    path = tmp_path / "nada.sqlite"

    with pytest.raises(SoilCatalogUnavailableError) as raised:
        SoilCatalog.open(path)

    assert raised.value.path == path
    assert raised.value.reason == (
        "file not found; run `python -m rufas_config_api.providers.soil.index`"
    )
    assert not path.exists()


def test_works_from_another_thread(soil_catalog_path):
    with ThreadPoolExecutor(max_workers=1) as opener:
        catalog = opener.submit(SoilCatalog.open, soil_catalog_path).result()
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(catalog.profiles_in, [[cell_of(-16.68, -49.25)]] * 8))
    finally:
        catalog.close()

    assert all([profile.id for profile in result] == ["go_test_a"] for result in results)


def test_rejects_writes(catalog):
    with pytest.raises(sqlite3.OperationalError):
        catalog._connection.execute("INSERT INTO coverage (h3_cell) VALUES ('x')")
