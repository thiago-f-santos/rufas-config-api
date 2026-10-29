"""Seed initial v0 soil catalog (coverage and 16 Goiás/DF profiles).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-20
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import geoalchemy2
import h3
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def get_v0_seeds_dir() -> Path:
    """Locate the v0 seed data catalog directory."""
    # First attempt: relative to this migration file (2 levels up -> project root)
    base = Path(__file__).resolve().parents[2] / "data" / "seeds" / "v0_initial_catalog"
    if base.exists():
        return base
    # Second attempt: current working directory
    cwd_base = Path.cwd() / "data" / "seeds" / "v0_initial_catalog"
    if cwd_base.exists():
        return cwd_base
    raise FileNotFoundError(f"v0 seed catalog not found at {base} or {cwd_base}")


def load_v0_coverage(coverage_path: Path | None = None) -> list[dict[str, str]]:
    """Parse coverage_go_df_res6.json into table rows."""
    if coverage_path is None:
        coverage_path = get_v0_seeds_dir() / "coverage_go_df_res6.json"
    with open(coverage_path, encoding="utf-8") as f:
        data = json.load(f)

    region = data.get("region", "GO+DF")
    cells = data.get("cells", [])
    return [{"h3_cell": cell, "region": region} for cell in cells]


def _derive_profile_name(provenance: dict[str, Any], profile_id: str) -> str:
    """Extract or construct a human-readable name for a profile."""
    name = provenance.get("name")
    if name:
        return str(name)
    group = provenance.get("group")
    if isinstance(group, dict):
        classe = group.get("classe")
        textura = group.get("textura")
        if classe and textura:
            return f"{classe.title()} {textura.title()}"
        if classe:
            return str(classe).title()
    return profile_id


def load_v0_profiles(profiles_dir: Path | None = None) -> list[dict[str, Any]]:
    """Parse all profile directories in v0_initial_catalog/profiles into profile records."""
    if profiles_dir is None:
        profiles_dir = get_v0_seeds_dir() / "profiles"

    profiles: list[dict[str, Any]] = []
    for p_dir in sorted(profiles_dir.iterdir()):
        if not p_dir.is_dir():
            continue
        soil_file = p_dir / "soil.json"
        prov_file = p_dir / "provenance.json"
        if not (soil_file.is_file() and prov_file.is_file()):
            continue

        with open(soil_file, encoding="utf-8") as sf:
            soil_data = json.load(sf)
        with open(prov_file, encoding="utf-8") as pf:
            provenance = json.load(pf)

        profile_id = provenance.get("profile_id", p_dir.name)
        lat = float(provenance["location"]["latitude"])
        lon = float(provenance["location"]["longitude"])
        h3_cell = h3.latlng_to_cell(lat, lon, 6)
        name = _derive_profile_name(provenance, profile_id)

        profiles.append(
            {
                "id": profile_id,
                "name": name,
                "latitude": lat,
                "longitude": lon,
                "h3_cell": h3_cell,
                "soil_data": soil_data,
                "provenance": provenance,
            }
        )

    return profiles


def upgrade() -> None:
    is_offline = context.is_offline_mode()

    # 1. Batch seed soil_coverage
    coverage_rows = load_v0_coverage()
    coverage_table = sa.table(
        "soil_coverage",
        sa.column("h3_cell", sa.String),
        sa.column("region", sa.String),
    )
    batch_size = 1000
    for i in range(0, len(coverage_rows), batch_size):
        batch = coverage_rows[i : i + batch_size]
        op.bulk_insert(coverage_table, batch)

    # 2. Seed soil_profiles
    profiles = load_v0_profiles()
    profile_table = sa.table(
        "soil_profiles",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("latitude", sa.Float),
        sa.column("longitude", sa.Float),
        sa.column("h3_cell", sa.String),
        sa.column("location", geoalchemy2.Geometry),
        sa.column("soil_data", postgresql.JSONB),
        sa.column("provenance", postgresql.JSONB),
    )
    mapping_table = sa.table(
        "soil_cell_mappings",
        sa.column("h3_cell", sa.String),
        sa.column("profile_id", sa.String),
    )

    mapping_rows: list[dict[str, str]] = []
    for prof in profiles:
        if is_offline:
            soil_data_val = sa.literal_column(
                "'" + json.dumps(prof["soil_data"]).replace("'", "''") + "'::jsonb"
            )
            provenance_val = sa.literal_column(
                "'" + json.dumps(prof["provenance"]).replace("'", "''") + "'::jsonb"
            )
        else:
            soil_data_val = prof["soil_data"]
            provenance_val = prof["provenance"]

        stmt = sa.insert(profile_table).values(
            id=prof["id"],
            name=prof["name"],
            latitude=prof["latitude"],
            longitude=prof["longitude"],
            h3_cell=prof["h3_cell"],
            location=sa.func.ST_SetSRID(
                sa.func.ST_MakePoint(prof["longitude"], prof["latitude"]), 4326
            ),
            soil_data=soil_data_val,
            provenance=provenance_val,
        )
        op.execute(stmt)

        mapping_rows.append(
            {
                "h3_cell": prof["h3_cell"],
                "profile_id": prof["id"],
            }
        )

    # 3. Seed soil_cell_mappings
    if mapping_rows:
        op.bulk_insert(mapping_table, mapping_rows)


def downgrade() -> None:
    mapping_table = sa.table("soil_cell_mappings")
    profile_table = sa.table("soil_profiles")
    coverage_table = sa.table("soil_coverage")

    op.execute(mapping_table.delete())
    op.execute(profile_table.delete())
    op.execute(coverage_table.delete())
