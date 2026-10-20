import math
from dataclasses import dataclass

import h3

from rufas_config_api.domain import Location
from rufas_config_api.errors import OutOfCoverageError, SoilCatalogError
from rufas_config_api.providers.soil.catalog import CatalogProfile, SoilCatalog

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True, slots=True)
class SoilMatch:
    profile: CatalogProfile
    distance_km: float
    request_cell: str
    ring: int


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def find_nearest(catalog: SoilCatalog, location: Location, max_rings: int) -> SoilMatch:
    """Nearest profile by great-circle distance, searched ring by ring around the H3 cell.

    The first non-empty ring k is not enough: a profile in ring k+1 can be closer than
    every profile in ring k, so both rings are compared.
    """
    lat, lon = location.latitude, location.longitude
    cell = h3.latlng_to_cell(lat, lon, catalog.resolution)
    if not catalog.in_coverage(cell):
        raise OutOfCoverageError(lat, lon, catalog.region)

    for k in range(max_rings + 1):
        found = catalog.profiles_in(h3.grid_ring(cell, k))
        if not found:
            continue
        candidates = [(profile, k) for profile in found] + [
            (profile, k + 1) for profile in catalog.profiles_in(h3.grid_ring(cell, k + 1))
        ]
        scored = [
            (haversine_km(lat, lon, profile.latitude, profile.longitude), profile, ring)
            for profile, ring in candidates
        ]
        distance, profile, ring = min(scored, key=lambda item: (item[0], item[1].id))
        return SoilMatch(profile, distance, cell, ring)

    raise SoilCatalogError(f"No soil profile within {max_rings} rings of {cell}")
