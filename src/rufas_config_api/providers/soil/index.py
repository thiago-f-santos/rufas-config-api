import argparse
import json
import os
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import h3

from rufas_config_api.errors import RufasConfigError

EXPECTED_RESOLUTION = 6
COVERAGE_FILE = "coverage_go_df_res6.json"
PROFILES_DIR = "profiles"
SOIL_FILE = "soil.json"
PROVENANCE_FILE = "provenance.json"
DEFAULT_DATA_DIR = Path("data/soil")
DEFAULT_OUTPUT = DEFAULT_DATA_DIR / "soil_catalog.sqlite"

SCHEMA = """
CREATE TABLE profiles (
  id TEXT PRIMARY KEY, latitude REAL NOT NULL, longitude REAL NOT NULL,
  h3_cell TEXT NOT NULL, soil_json BLOB NOT NULL, provenance_json TEXT NOT NULL
);
CREATE INDEX profiles_h3_cell ON profiles (h3_cell);
CREATE TABLE coverage (h3_cell TEXT PRIMARY KEY);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class IndexBuildError(RufasConfigError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class _Coverage:
    region: str
    resolution: int
    cells: frozenset[str]


@dataclass(frozen=True, slots=True)
class _Profile:
    id: str
    latitude: float
    longitude: float
    h3_cell: str
    soil_json: bytes
    provenance_json: str


def build_index(data_dir: Path, db_path: Path) -> int:
    coverage = _read_coverage(data_dir / COVERAGE_FILE)
    profiles = _read_profiles(data_dir / PROFILES_DIR, coverage)
    _write_database(db_path, coverage, profiles)
    return len(profiles)


def _read_coverage(path: Path) -> _Coverage:
    if not path.is_file():
        raise IndexBuildError(f"Coverage file {path} not found")
    document = _read_json(path, f"Coverage file {path}")
    try:
        region = str(document["region"])
        resolution = document["resolution"]
        cells = frozenset(document["cells"])
    except (KeyError, TypeError) as error:
        raise IndexBuildError(
            f"Coverage file {path} must have 'region', 'resolution' and 'cells'"
        ) from error
    if resolution != EXPECTED_RESOLUTION:
        raise IndexBuildError(
            f"Coverage file {path} has H3 resolution {resolution}; expected {EXPECTED_RESOLUTION}"
        )
    return _Coverage(region, resolution, cells)


def _read_profiles(profiles_dir: Path, coverage: _Coverage) -> list[_Profile]:
    if not profiles_dir.is_dir():
        raise IndexBuildError(f"Profiles directory {profiles_dir} not found")
    profiles = [
        _read_profile(profile_dir, coverage)
        for profile_dir in sorted(profiles_dir.iterdir())
        if profile_dir.is_dir()
    ]
    if not profiles:
        raise IndexBuildError(f"No soil profiles found in {profiles_dir}")
    return profiles


def _read_profile(profile_dir: Path, coverage: _Coverage) -> _Profile:
    profile_id = profile_dir.name
    soil_path = profile_dir / SOIL_FILE
    provenance_path = profile_dir / PROVENANCE_FILE
    for path in (soil_path, provenance_path):
        if not path.is_file():
            raise IndexBuildError(f"Profile {profile_id} has no {path.name}")

    soil_json = soil_path.read_bytes()
    _parse_json(soil_json, f"Profile {profile_id}: {SOIL_FILE}")
    provenance_text = provenance_path.read_text(encoding="utf-8")
    provenance = _parse_json(provenance_text, f"Profile {profile_id}: {PROVENANCE_FILE}")
    latitude, longitude = _read_location(profile_id, provenance)

    cell = h3.latlng_to_cell(latitude, longitude, coverage.resolution)
    if cell not in coverage.cells:
        raise IndexBuildError(
            f"Profile {profile_id} at ({latitude}, {longitude}) is in H3 cell {cell}, "
            f"outside the {coverage.region} coverage"
        )
    return _Profile(profile_id, latitude, longitude, cell, soil_json, provenance_text)


def _read_location(profile_id: str, provenance: Any) -> tuple[float, float]:
    location = provenance.get("location") if isinstance(provenance, dict) else None
    values = []
    for key in ("latitude", "longitude"):
        value = location.get(key) if isinstance(location, dict) else None
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise IndexBuildError(
                f"Profile {profile_id}: {PROVENANCE_FILE} has no numeric location.{key}"
            )
        values.append(float(value))
    return values[0], values[1]


def _read_json(path: Path, label: str) -> Any:
    return _parse_json(path.read_text(encoding="utf-8"), label)


def _parse_json(content: str | bytes, label: str) -> Any:
    try:
        return json.loads(content)
    except ValueError as error:
        raise IndexBuildError(f"{label} is not valid JSON: {error}") from error


def _write_database(db_path: Path, coverage: _Coverage, profiles: Sequence[_Profile]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = db_path.with_name(f"{db_path.name}.tmp")
    tmp_path.unlink(missing_ok=True)
    try:
        connection = sqlite3.connect(tmp_path)
        try:
            with connection:
                connection.executescript(SCHEMA)
                connection.executemany(
                    "INSERT INTO profiles VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (p.id, p.latitude, p.longitude, p.h3_cell, p.soil_json, p.provenance_json)
                        for p in profiles
                    ],
                )
                connection.executemany(
                    "INSERT INTO coverage VALUES (?)", [(cell,) for cell in sorted(coverage.cells)]
                )
                connection.executemany(
                    "INSERT INTO meta VALUES (?, ?)",
                    [
                        ("h3_resolution", str(coverage.resolution)),
                        ("coverage_region", coverage.region),
                        ("built_at", datetime.now(UTC).isoformat()),
                        ("profile_count", str(len(profiles))),
                    ],
                )
        finally:
            connection.close()
        os.replace(tmp_path, db_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m rufas_config_api.providers.soil.index",
        description="Build the SQLite soil catalog from soil profiles and H3 coverage.",
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        count = build_index(args.data_dir, args.output)
    except IndexBuildError as error:
        raise SystemExit(f"error: {error}") from error
    print(f"Wrote {count} soil profile(s) to {args.output}")


if __name__ == "__main__":
    main()
