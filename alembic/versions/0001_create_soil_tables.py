"""Create soil coverage, profiles, and cell mappings tables.

Revision ID: 0001
Revises: None
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # 2. Table: soil_coverage
    op.create_table(
        "soil_coverage",
        sa.Column("h3_cell", sa.String(length=15), nullable=False),
        sa.Column("region", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("h3_cell"),
    )
    op.create_index("idx_soil_coverage_region", "soil_coverage", ["region"])

    # 3. Table: soil_profiles
    op.create_table(
        "soil_profiles",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("h3_cell", sa.String(length=15), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("soil_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_soil_profiles_h3_cell", "soil_profiles", ["h3_cell"])
    op.create_index(
        "idx_soil_profiles_location",
        "soil_profiles",
        ["location"],
        postgresql_using="gist",
    )

    # 4. Table: soil_cell_mappings
    op.create_table(
        "soil_cell_mappings",
        sa.Column("h3_cell", sa.String(length=15), nullable=False),
        sa.Column("profile_id", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["soil_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("h3_cell"),
    )
    op.create_index(
        "idx_soil_cell_mappings_profile_id",
        "soil_cell_mappings",
        ["profile_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_soil_cell_mappings_profile_id", table_name="soil_cell_mappings")
    op.drop_table("soil_cell_mappings")

    op.drop_index(
        "idx_soil_profiles_location",
        table_name="soil_profiles",
        postgresql_using="gist",
    )
    op.drop_index("idx_soil_profiles_h3_cell", table_name="soil_profiles")
    op.drop_table("soil_profiles")

    op.drop_index("idx_soil_coverage_region", table_name="soil_coverage")
    op.drop_table("soil_coverage")
