import json
from typing import Any

from rufas_config_api.domain import Location, PackageFile, Period, ProviderResult, SoilMatch
from rufas_config_api.providers.soil.service import SoilService

DISTANCE_DECIMALS = 3


class SoilProvider:
    name = "soil"
    FILE_NAME = "soil.json"
    SOURCE = "rufas-config-api dynamic soil database"

    def __init__(self, soil_service: SoilService) -> None:
        self._soil_service = soil_service

    async def build(self, location: Location, period: Period | None = None) -> ProviderResult:
        match = await self._soil_service.resolve_soil(location)
        if isinstance(match.profile.soil_data, (bytes, bytearray)):
            soil_bytes = bytes(match.profile.soil_data)
        elif isinstance(match.profile.soil_data, str):
            soil_bytes = match.profile.soil_data.encode("utf-8")
        else:
            soil_bytes = json.dumps(match.profile.soil_data).encode("utf-8")

        soil_file = PackageFile(self.FILE_NAME, soil_bytes, provider=self.name)
        return ProviderResult(self.name, (soil_file,), self._provenance(match))

    def _provenance(self, match: SoilMatch) -> dict[str, Any]:
        profile = match.profile
        return {
            "source": self.SOURCE,
            "match_type": match.match_type,
            "h3": {
                "resolution": self._soil_service.resolution,
                "request_cell": match.request_cell,
                "profile_cell": profile.h3_cell,
            },
            "profile_id": profile.id,
            "distance_km": round(match.distance_km, DISTANCE_DECIMALS),
            "warning": match.warning,
            "profile_provenance": dict(profile.provenance),
        }
