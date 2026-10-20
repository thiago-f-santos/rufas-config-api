from typing import Any

from rufas_config_api.domain import Location, PackageFile, Period, ProviderResult
from rufas_config_api.providers.soil.catalog import SoilCatalog
from rufas_config_api.providers.soil.search import SoilMatch, find_nearest

DISTANCE_DECIMALS = 3


class SoilProvider:
    name = "soil"
    FILE_NAME = "soil.json"
    SOURCE = "rufas-config-api soil catalog"
    METHOD = "h3_ring_nearest"

    def __init__(self, catalog: SoilCatalog, max_rings: int) -> None:
        self._catalog = catalog
        self._max_rings = max_rings

    async def build(self, location: Location, period: Period) -> ProviderResult:
        match = find_nearest(self._catalog, location, self._max_rings)
        soil_file = PackageFile(self.FILE_NAME, match.profile.soil_json, provider=self.name)
        return ProviderResult(self.name, (soil_file,), self._provenance(match))

    def _provenance(self, match: SoilMatch) -> dict[str, Any]:
        profile = match.profile
        return {
            "source": self.SOURCE,
            "method": self.METHOD,
            "h3": {
                "resolution": self._catalog.resolution,
                "request_cell": match.request_cell,
                "profile_cell": profile.h3_cell,
                "ring": match.ring,
            },
            "profile_id": profile.id,
            "profile_location": {"latitude": profile.latitude, "longitude": profile.longitude},
            "distance_km": round(match.distance_km, DISTANCE_DECIMALS),
            "profile_provenance": dict(profile.provenance),
        }
