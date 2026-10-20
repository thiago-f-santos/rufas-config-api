import json
import sqlite3
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from rufas_config_api.errors import SoilCatalogUnavailableError

INDEX_COMMAND = "python -m rufas_config_api.providers.soil.index"


@dataclass(frozen=True, slots=True)
class CatalogProfile:
    id: str
    latitude: float
    longitude: float
    h3_cell: str
    soil_json: bytes
    provenance: Mapping[str, Any]


class SoilCatalog:
    """Read-only view of the SQLite soil catalog, safe to share across threads."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._lock = threading.Lock()
        self._meta = dict(connection.execute("SELECT key, value FROM meta").fetchall())

    @classmethod
    def open(cls, path: Path) -> Self:
        if not path.is_file():
            raise SoilCatalogUnavailableError(path, f"file not found; run `{INDEX_COMMAND}`")
        uri = f"{path.resolve().as_uri()}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
        except sqlite3.Error as error:
            raise SoilCatalogUnavailableError(path, str(error)) from error
        try:
            catalog = cls(connection)
            _ = catalog.resolution, catalog.region
        except (sqlite3.Error, KeyError, ValueError) as error:
            connection.close()
            raise SoilCatalogUnavailableError(
                path, f"invalid catalog ({error}); run `{INDEX_COMMAND}`"
            ) from error
        return catalog

    @property
    def resolution(self) -> int:
        return int(self._meta["h3_resolution"])

    @property
    def region(self) -> str:
        return self._meta["coverage_region"]

    def in_coverage(self, cell: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM coverage WHERE h3_cell = ?", (cell,)
            ).fetchone()
        return row is not None

    def profiles_in(self, cells: Iterable[str]) -> list[CatalogProfile]:
        cells = list(dict.fromkeys(cells))
        if not cells:
            return []
        placeholders = ", ".join("?" * len(cells))
        query = (
            "SELECT id, latitude, longitude, h3_cell, soil_json, provenance_json "
            f"FROM profiles WHERE h3_cell IN ({placeholders}) ORDER BY id"
        )
        with self._lock:
            rows = self._connection.execute(query, cells).fetchall()
        return [
            CatalogProfile(
                id=row[0],
                latitude=row[1],
                longitude=row[2],
                h3_cell=row[3],
                soil_json=bytes(row[4]),
                provenance=json.loads(row[5]),
            )
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._connection.close()
