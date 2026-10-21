from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SoilLayerSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    bottom_depth: float
    clay_fraction: float
    silt_fraction: float
    sand_fraction: float
    bulk_density: float
    saturated_hydraulic_conductivity: float
    wilting_point_water_concentration: float
    field_capacity_water_concentration: float
    saturation_point_water_concentration: float

    @model_validator(mode="after")
    def validate_layer(self) -> Self:
        fraction_sum = self.clay_fraction + self.silt_fraction + self.sand_fraction
        if round(abs(fraction_sum - 1.0), 6) > 0.01:
            raise ValueError(
                f"Sum of clay_fraction, silt_fraction, and sand_fraction must equal 1.0 "
                f"within 0.01 tolerance (got {fraction_sum:.4f})"
            )
        if not (
            0
            < self.wilting_point_water_concentration
            < self.field_capacity_water_concentration
            < self.saturation_point_water_concentration
        ):
            raise ValueError(
                "Moisture concentrations must satisfy: "
                "0 < wilting_point < field_capacity < saturation_point"
            )
        return self


class SoilDataSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    soil_layers: list[SoilLayerSchema] = Field(min_length=1)


class SoilProfileCreateRequest(BaseModel):
    id: str
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    soil_data: SoilDataSchema
    provenance: dict[str, Any] = Field(default_factory=dict)


class SoilProfileUpdateRequest(BaseModel):
    name: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    soil_data: SoilDataSchema | None = None
    provenance: dict[str, Any] | None = None


class SoilProfileResponse(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    h3_cell: str
    soil_data: dict[str, Any]
    provenance: dict[str, Any]
