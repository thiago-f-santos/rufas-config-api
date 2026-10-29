import asyncio
import json
import sqlite3
import threading
from typing import Any, Self

from rufas_config_api.domain.soil import SoilProfileDomain
from rufas_config_api.providers.soil.search import haversine_km


def _sqlite_haversine_km(
    lat1: float | None, lon1: float | None, lat2: float | None, lon2: float | None
) -> float | None:
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    return haversine_km(float(lat1), float(lon1), float(lat2), float(lon2))


class SqliteMemorySoilRepository:
    def __init__(self, database: str = ":memory:") -> None:
        self._conn = sqlite3.connect(database, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.create_function("haversine_km", 4, _sqlite_haversine_km)
        self._lock = threading.Lock()
        self.init_db()

    def init_db(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS soil_coverage (
                    h3_cell TEXT PRIMARY KEY,
                    region TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS soil_profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    h3_cell TEXT NOT NULL,
                    soil_data TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS soil_cell_mappings (
                    h3_cell TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL REFERENCES soil_profiles(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_soil_coverage_region
                    ON soil_coverage(region);
                CREATE INDEX IF NOT EXISTS idx_soil_profiles_h3_cell
                    ON soil_profiles(h3_cell);
                CREATE INDEX IF NOT EXISTS idx_soil_cell_mappings_profile_id
                    ON soil_cell_mappings(profile_id);
                """
            )
            self._conn.commit()

    @staticmethod
    def _row_to_domain(row: sqlite3.Row) -> SoilProfileDomain:
        return SoilProfileDomain(
            id=row["id"],
            name=row["name"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            h3_cell=row["h3_cell"],
            soil_data=json.loads(row["soil_data"]),
            provenance=json.loads(row["provenance"]),
        )

    async def is_in_coverage(self, h3_cell: str) -> bool:
        def _run() -> bool:
            with self._lock:
                cur = self._conn.execute(
                    "SELECT 1 FROM soil_coverage WHERE h3_cell = ? LIMIT 1",
                    (h3_cell,),
                )
                return cur.fetchone() is not None

        return await asyncio.to_thread(_run)

    async def get_profile_by_id(self, profile_id: str) -> SoilProfileDomain | None:
        def _run() -> SoilProfileDomain | None:
            with self._lock:
                cur = self._conn.execute(
                    """
                    SELECT id, name, latitude, longitude, h3_cell, soil_data, provenance
                    FROM soil_profiles
                    WHERE id = ?
                    """,
                    (profile_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_domain(row)

        return await asyncio.to_thread(_run)

    async def get_profile_by_cell(self, h3_cell: str) -> SoilProfileDomain | None:
        def _run() -> SoilProfileDomain | None:
            with self._lock:
                cur = self._conn.execute(
                    """
                    SELECT p.id, p.name, p.latitude, p.longitude,
                           p.h3_cell, p.soil_data, p.provenance
                    FROM soil_profiles p
                    JOIN soil_cell_mappings m ON p.id = m.profile_id
                    WHERE m.h3_cell = ?
                    """,
                    (h3_cell,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_domain(row)

        return await asyncio.to_thread(_run)

    async def find_nearest(
        self, latitude: float, longitude: float, max_distance_km: float
    ) -> tuple[SoilProfileDomain, float] | None:
        def _run() -> tuple[SoilProfileDomain, float] | None:
            with self._lock:
                cur = self._conn.execute(
                    """
                    SELECT p.id, p.name, p.latitude, p.longitude,
                           p.h3_cell, p.soil_data, p.provenance,
                           haversine_km(:lat, :lon, p.latitude, p.longitude) AS distance_km
                    FROM soil_profiles p
                    WHERE distance_km <= :max_dist
                    ORDER BY distance_km ASC, p.id ASC
                    LIMIT 1
                    """,
                    {"lat": latitude, "lon": longitude, "max_dist": max_distance_km},
                )
                row = cur.fetchone()
                if row is None:
                    return None
                profile = self._row_to_domain(row)
                return profile, float(row["distance_km"])

        return await asyncio.to_thread(_run)

    async def save_profile(self, profile: SoilProfileDomain) -> None:
        def _run() -> None:
            with self._lock:
                self._conn.execute(
                    """
                    INSERT INTO soil_profiles (
                        id, name, latitude, longitude, h3_cell, soil_data, provenance, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        latitude = excluded.latitude,
                        longitude = excluded.longitude,
                        h3_cell = excluded.h3_cell,
                        soil_data = excluded.soil_data,
                        provenance = excluded.provenance,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        profile.id,
                        profile.name,
                        profile.latitude,
                        profile.longitude,
                        profile.h3_cell,
                        json.dumps(profile.soil_data),
                        json.dumps(profile.provenance),
                    ),
                )
                self._conn.commit()

        await asyncio.to_thread(_run)

    async def map_cell_to_profile(self, h3_cell: str, profile_id: str) -> None:
        def _run() -> None:
            with self._lock:
                self._conn.execute(
                    """
                    INSERT INTO soil_cell_mappings (h3_cell, profile_id)
                    VALUES (?, ?)
                    ON CONFLICT(h3_cell) DO UPDATE SET
                        profile_id = excluded.profile_id
                    """,
                    (h3_cell, profile_id),
                )
                self._conn.commit()

        await asyncio.to_thread(_run)

    async def unmap_cell_from_profile(self, h3_cell: str, profile_id: str) -> bool:
        def _run() -> bool:
            with self._lock:
                cur = self._conn.execute(
                    "DELETE FROM soil_cell_mappings WHERE h3_cell = ? AND profile_id = ?",
                    (h3_cell, profile_id),
                )
                self._conn.commit()
                return cur.rowcount > 0

        return await asyncio.to_thread(_run)

    async def delete_profile(self, profile_id: str) -> bool:
        def _run() -> bool:
            with self._lock:
                cur = self._conn.execute(
                    "DELETE FROM soil_profiles WHERE id = ?",
                    (profile_id,),
                )
                self._conn.commit()
                return cur.rowcount > 0

        return await asyncio.to_thread(_run)

    async def add_coverage_cells(self, cells: list[str], region: str) -> None:
        def _run() -> None:
            with self._lock:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO soil_coverage (h3_cell, region) VALUES (?, ?)",
                    [(c, region) for c in cells],
                )
                self._conn.commit()

        await asyncio.to_thread(_run)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    async def aclose(self) -> None:
        self.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
