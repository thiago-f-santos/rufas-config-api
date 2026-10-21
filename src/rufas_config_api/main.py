import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rufas_config_api import __version__
from rufas_config_api.api import health, inputs
from rufas_config_api.config import Settings
from rufas_config_api.domain.soil import SoilProfileDomain
from rufas_config_api.errors.handlers import register_error_handlers
from rufas_config_api.providers.soil.adapters.postgres import PostgresSoilRepository
from rufas_config_api.providers.soil.adapters.sqlite_memory import SqliteMemorySoilRepository
from rufas_config_api.providers.soil.catalog import SoilCatalog
from rufas_config_api.providers.soil.service import SoilService


async def _populate_memory_repo_from_catalog(
    repo: SqliteMemorySoilRepository, catalog_path: Path
) -> None:
    if not catalog_path.is_file():
        return
    with sqlite3.connect(f"{catalog_path.resolve().as_uri()}?mode=ro", uri=True) as conn:
        meta_rows = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        region = meta_rows.get("coverage_region", "GO_DF")
        coverage_rows = conn.execute("SELECT h3_cell FROM coverage").fetchall()
        cells = [r[0] for r in coverage_rows]
        await repo.add_coverage_cells(cells, region=region)

        profile_rows = conn.execute(
            "SELECT id, latitude, longitude, h3_cell, soil_json, provenance_json FROM profiles"
        ).fetchall()
        for pid, lat, lon, cell, s_json, prov_json in profile_rows:
            soil_data = json.loads(s_json)
            provenance = json.loads(prov_json)
            profile = SoilProfileDomain(
                id=pid,
                name=pid,
                latitude=float(lat),
                longitude=float(lon),
                h3_cell=cell,
                soil_data=soil_data,
                provenance=provenance,
            )
            await repo.save_profile(profile)
            await repo.map_cell_to_profile(cell, pid)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    soil_catalog = (
        SoilCatalog.open(settings.soil_catalog_path)
        if settings.soil_catalog_path.is_file()
        else None
    )
    engine = None
    repo = None

    if not hasattr(app.state, "soil_service") or app.state.soil_service is None:
        use_sqlite = (
            settings.database_url.startswith("sqlite") or settings.database_url == ":memory:"
        )
        if use_sqlite:
            repo = SqliteMemorySoilRepository()
            repo.init_db()
            await _populate_memory_repo_from_catalog(repo, settings.soil_catalog_path)
            soil_service = SoilService(
                repo,
                max_distance_km=settings.soil_max_distance_km,
                warning_distance_km=settings.soil_warning_distance_km,
            )
        else:
            engine = create_async_engine(settings.database_url, echo=False)
            session_factory = async_sessionmaker(
                engine, expire_on_commit=False, class_=AsyncSession
            )
            repo = PostgresSoilRepository(session_factory)
            soil_service = SoilService(
                repo,
                max_distance_km=settings.soil_max_distance_km,
                warning_distance_km=settings.soil_warning_distance_km,
            )
        app.state.soil_repository = repo
        app.state.soil_service = soil_service

    try:
        async with httpx.AsyncClient() as http_client:
            app.state.soil_catalog = soil_catalog
            app.state.http_client = http_client
            yield
    finally:
        if soil_catalog is not None:
            soil_catalog.close()
        if repo is not None and hasattr(repo, "close"):
            repo.close()
        if engine is not None:
            await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="RuFaS Config API", version=__version__, lifespan=lifespan)
    app.state.settings = settings or Settings()
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(inputs.router)
    return app


app = create_app()
