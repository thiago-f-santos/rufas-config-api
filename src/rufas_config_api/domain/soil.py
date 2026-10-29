from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SoilProfileDomain:
    id: str
    name: str
    latitude: float
    longitude: float
    h3_cell: str
    soil_data: Mapping[str, Any]
    provenance: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SoilMatch:
    profile: SoilProfileDomain
    distance_km: float
    request_cell: str
    match_type: str  # "exact" or "fallback_nearest"
    warning: str | None = None
