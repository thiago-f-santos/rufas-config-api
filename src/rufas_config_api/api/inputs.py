import asyncio
from typing import Annotated

from fastapi import APIRouter, Query, Response

from rufas_config_api.api.dependencies import (
    PackageBuilderDep,
    RegistryDep,
    SettingsDep,
    TodayDep,
)
from rufas_config_api.domain import Location, Period

ZIP_MEDIA_TYPE = "application/zip"

router = APIRouter(tags=["inputs"])


@router.get(
    "/inputs",
    response_class=Response,
    responses={200: {"content": {ZIP_MEDIA_TYPE: {}}, "description": "Zip with RuFaS inputs"}},
)
async def get_inputs(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    start_year: Annotated[int, Query()],
    end_year: Annotated[int, Query()],
    settings: SettingsDep,
    today: TodayDep,
    registry: RegistryDep,
    package_builder: PackageBuilderDep,
    include: Annotated[list[str] | None, Query()] = None,
) -> Response:
    location = Location(latitude, longitude)
    period = Period.from_years(
        start_year, end_year, today=today, lag_days=settings.nasa_power_lag_days
    )
    providers = registry.resolve(include or [])
    results = await asyncio.gather(*(provider.build(location, period) for provider in providers))
    archive = package_builder.build(results, location, period)
    filename = f"rufas_inputs_{latitude}_{longitude}_{start_year}_{end_year}.zip"
    return Response(
        content=archive,
        media_type=ZIP_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
