from fastapi import FastAPI

from rufas_config_api import __version__
from rufas_config_api.api import health
from rufas_config_api.config import Settings
from rufas_config_api.errors.handlers import register_error_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="RuFaS Config API", version=__version__)
    app.state.settings = settings or Settings()
    register_error_handlers(app)
    app.include_router(health.router)
    return app


app = create_app()
