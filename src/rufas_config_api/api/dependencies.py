from datetime import date
from typing import Annotated

import httpx
from fastapi import Depends, Request

from rufas_config_api import __version__
from rufas_config_api.config import Settings
from rufas_config_api.packaging import PackageBuilder
from rufas_config_api.providers import ProviderRegistry
from rufas_config_api.providers.soil import SoilProvider, SoilService
from rufas_config_api.providers.soil.catalog import SoilCatalog
from rufas_config_api.providers.weather import WeatherProvider
from rufas_config_api.providers.weather.nasa_power import NasaPowerClient


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def get_soil_service(request: Request) -> SoilService:
    return request.app.state.soil_service


def get_soil_catalog(request: Request) -> SoilCatalog | None:
    return getattr(request.app.state, "soil_catalog", None)


def get_today() -> date:
    return date.today()


SettingsDep = Annotated[Settings, Depends(get_settings)]
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
SoilServiceDep = Annotated[SoilService, Depends(get_soil_service)]
SoilCatalogDep = Annotated[SoilCatalog | None, Depends(get_soil_catalog)]
TodayDep = Annotated[date, Depends(get_today)]


def get_registry(
    settings: SettingsDep, http: HttpClientDep, soil_service: SoilServiceDep
) -> ProviderRegistry:
    nasa_power = NasaPowerClient(http, settings.nasa_power_base_url, settings.nasa_timeout_seconds)
    return ProviderRegistry(
        [
            WeatherProvider(nasa_power, settings.nasa_power_lag_days),
            SoilProvider(soil_service),
        ]
    )


def get_package_builder() -> PackageBuilder:
    return PackageBuilder(service_version=__version__)


RegistryDep = Annotated[ProviderRegistry, Depends(get_registry)]
PackageBuilderDep = Annotated[PackageBuilder, Depends(get_package_builder)]
