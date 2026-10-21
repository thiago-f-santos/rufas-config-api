import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rufas_config_api.config import Settings
from rufas_config_api.domain.soil import SoilProfileDomain
from rufas_config_api.providers.soil.adapters.postgres import PostgresSoilRepository
from rufas_config_api.providers.soil.models import (
    Base,
    SoilCellMappingModel,
    SoilCoverageModel,
    SoilProfileModel,
)
from rufas_config_api.providers.soil.repository import SoilRepository


@pytest.fixture
async def pg_session_factory():
    settings = Settings()
    database_url = os.environ.get("DATABASE_URL", settings.database_url)
    try:
        engine = create_async_engine(database_url, echo=False)
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        pytest.skip(f"PostgreSQL/PostGIS not available: {exc}")

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield session_factory

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
    except Exception:
        pass


# ============================================================================
# Unit Tests (Run without Docker / external Postgres instance)
# ============================================================================


def test_models_schema_structure():
    """Verify ORM model tables, columns, indexes, and foreign keys."""
    # SoilCoverageModel
    assert SoilCoverageModel.__tablename__ == "soil_coverage"
    coverage_cols = SoilCoverageModel.__table__.columns
    assert "h3_cell" in coverage_cols
    assert coverage_cols["h3_cell"].primary_key is True
    assert "region" in coverage_cols
    assert coverage_cols["region"].nullable is False
    assert "created_at" in coverage_cols

    # SoilProfileModel
    assert SoilProfileModel.__tablename__ == "soil_profiles"
    profile_cols = SoilProfileModel.__table__.columns
    assert profile_cols["id"].primary_key is True
    assert profile_cols["name"].nullable is False
    assert profile_cols["latitude"].nullable is False
    assert profile_cols["longitude"].nullable is False
    assert profile_cols["h3_cell"].nullable is False
    assert profile_cols["location"].nullable is False
    assert profile_cols["soil_data"].nullable is False
    assert profile_cols["provenance"].nullable is False
    assert "created_at" in profile_cols
    assert "updated_at" in profile_cols

    # SoilCellMappingModel
    assert SoilCellMappingModel.__tablename__ == "soil_cell_mappings"
    mapping_cols = SoilCellMappingModel.__table__.columns
    assert mapping_cols["h3_cell"].primary_key is True
    assert mapping_cols["profile_id"].nullable is False
    # Foreign key to soil_profiles.id with CASCADE
    fk = next(iter(mapping_cols["profile_id"].foreign_keys))
    assert fk.target_fullname == "soil_profiles.id"
    assert fk.ondelete == "CASCADE"


def test_postgres_repository_protocol_conformance():
    """Verify PostgresSoilRepository conforms to SoilRepository protocol."""
    mock_factory = MagicMock(spec=async_sessionmaker)
    repo = PostgresSoilRepository(mock_factory)
    assert isinstance(repo, SoilRepository)


def test_postgres_repository_find_nearest_sql_compilation():
    """Verify SQL statement structure and PostGIS expressions in find_nearest."""
    mock_factory = MagicMock(spec=async_sessionmaker)
    repo = PostgresSoilRepository(mock_factory)

    stmt = repo._build_find_nearest_statement(
        latitude=-16.5,
        longitude=-49.2,
        max_distance_km=300.0,
    )
    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    # Check GiST KNN operator <->
    assert "<->" in compiled
    # Check ST_Distance with True (geography distance in meters)
    assert "ST_Distance" in compiled
    # Check ST_DWithin with True (geography distance filtering)
    assert "ST_DWithin" in compiled
    # Check ST_MakePoint and ST_SetSRID 4326
    assert "ST_MakePoint" in compiled
    assert "ST_SetSRID" in compiled
    assert "4326" in compiled or "%(ST_SetSRID" in compiled


def test_postgres_repository_save_profile_query_compilation():
    """Verify upsert compilation for save_profile."""
    mock_factory = MagicMock(spec=async_sessionmaker)
    repo = PostgresSoilRepository(mock_factory)

    profile = SoilProfileDomain(
        id="test_p1",
        name="Latossolo Teste",
        latitude=-16.5,
        longitude=-49.2,
        h3_cell="868261977ffffff",
        soil_data={"layers": []},
        provenance={"source": "unit_test"},
    )
    stmt = repo._build_save_profile_statement(profile)
    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "INSERT INTO soil_profiles" in compiled
    assert "ON CONFLICT (id) DO UPDATE" in compiled
    assert "excluded.name" in compiled
    assert "excluded.location" in compiled


def test_postgres_repository_map_cell_query_compilation():
    """Verify upsert compilation for map_cell_to_profile."""
    mock_factory = MagicMock(spec=async_sessionmaker)
    repo = PostgresSoilRepository(mock_factory)

    stmt = repo._build_map_cell_statement(h3_cell="868261977ffffff", profile_id="test_p1")
    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "INSERT INTO soil_cell_mappings" in compiled
    assert "ON CONFLICT (h3_cell) DO UPDATE" in compiled
    assert "excluded.profile_id" in compiled


def test_postgres_repository_add_coverage_query_compilation():
    """Verify insert on conflict do nothing compilation for add_coverage_cells."""
    mock_factory = MagicMock(spec=async_sessionmaker)
    repo = PostgresSoilRepository(mock_factory)

    stmt = repo._build_add_coverage_statement(["cell_1", "cell_2"], region="GO_DF")
    assert stmt is not None
    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "INSERT INTO soil_coverage" in compiled
    assert "ON CONFLICT (h3_cell) DO NOTHING" in compiled


@pytest.mark.asyncio
async def test_postgres_repository_mock_crud():
    """Verify method execution against mocked AsyncSession."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session

    repo = PostgresSoilRepository(mock_factory)

    # 1. is_in_coverage
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = "868261977ffffff"
    mock_session.execute.return_value = mock_result

    in_cov = await repo.is_in_coverage("868261977ffffff")
    assert in_cov is True

    mock_result.scalar_one_or_none.return_value = None
    not_in_cov = await repo.is_in_coverage("unknown_cell")
    assert not_in_cov is False

    # 2. get_profile_by_id
    mock_model = MagicMock(spec=SoilProfileModel)
    mock_model.id = "p1"
    mock_model.name = "Latossolo"
    mock_model.latitude = -16.5
    mock_model.longitude = -49.2
    mock_model.h3_cell = "868261977ffffff"
    mock_model.soil_data = {"layers": []}
    mock_model.provenance = {"source": "mock"}

    mock_result.scalar_one_or_none.return_value = mock_model
    profile = await repo.get_profile_by_id("p1")
    assert profile is not None
    assert profile.id == "p1"
    assert profile.name == "Latossolo"
    assert profile.latitude == -16.5
    assert profile.longitude == -49.2
    assert profile.soil_data == {"layers": []}

    mock_result.scalar_one_or_none.return_value = None
    missing = await repo.get_profile_by_id("missing")
    assert missing is None

    # 3. get_profile_by_cell
    mock_result.scalar_one_or_none.return_value = mock_model
    cell_profile = await repo.get_profile_by_cell("868261977ffffff")
    assert cell_profile is not None
    assert cell_profile.id == "p1"

    # 4. find_nearest
    mock_result.first.return_value = (mock_model, 12.34)
    nearest = await repo.find_nearest(-16.6, -49.3, max_distance_km=50.0)
    assert nearest is not None
    p, dist = nearest
    assert p.id == "p1"
    assert dist == pytest.approx(12.34)

    mock_result.first.return_value = None
    no_nearest = await repo.find_nearest(-16.6, -49.3, max_distance_km=50.0)
    assert no_nearest is None

    # 5. save_profile
    save_domain = SoilProfileDomain(
        id="p1",
        name="Latossolo",
        latitude=-16.5,
        longitude=-49.2,
        h3_cell="868261977ffffff",
        soil_data={"layers": []},
        provenance={"source": "mock"},
    )
    await repo.save_profile(save_domain)
    mock_session.commit.assert_awaited()

    # 6. map_cell_to_profile
    await repo.map_cell_to_profile("868261977ffffff", "p1")
    mock_session.commit.assert_awaited()

    # 7. delete_profile
    mock_delete_result = MagicMock()
    mock_delete_result.rowcount = 1
    mock_session.execute.return_value = mock_delete_result
    deleted = await repo.delete_profile("p1")
    assert deleted is True

    mock_delete_result.rowcount = 0
    not_deleted = await repo.delete_profile("p_unknown")
    assert not_deleted is False

    # 8. add_coverage_cells
    await repo.add_coverage_cells(["c1", "c2"], region="GO_DF")
    mock_session.commit.assert_awaited()


# ============================================================================
# Integration Tests (Marked with @pytest.mark.integration, requires Postgres)
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_repository_crud(pg_session_factory):
    repo = PostgresSoilRepository(pg_session_factory)
    profile = SoilProfileDomain(
        id="pg_test_01",
        name="Latossolo PG",
        latitude=-16.5,
        longitude=-49.2,
        h3_cell="868261977ffffff",
        soil_data={"layers": []},
        provenance={"source": "test"},
    )
    await repo.save_profile(profile)
    found = await repo.get_profile_by_id("pg_test_01")
    assert found is not None
    assert found.name == "Latossolo PG"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_repository_integration_full_lifecycle(pg_session_factory):
    repo = PostgresSoilRepository(pg_session_factory)

    # 1. Coverage
    await repo.add_coverage_cells(["868261977ffffff", "868261970000000"], region="GO_DF")
    assert await repo.is_in_coverage("868261977ffffff") is True
    assert await repo.is_in_coverage("nonexistent_cell") is False

    # 2. Save profile and map cell
    profile = SoilProfileDomain(
        id="pg_life_01",
        name="Latossolo Lifecycle",
        latitude=-16.5,
        longitude=-49.2,
        h3_cell="868261977ffffff",
        soil_data={"soil_layers": [{"depth": 20}]},
        provenance={"source": "integration_test"},
    )
    await repo.save_profile(profile)
    await repo.map_cell_to_profile("868261977ffffff", "pg_life_01")

    # 3. Lookup by cell
    by_cell = await repo.get_profile_by_cell("868261977ffffff")
    assert by_cell is not None
    assert by_cell.id == "pg_life_01"
    assert by_cell.name == "Latossolo Lifecycle"
    assert by_cell.soil_data == {"soil_layers": [{"depth": 20}]}

    # 4. Nearest neighbor search
    # Exact point -> distance near 0
    nearest = await repo.find_nearest(-16.5, -49.2, max_distance_km=10.0)
    assert nearest is not None
    p, dist = nearest
    assert p.id == "pg_life_01"
    assert dist < 0.1

    # Close point (~10 km away)
    nearest_close = await repo.find_nearest(-16.55, -49.25, max_distance_km=50.0)
    assert nearest_close is not None
    p_close, dist_close = nearest_close
    assert p_close.id == "pg_life_01"
    assert 0 < dist_close < 20.0

    # Max distance too small
    too_far = await repo.find_nearest(-16.55, -49.25, max_distance_km=1.0)
    assert too_far is None

    # 5. Cascade delete
    deleted = await repo.delete_profile("pg_life_01")
    assert deleted is True
    assert await repo.get_profile_by_id("pg_life_01") is None
    assert await repo.get_profile_by_cell("868261977ffffff") is None
