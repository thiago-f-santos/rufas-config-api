import asyncio
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

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
    settings: SettingsDep,
    today: TodayDep,
    registry: RegistryDep,
    package_builder: PackageBuilderDep,
    start_year: Annotated[int | None, Query()] = None,
    end_year: Annotated[int | None, Query()] = None,
    include: Annotated[list[str] | None, Query()] = None,
) -> Response:
    location = Location(latitude, longitude)
    providers = registry.resolve(include or [])
    provider_names = {p.name for p in providers}

    if ("weather" in provider_names or not include) and (start_year is None or end_year is None):
        raise HTTPException(
            status_code=422,
            detail="start_year and end_year are required when weather provider is included",
        )

    if start_year is not None and end_year is not None:
        period = Period.from_years(
            start_year, end_year, today=today, lag_days=settings.nasa_power_lag_days
        )
        filename = f"rufas_inputs_{latitude}_{longitude}_{start_year}_{end_year}.zip"
    else:
        period = Period.from_years(
            today.year, today.year, today=today, lag_days=settings.nasa_power_lag_days
        )
        filename = f"rufas_inputs_{latitude}_{longitude}.zip"

    results = await asyncio.gather(*(provider.build(location, period) for provider in providers))
    archive = package_builder.build(results, location, period)
    return Response(
        content=archive,
        media_type=ZIP_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
