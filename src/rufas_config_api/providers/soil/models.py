from __future__ import annotations

from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SoilCoverageModel(Base):
    __tablename__ = "soil_coverage"

    h3_cell: Mapped[str] = mapped_column(String(15), primary_key=True)
    region: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SoilProfileModel(Base):
    __tablename__ = "soil_profiles"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    h3_cell: Mapped[str] = mapped_column(String(15), nullable=False, index=True)
    location = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False
    )
    soil_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    cell_mappings: Mapped[list[SoilCellMappingModel]] = relationship(
        "SoilCellMappingModel",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SoilCellMappingModel(Base):
    __tablename__ = "soil_cell_mappings"

    h3_cell: Mapped[str] = mapped_column(String(15), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("soil_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    profile: Mapped[SoilProfileModel] = relationship(
        "SoilProfileModel", back_populates="cell_mappings"
    )
