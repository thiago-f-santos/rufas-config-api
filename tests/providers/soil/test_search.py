from collections.abc import Iterable
from dataclasses import dataclass

import h3
import pytest

from rufas_config_api.domain import Location
from rufas_config_api.errors import OutOfCoverageError, SoilCatalogError
from rufas_config_api.providers.soil.catalog import CatalogProfile
from rufas_config_api.providers.soil.search import SoilMatch, find_nearest, haversine_km

RESOLUTION = 6
CENTER_CELL = h3.latlng_to_cell(-16.68, -49.25, RESOLUTION)
CENTER = h3.cell_to_latlng(CENTER_CELL)
COVERAGE = frozenset(h3.grid_disk(CENTER_CELL, 10))


@dataclass
class StubCatalog:
    profiles: list[CatalogProfile]
    cells: frozenset[str] = COVERAGE
    resolution: int = RESOLUTION
    region: str = "GO+DF"

    def in_coverage(self, cell: str) -> bool:
        return cell in self.cells

    def profiles_in(self, cells: Iterable[str]) -> list[CatalogProfile]:
        wanted = set(cells)
        return [profile for profile in self.profiles if profile.h3_cell in wanted]


def make_profile(profile_id: str, latitude: float, longitude: float) -> CatalogProfile:
    return CatalogProfile(
        id=profile_id,
        latitude=latitude,
        longitude=longitude,
        h3_cell=h3.latlng_to_cell(latitude, longitude, RESOLUTION),
        soil_json=b"{}\n",
        provenance={},
    )


def inside_vertex(cell: str, vertex: tuple[float, float]) -> tuple[float, float]:
    """A point just inside ``cell`` next to one of its vertices."""
    center_lat, center_lon = h3.cell_to_latlng(cell)
    lat = vertex[0] + 0.02 * (center_lat - vertex[0])
    lon = vertex[1] + 0.02 * (center_lon - vertex[1])
    assert h3.latlng_to_cell(lat, lon, RESOLUTION) == cell
    return lat, lon


def test_haversine():
    assert haversine_km(-16.68, -49.25, -16.68, -49.25) == 0
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.19, abs=0.01)


def test_profile_in_request_cell_is_ring_zero():
    profile = make_profile("go_a", CENTER[0] + 0.01, CENTER[1] - 0.01)
    assert profile.h3_cell == CENTER_CELL

    match = find_nearest(StubCatalog([profile]), Location(*CENTER), max_rings=5)

    assert match == SoilMatch(
        profile=profile,
        distance_km=haversine_km(*CENTER, profile.latitude, profile.longitude),
        request_cell=CENTER_CELL,
        ring=0,
    )


def test_skips_empty_rings():
    ring_3_cell = sorted(h3.grid_ring(CENTER_CELL, 3))[0]
    profile = make_profile("go_a", *h3.cell_to_latlng(ring_3_cell))

    match = find_nearest(StubCatalog([profile]), Location(*CENTER), max_rings=5)

    assert match.profile is profile
    assert match.ring == 3


def test_prefers_closer_profile_in_next_ring():
    far_x = max(
        (haversine_km(*CENTER, *vertex), cell, vertex)
        for cell in h3.grid_ring(CENTER_CELL, 2)
        for vertex in h3.cell_to_boundary(cell)
    )
    near_y = min(
        (haversine_km(*CENTER, *vertex), cell, vertex)
        for cell in h3.grid_ring(CENTER_CELL, 3)
        for vertex in h3.cell_to_boundary(cell)
    )
    x = make_profile("go_x", *inside_vertex(far_x[1], far_x[2]))
    y = make_profile("go_y", *inside_vertex(near_y[1], near_y[2]))
    assert haversine_km(*CENTER, y.latitude, y.longitude) < haversine_km(
        *CENTER, x.latitude, x.longitude
    )

    match = find_nearest(StubCatalog([x, y]), Location(*CENTER), max_rings=5)

    assert match.profile is y
    assert match.ring == 3
    assert match.distance_km == haversine_km(*CENTER, y.latitude, y.longitude)


def test_tie_is_broken_by_smallest_id():
    latitude, longitude = h3.cell_to_latlng(sorted(h3.grid_ring(CENTER_CELL, 1))[0])
    later = make_profile("go_z", latitude, longitude)
    earlier = make_profile("go_a", latitude, longitude)

    match = find_nearest(StubCatalog([later, earlier]), Location(*CENTER), max_rings=5)

    assert match.profile is earlier


def test_cell_outside_coverage_is_rejected():
    catalog = StubCatalog([make_profile("go_a", *CENTER)])

    with pytest.raises(OutOfCoverageError) as raised:
        find_nearest(catalog, Location(-12.97, -38.5), max_rings=5)

    assert raised.value.coverage == "GO+DF"
    assert (raised.value.latitude, raised.value.longitude) == (-12.97, -38.5)


def test_far_valid_coordinate_is_out_of_coverage():
    catalog = StubCatalog([make_profile("go_a", *CENTER)])

    with pytest.raises(OutOfCoverageError):
        find_nearest(catalog, Location(89.0, 179.0), max_rings=80)


def test_covered_area_without_profiles_is_an_internal_error():
    with pytest.raises(SoilCatalogError, match=f"No soil profile within 3 rings of {CENTER_CELL}"):
        find_nearest(StubCatalog([]), Location(*CENTER), max_rings=3)
