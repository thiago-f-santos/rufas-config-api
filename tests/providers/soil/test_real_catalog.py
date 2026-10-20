"""End-to-end checks against the real Goiás and DF profiles in data/soil/.

They read the committed profiles and coverage, so they run from the repository root and skip
when the data is not there.
"""

import json
from pathlib import Path

import pytest

from rufas_config_api.domain import Location
from rufas_config_api.errors import OutOfCoverageError
from rufas_config_api.providers.soil.catalog import SoilCatalog
from rufas_config_api.providers.soil.index import build_index
from rufas_config_api.providers.soil.search import find_nearest

DATA_DIR = Path("data/soil")
PROFILES_DIR = DATA_DIR / "profiles"
MAX_RINGS = 80
EXPECTED_PROFILES = 16
LAYER_BOTTOMS = [20, 200, 600, 1500]


@pytest.fixture(scope="module")
def catalog(tmp_path_factory):
    if not (PROFILES_DIR.is_dir() and (DATA_DIR / "coverage_go_df_res6.json").exists()):
        pytest.skip("data/soil is not populated")
    db_path = tmp_path_factory.mktemp("catalog") / "catalog.sqlite"
    assert build_index(DATA_DIR, db_path) == EXPECTED_PROFILES
    opened = SoilCatalog.open(db_path)
    yield opened
    opened.close()


def nearest(catalog, latitude, longitude):
    return find_nearest(catalog, Location(latitude, longitude), max_rings=MAX_RINGS)


def test_every_committed_profile_is_in_the_catalog(catalog):
    ids = sorted(path.name for path in PROFILES_DIR.iterdir() if path.is_dir())
    assert len(ids) == EXPECTED_PROFILES
    for profile_id in ids:
        match = nearest(catalog, *_location_of(profile_id))
        assert match.profile.id == profile_id


def test_every_profile_is_a_valid_rufas_soil_file():
    for path in sorted(PROFILES_DIR.glob("*/soil.json")):
        soil = json.loads(path.read_text(encoding="utf-8"))
        layers = soil["soil_layers"]
        assert [layer["bottom_depth"] for layer in layers] == LAYER_BOTTOMS, path
        for layer in layers:
            fractions = layer["clay_fraction"] + layer["silt_fraction"] + layer["sand_fraction"]
            assert fractions == pytest.approx(1.0, abs=0.01), path
            assert layer["wilting_point_water_concentration"] > 0
            assert (
                layer["wilting_point_water_concentration"]
                < layer["field_capacity_water_concentration"]
                < layer["saturation_point_water_concentration"]
            ), path


def test_rio_verde_gets_the_very_clayey_latossolo(catalog):
    match = nearest(catalog, -17.49, -51.39)
    assert match.profile.id == "go_lv_muito_argilosa_01"
    assert match.distance_km < 50


def test_brasilia_gets_a_profile_within_the_pilot_distance(catalog):
    match = nearest(catalog, -15.79, -47.88)
    assert match.distance_km < 300


def test_a_point_on_the_goias_border_gets_a_profile(catalog):
    match = nearest(catalog, -18.42, -49.21)
    assert match.profile is not None


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(-16.68, -49.25), (-18.0, -52.0), (-14.0, -50.0), (-17.5, -48.0)],
)
def test_goias_points_are_within_the_pilot_distance(catalog, latitude, longitude):
    assert nearest(catalog, latitude, longitude).distance_km < 300


@pytest.mark.xfail(
    strict=True,
    reason="lacuna de cobertura no nordeste de Goiás: não há perfil num raio de 300 km",
)
def test_the_northeast_of_goias_is_within_the_pilot_distance(catalog):
    assert nearest(catalog, -13.5, -46.5).distance_km < 300


def test_salvador_is_outside_the_coverage(catalog):
    with pytest.raises(OutOfCoverageError):
        nearest(catalog, -12.97, -38.50)


def _location_of(profile_id):
    provenance = json.loads((PROFILES_DIR / profile_id / "provenance.json").read_text("utf-8"))
    return provenance["location"]["latitude"], provenance["location"]["longitude"]
