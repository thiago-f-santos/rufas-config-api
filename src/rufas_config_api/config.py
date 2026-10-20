from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    nasa_power_base_url: str = "https://power.larc.nasa.gov"
    nasa_timeout_seconds: float = Field(default=60.0, gt=0)
    nasa_power_lag_days: int = Field(default=7, ge=0)
    soil_catalog_path: Path = Path("data/soil/soil_catalog.sqlite")
    soil_max_rings: int = Field(default=80, ge=1)
