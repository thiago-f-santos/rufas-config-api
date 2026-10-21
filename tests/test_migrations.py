import io
import os
from pathlib import Path

import h3
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from alembic import command
from rufas_config_api.config import Settings


def test_alembic_configuration_files_exist():
    """Verify that alembic.ini, alembic/env.py, and script.py.mako exist."""
    root_dir = Path(__file__).resolve().parents[1]
    alembic_ini = root_dir / "alembic.ini"
    env_py = root_dir / "alembic" / "env.py"
    script_mako = root_dir / "alembic" / "script.py.mako"

    assert alembic_ini.is_file(), "alembic.ini must exist in project root"
    assert env_py.is_file(), "alembic/env.py must exist"
    assert script_mako.is_file(), "alembic/script.py.mako must exist"

    # Verify alembic.ini points to alembic directory
    config = Config(str(alembic_ini))
    assert config.get_main_option("script_location") == "alembic"


def test_migration_revision_chain():
    """Verify revision chain ('0001' -> '0002') and down_revision continuity."""
    root_dir = Path(__file__).resolve().parents[1]
    alembic_ini = root_dir / "alembic.ini"
    config = Config(str(alembic_ini))
    script_dir = ScriptDirectory.from_config(config)

    heads = script_dir.get_heads()
    assert heads == ["0002"], f"Expected single head '0002', got {heads}"

    rev_0002 = script_dir.get_revision("0002")
    assert rev_0002 is not None
    assert rev_0002.revision == "0002"
    assert rev_0002.down_revision == "0001"

    rev_0001 = script_dir.get_revision("0001")
    assert rev_0001 is not None
    assert rev_0001.revision == "0001"
    assert rev_0001.down_revision is None

    # Walk from head down to base
    chain = [rev.revision for rev in script_dir.walk_revisions(base="base", head="0002")]
    assert chain == ["0002", "0001"], f"Unexpected revision chain: {chain}"


def test_v0_coverage_seed_parser():
    """Verify the seed parser can read and parse the v0 coverage file."""
    root_dir = Path(__file__).resolve().parents[1]
    alembic_ini = root_dir / "alembic.ini"
    config = Config(str(alembic_ini))
    script_dir = ScriptDirectory.from_config(config)

    rev_0002 = script_dir.get_revision("0002")
    assert rev_0002 is not None
    module = rev_0002.module
    assert hasattr(module, "load_v0_coverage"), "0002 migration must export load_v0_coverage"

    coverage_rows = module.load_v0_coverage()
    assert len(coverage_rows) == 9075
    for row in coverage_rows:
        assert "h3_cell" in row
        assert "region" in row
        assert row["region"] == "GO+DF"
        assert len(row["h3_cell"]) == 15
        assert h3.is_valid_cell(row["h3_cell"])


def test_v0_profiles_seed_parser():
    """Verify the seed parser can read and parse all 16 v0 soil profiles."""
    root_dir = Path(__file__).resolve().parents[1]
    alembic_ini = root_dir / "alembic.ini"
    config = Config(str(alembic_ini))
    script_dir = ScriptDirectory.from_config(config)

    rev_0002 = script_dir.get_revision("0002")
    assert rev_0002 is not None
    module = rev_0002.module
    assert hasattr(module, "load_v0_profiles"), "0002 migration must export load_v0_profiles"

    profiles = module.load_v0_profiles()
    assert len(profiles) == 16

    coverage_cells = {row["h3_cell"] for row in module.load_v0_coverage()}
    seen_ids = set()
    seen_cells = set()

    for p in profiles:
        assert p.get("id")
        assert p.get("name")
        assert "latitude" in p
        assert "longitude" in p
        assert "h3_cell" in p
        assert "soil_data" in p
        assert "provenance" in p

        assert p["id"] not in seen_ids, f"Duplicate profile id: {p['id']}"
        seen_ids.add(p["id"])

        assert p["h3_cell"] not in seen_cells, f"Duplicate h3_cell: {p['h3_cell']}"
        seen_cells.add(p["h3_cell"])

        assert h3.is_valid_cell(p["h3_cell"])
        assert p["h3_cell"] in coverage_cells, f"Profile {p['id']} cell not in coverage"

        # Check soil layers structure
        soil_data = p["soil_data"]
        assert "soil_layers" in soil_data
        assert len(soil_data["soil_layers"]) == 4

        # Check provenance location matches profile coordinates
        prov_loc = p["provenance"]["location"]
        assert prov_loc["latitude"] == pytest.approx(p["latitude"])
        assert prov_loc["longitude"] == pytest.approx(p["longitude"])


def test_migration_offline_sql_generation():
    """Verify Alembic offline SQL emission for 0001 and 0002 revisions."""
    root_dir = Path(__file__).resolve().parents[1]
    alembic_ini = root_dir / "alembic.ini"

    buf = io.StringIO()
    config = Config(str(alembic_ini), stdout=buf)
    config.output_buffer = buf
    command.upgrade(config, "head", sql=True)
    sql_text = buf.getvalue()

    # Verify 0001 operations in generated SQL
    assert "CREATE EXTENSION IF NOT EXISTS postgis;" in sql_text
    assert "CREATE TABLE soil_coverage" in sql_text
    assert "CREATE TABLE soil_profiles" in sql_text
    assert "CREATE TABLE soil_cell_mappings" in sql_text
    assert "idx_soil_coverage_region" in sql_text
    assert "idx_soil_profiles_h3_cell" in sql_text
    assert "idx_soil_profiles_location" in sql_text
    assert "gist" in sql_text.lower()
    assert "idx_soil_cell_mappings_profile_id" in sql_text

    # Verify 0002 operations in generated SQL
    assert "INSERT INTO soil_coverage" in sql_text
    assert "INSERT INTO soil_profiles" in sql_text
    assert "INSERT INTO soil_cell_mappings" in sql_text
    assert "ST_SetSRID" in sql_text
    assert "ST_MakePoint" in sql_text


@pytest.mark.integration
def test_live_migration_execution():
    """Verify running real migrations against a live Postgres database."""
    settings = Settings()
    database_url = os.environ.get("DATABASE_URL", settings.database_url)
    try:
        sync_url = database_url.replace("+asyncpg", "")
        sync_engine = create_engine(sync_url)
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL/PostGIS not available: {exc}")

    root_dir = Path(__file__).resolve().parents[1]
    alembic_ini = root_dir / "alembic.ini"
    config = Config(str(alembic_ini))

    # Test upgrade head and downgrade base
    command.upgrade(config, "head")
    command.downgrade(config, "base")
