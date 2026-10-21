from typing import Any, Self

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import Select

from rufas_config_api.domain.soil import SoilProfileDomain
from rufas_config_api.providers.soil.models import (
    SoilCellMappingModel,
    SoilCoverageModel,
    SoilProfileModel,
)


class PostgresSoilRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _to_domain(model: SoilProfileModel) -> SoilProfileDomain:
        return SoilProfileDomain(
            id=str(model.id),
            name=str(model.name),
            latitude=float(model.latitude),
            longitude=float(model.longitude),
            h3_cell=str(model.h3_cell),
            soil_data=(
                dict(model.soil_data) if isinstance(model.soil_data, dict) else model.soil_data
            ),
            provenance=(
                dict(model.provenance) if isinstance(model.provenance, dict) else model.provenance
            ),
        )

    def _build_find_nearest_statement(
        self, latitude: float, longitude: float, max_distance_km: float
    ) -> Select[tuple[SoilProfileModel, Any]]:
        point_geom = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        distance_km_expr = (
            func.ST_Distance(
                SoilProfileModel.location,
                point_geom,
                True,
            )
            / 1000.0
        )
        return (
            select(
                SoilProfileModel,
                distance_km_expr.label("distance_km"),
            )
            .where(
                func.ST_DWithin(
                    SoilProfileModel.location,
                    point_geom,
                    max_distance_km * 1000.0,
                    True,
                )
            )
            .order_by(SoilProfileModel.location.distance_centroid(point_geom))
            .limit(1)
        )

    def _build_save_profile_statement(self, profile: SoilProfileDomain) -> Insert:
        point_geom = func.ST_SetSRID(func.ST_MakePoint(profile.longitude, profile.latitude), 4326)
        insert_stmt = insert(SoilProfileModel).values(
            id=profile.id,
            name=profile.name,
            latitude=profile.latitude,
            longitude=profile.longitude,
            h3_cell=profile.h3_cell,
            location=point_geom,
            soil_data=dict(profile.soil_data),
            provenance=dict(profile.provenance),
        )
        return insert_stmt.on_conflict_do_update(
            index_elements=[SoilProfileModel.id],
            set_={
                "name": insert_stmt.excluded.name,
                "latitude": insert_stmt.excluded.latitude,
                "longitude": insert_stmt.excluded.longitude,
                "h3_cell": insert_stmt.excluded.h3_cell,
                "location": insert_stmt.excluded.location,
                "soil_data": insert_stmt.excluded.soil_data,
                "provenance": insert_stmt.excluded.provenance,
                "updated_at": func.now(),
            },
        )

    def _build_map_cell_statement(self, h3_cell: str, profile_id: str) -> Insert:
        insert_stmt = insert(SoilCellMappingModel).values(
            h3_cell=h3_cell,
            profile_id=profile_id,
        )
        return insert_stmt.on_conflict_do_update(
            index_elements=[SoilCellMappingModel.h3_cell],
            set_={"profile_id": insert_stmt.excluded.profile_id},
        )

    def _build_add_coverage_statement(self, cells: list[str], region: str) -> Insert | None:
        if not cells:
            return None
        insert_stmt = insert(SoilCoverageModel).values(
            [{"h3_cell": cell, "region": region} for cell in cells]
        )
        return insert_stmt.on_conflict_do_nothing(index_elements=[SoilCoverageModel.h3_cell])

    async def is_in_coverage(self, h3_cell: str) -> bool:
        stmt = (
            select(SoilCoverageModel.h3_cell).where(SoilCoverageModel.h3_cell == h3_cell).limit(1)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def get_profile_by_id(self, profile_id: str) -> SoilProfileDomain | None:
        stmt = select(SoilProfileModel).where(SoilProfileModel.id == profile_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model is None:
                return None
            return self._to_domain(model)

    async def get_profile_by_cell(self, h3_cell: str) -> SoilProfileDomain | None:
        stmt = (
            select(SoilProfileModel)
            .join(SoilCellMappingModel, SoilProfileModel.id == SoilCellMappingModel.profile_id)
            .where(SoilCellMappingModel.h3_cell == h3_cell)
            .limit(1)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model is None:
                return None
            return self._to_domain(model)

    async def find_nearest(
        self, latitude: float, longitude: float, max_distance_km: float
    ) -> tuple[SoilProfileDomain, float] | None:
        stmt = self._build_find_nearest_statement(latitude, longitude, max_distance_km)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            row = result.first()
            if row is None:
                return None
            model, dist = row
            return self._to_domain(model), float(dist)

    async def save_profile(self, profile: SoilProfileDomain) -> None:
        stmt = self._build_save_profile_statement(profile)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def map_cell_to_profile(self, h3_cell: str, profile_id: str) -> None:
        stmt = self._build_map_cell_statement(h3_cell, profile_id)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def delete_profile(self, profile_id: str) -> bool:
        stmt = delete(SoilProfileModel).where(SoilProfileModel.id == profile_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            await session.commit()
            return (result.rowcount or 0) > 0

    async def add_coverage_cells(self, cells: list[str], region: str) -> None:
        if not cells:
            return
        batch_size = 1000
        async with self._session_factory() as session:
            for i in range(0, len(cells), batch_size):
                chunk = cells[i : i + batch_size]
                stmt = self._build_add_coverage_statement(chunk, region)
                if stmt is not None:
                    await session.execute(stmt)
            await session.commit()

    async def aclose(self) -> None:
        pass

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass
