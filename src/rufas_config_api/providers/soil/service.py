import h3

from rufas_config_api.domain import Location, SoilMatch
from rufas_config_api.errors import NoProfileInRangeError, OutOfCoverageError
from rufas_config_api.providers.soil.repository import SoilRepository


class SoilService:
    """Two-tier soil profile resolution (exact cell match and nearest fallback)."""

    def __init__(
        self,
        repo: SoilRepository,
        max_distance_km: float = 300.0,
        warning_distance_km: float = 50.0,
        resolution: int = 6,
    ) -> None:
        self._repo = repo
        self._max_distance_km = max_distance_km
        self._warning_distance_km = warning_distance_km
        self._resolution = resolution

    @property
    def repo(self) -> SoilRepository:
        return self._repo

    @property
    def max_distance_km(self) -> float:
        return self._max_distance_km

    @property
    def warning_distance_km(self) -> float:
        return self._warning_distance_km

    @property
    def resolution(self) -> int:
        return self._resolution

    async def resolve_soil(self, location: Location) -> SoilMatch:
        """Resolve a soil profile for a given location using two-tier search.

        1. Computes the H3 index cell at the configured resolution.
        2. Validates whether the cell is within catalog coverage.
        3. Attempts an O(1) exact match for the cell.
        4. Falls back to proximity-based nearest search within max_distance_km.
        """
        cell = h3.latlng_to_cell(location.latitude, location.longitude, self._resolution)

        if not await self._repo.is_in_coverage(cell):
            raise OutOfCoverageError(location.latitude, location.longitude, "GO_DF")

        exact_profile = await self._repo.get_profile_by_cell(cell)
        if exact_profile is not None:
            return SoilMatch(
                profile=exact_profile,
                distance_km=0.0,
                request_cell=cell,
                match_type="exact",
                warning=None,
            )

        nearest = await self._repo.find_nearest(
            location.latitude, location.longitude, max_distance_km=self._max_distance_km
        )
        if nearest is None:
            raise NoProfileInRangeError(
                location.latitude, location.longitude, self._max_distance_km
            )

        profile, distance_km = nearest
        warning: str | None = None
        if distance_km > self._warning_distance_km:
            warning = (
                f"Nearest profile is {distance_km:.1f} km away; "
                "local soil characteristics may differ."
            )

        return SoilMatch(
            profile=profile,
            distance_km=distance_km,
            request_cell=cell,
            match_type="fallback_nearest",
            warning=warning,
        )
