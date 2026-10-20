from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from rufas_config_api import __version__
from rufas_config_api.api import health, inputs
from rufas_config_api.config import Settings
from rufas_config_api.errors.handlers import register_error_handlers
from rufas_config_api.providers.soil.catalog import SoilCatalog


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    soil_catalog = SoilCatalog.open(settings.soil_catalog_path)
    try:
        async with httpx.AsyncClient() as http_client:
            app.state.soil_catalog = soil_catalog
            app.state.http_client = http_client
            yield
    finally:
        soil_catalog.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="RuFaS Config API", version=__version__, lifespan=lifespan)
    app.state.settings = settings or Settings()
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(inputs.router)
    return app


app = create_app()
