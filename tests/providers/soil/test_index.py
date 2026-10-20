import json
import shutil
import sqlite3
from pathlib import Path

import h3
import pytest

from rufas_config_api.errors import RufasConfigError
from rufas_config_api.providers.soil.index import (
    EXPECTED_RESOLUTION,
    IndexBuildError,
    build_index,
    main,
)

COVERAGE_FILE = "coverage_go_df_res6.json"


@pytest.fixture
def data_dir(soil_data_dir: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "soil"
    shutil.copytree(soil_data_dir, copy)
    return copy


def read_rows(db_path: Path, query: str) -> list[tuple]:
    with sqlite3.connect(db_path) as connection:
        return connection.execute(query).fetchall()


def test_builds_every_profile(data_dir, tmp_path):
    db_path = tmp_path / "catalog.sqlite"

    assert build_index(data_dir, db_path) == 3

    rows = read_rows(db_path, "SELECT id, latitude, longitude, h3_cell FROM profiles ORDER BY id")
    assert rows == [
        ("go_test_a", -16.68, -49.25, h3.latlng_to_cell(-16.68, -49.25, EXPECTED_RESOLUTION)),
        ("go_test_b", -16.70, -49.40, h3.latlng_to_cell(-16.70, -49.40, EXPECTED_RESOLUTION)),
        ("go_test_c", -17.79, -50.92, h3.latlng_to_cell(-17.79, -50.92, EXPECTED_RESOLUTION)),
    ]


def test_stores_meta_and_coverage(data_dir, tmp_path):
    db_path = tmp_path / "catalog.sqlite"
    build_index(data_dir, db_path)

    meta = dict(read_rows(db_path, "SELECT key, value FROM meta"))
    coverage = json.loads((data_dir / COVERAGE_FILE).read_text())
    [(cell_count,)] = read_rows(db_path, "SELECT COUNT(*) FROM coverage")
    assert meta["h3_resolution"] == "6"
    assert meta["coverage_region"] == "GO+DF"
    assert meta["profile_count"] == "3"
    assert meta["built_at"]
    assert cell_count == len(coverage["cells"])


def test_stores_soil_json_bytes_unchanged(data_dir, tmp_path):
    db_path = tmp_path / "catalog.sqlite"
    build_index(data_dir, db_path)

    [(stored,)] = read_rows(db_path, "SELECT soil_json FROM profiles WHERE id = 'go_test_a'")
    assert stored == (data_dir / "profiles" / "go_test_a" / "soil.json").read_bytes()


def test_replaces_existing_database_without_leftover_temp_file(data_dir, tmp_path):
    db_path = tmp_path / "catalog.sqlite"
    build_index(data_dir, db_path)
    shutil.rmtree(data_dir / "profiles" / "go_test_c")

    assert build_index(data_dir, db_path) == 2
    assert read_rows(db_path, "SELECT COUNT(*) FROM profiles") == [(2,)]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["catalog.sqlite", "soil"]


def test_missing_coverage_is_rejected(data_dir, tmp_path):
    (data_dir / COVERAGE_FILE).unlink()

    with pytest.raises(IndexBuildError, match=COVERAGE_FILE):
        build_index(data_dir, tmp_path / "catalog.sqlite")


def test_coverage_with_other_resolution_is_rejected(data_dir, tmp_path):
    coverage_path = data_dir / COVERAGE_FILE
    coverage = json.loads(coverage_path.read_text())
    coverage_path.write_text(json.dumps({**coverage, "resolution": 7}))

    with pytest.raises(IndexBuildError, match="resolution 7"):
        build_index(data_dir, tmp_path / "catalog.sqlite")


def test_profile_without_soil_json_is_rejected(data_dir, tmp_path):
    (data_dir / "profiles" / "go_test_b" / "soil.json").unlink()

    with pytest.raises(IndexBuildError, match="go_test_b"):
        build_index(data_dir, tmp_path / "catalog.sqlite")


@pytest.mark.parametrize("missing", ["latitude", "longitude"])
def test_profile_without_location_is_rejected(data_dir, tmp_path, missing):
    provenance_path = data_dir / "profiles" / "go_test_b" / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    del provenance["location"][missing]
    provenance_path.write_text(json.dumps(provenance))

    with pytest.raises(IndexBuildError, match="go_test_b"):
        build_index(data_dir, tmp_path / "catalog.sqlite")


def test_profile_outside_coverage_is_rejected(data_dir, tmp_path):
    provenance_path = data_dir / "profiles" / "go_test_b" / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    provenance["location"] = {"latitude": -12.97, "longitude": -38.5}
    provenance_path.write_text(json.dumps(provenance))

    with pytest.raises(IndexBuildError, match="go_test_b"):
        build_index(data_dir, tmp_path / "catalog.sqlite")


def test_failed_build_keeps_previous_database(data_dir, tmp_path):
    db_path = tmp_path / "catalog.sqlite"
    build_index(data_dir, db_path)
    (data_dir / "profiles" / "go_test_b" / "soil.json").unlink()

    with pytest.raises(IndexBuildError):
        build_index(data_dir, db_path)

    assert read_rows(db_path, "SELECT COUNT(*) FROM profiles") == [(3,)]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["catalog.sqlite", "soil"]


def test_index_build_error_is_a_domain_error():
    assert issubclass(IndexBuildError, RufasConfigError)


def test_main_builds_catalog(data_dir, tmp_path, capsys):
    db_path = tmp_path / "out" / "catalog.sqlite"

    main(["--data-dir", str(data_dir), "--output", str(db_path)])

    assert read_rows(db_path, "SELECT COUNT(*) FROM profiles") == [(3,)]
    assert "3 soil profile(s)" in capsys.readouterr().out


def test_main_exits_with_error_message(tmp_path):
    with pytest.raises(SystemExit, match="Coverage file"):
        main(["--data-dir", str(tmp_path), "--output", str(tmp_path / "catalog.sqlite")])
