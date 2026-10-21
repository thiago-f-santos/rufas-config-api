import json
from collections.abc import AsyncIterator, Callable, Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import h3
import pytest

from rufas_config_api.main import _populate_memory_repo_from_catalog
from rufas_config_api.providers.soil.adapters.sqlite_memory import SqliteMemorySoilRepository
from rufas_config_api.providers.soil.index import build_index

DEFAULT_VALUES = {
    "PRECTOTCORR": 1.234,
    "T2M_MAX": 30.5,
    "T2M_MIN": 18.25,
    "T2M": 24.0,
    "ALLSKY_SFC_SW_DWN": 20.126,
}
FILL_VALUE = -999.0

SOIL_RESOLUTION = 6
SOIL_COVERAGE_RADIUS = 20
SOIL_PROFILES = {
    "go_test_a": (-16.68, -49.25),
    "go_test_b": (-16.70, -49.40),
    "go_test_c": (-17.79, -50.92),
}

type NasaPayloadFactory = Callable[..., dict[str, Any]]


@pytest.fixture
def nasa_payload() -> NasaPayloadFactory:
    def build(start: date, end: date, missing: Iterable[tuple[date, str]] = ()) -> dict[str, Any]:
        missing_values = set(missing)
        days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
        parameter = {
            name: {
                day.strftime("%Y%m%d"): FILL_VALUE if (day, name) in missing_values else value
                for day in days
            }
            for name, value in DEFAULT_VALUES.items()
        }
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-49.49, -16.36, 807.47]},
            "properties": {"parameter": parameter},
            "header": {
                "api": {"version": "v2.10.0", "name": "POWER Daily API"},
                "sources": ["FLASHFLUX", "GEOSIT", "POWER"],
                "fill_value": FILL_VALUE,
                "start": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"),
            },
            "messages": [],
        }

    return build


def write_soil_profile(data_dir: Path, profile_id: str, latitude: float, longitude: float) -> None:
    profile_dir = data_dir / "profiles" / profile_id
    profile_dir.mkdir(parents=True)
    soil = {
        "_nota": "solo genérico",
        "profile_id": profile_id,
        "soil_layers": [{"bottom_depth": depth} for depth in (20, 200, 600, 1500)],
    }
    (profile_dir / "soil.json").write_bytes(
        (json.dumps(soil, indent=4, ensure_ascii=False) + "\n").encode()
    )
    provenance = {
        "profile_id": profile_id,
        "location": {"latitude": latitude, "longitude": longitude},
    }
    (profile_dir / "provenance.json").write_text(json.dumps(provenance, indent=2))


def write_soil_coverage(data_dir: Path, cells: Iterable[str]) -> None:
    coverage = {"region": "GO+DF", "resolution": SOIL_RESOLUTION, "cells": sorted(set(cells))}
    (data_dir / "coverage_go_df_res6.json").write_text(json.dumps(coverage))


@pytest.fixture(scope="session")
def soil_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    data_dir = tmp_path_factory.mktemp("data") / "soil"
    data_dir.mkdir()
    cells: set[str] = set()
    for profile_id, (latitude, longitude) in SOIL_PROFILES.items():
        write_soil_profile(data_dir, profile_id, latitude, longitude)
        center = h3.latlng_to_cell(latitude, longitude, SOIL_RESOLUTION)
        cells.update(h3.grid_disk(center, SOIL_COVERAGE_RADIUS))
    write_soil_coverage(data_dir, cells)
    return data_dir


@pytest.fixture(scope="session")
def soil_catalog_path(soil_data_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_path = tmp_path_factory.mktemp("catalog") / "catalog.sqlite"
    build_index(soil_data_dir, db_path)
    return db_path


V0_SEEDS_DIR = Path("data/seeds/v0_initial_catalog")


@pytest.fixture(scope="session")
def v0_seeds_dir() -> Path:
    return V0_SEEDS_DIR


@pytest.fixture(scope="session")
def v0_soil_catalog_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_path = tmp_path_factory.mktemp("catalog_v0") / "catalog.sqlite"
    build_index(V0_SEEDS_DIR, db_path)
    return db_path


@pytest.fixture
async def seed_soil_repository(
    v0_soil_catalog_path: Path,
) -> AsyncIterator[SqliteMemorySoilRepository]:
    repo = SqliteMemorySoilRepository()
    repo.init_db()
    await _populate_memory_repo_from_catalog(repo, v0_soil_catalog_path)
    try:
        yield repo
    finally:
        repo.close()


@pytest.fixture
async def v0_soil_repository(
    seed_soil_repository: SqliteMemorySoilRepository,
) -> SqliteMemorySoilRepository:
    return seed_soil_repository


@pytest.fixture
async def memory_soil_repository(
    soil_catalog_path: Path,
) -> AsyncIterator[SqliteMemorySoilRepository]:
    repo = SqliteMemorySoilRepository()
    repo.init_db()
    await _populate_memory_repo_from_catalog(repo, soil_catalog_path)
    try:
        yield repo
    finally:
        repo.close()
