import h3
from fastapi import APIRouter, HTTPException, Response, status

from rufas_config_api.api.dependencies import SoilRepositoryDep
from rufas_config_api.api.schemas.soil import (
    SoilProfileCreateRequest,
    SoilProfileResponse,
    SoilProfileUpdateRequest,
)
from rufas_config_api.domain.soil import SoilProfileDomain

router = APIRouter(prefix="/soils", tags=["soils"])


@router.post(
    "/profiles",
    status_code=status.HTTP_201_CREATED,
    response_model=SoilProfileResponse,
)
async def create_soil_profile(
    body: SoilProfileCreateRequest,
    repo: SoilRepositoryDep,
) -> SoilProfileResponse:
    h3_cell = h3.latlng_to_cell(body.latitude, body.longitude, 6)
    profile = SoilProfileDomain(
        id=body.id,
        name=body.name,
        latitude=body.latitude,
        longitude=body.longitude,
        h3_cell=h3_cell,
        soil_data=body.soil_data.model_dump(),
        provenance=body.provenance,
    )
    await repo.save_profile(profile)
    await repo.map_cell_to_profile(h3_cell, body.id)
    return SoilProfileResponse(
        id=profile.id,
        name=profile.name,
        latitude=profile.latitude,
        longitude=profile.longitude,
        h3_cell=profile.h3_cell,
        soil_data=dict(profile.soil_data),
        provenance=dict(profile.provenance),
    )


@router.get(
    "/profiles/{id}",
    status_code=status.HTTP_200_OK,
    response_model=SoilProfileResponse,
)
async def get_soil_profile(
    id: str,
    repo: SoilRepositoryDep,
) -> SoilProfileResponse:
    profile = await repo.get_profile_by_id(id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Soil profile '{id}' not found",
        )
    return SoilProfileResponse(
        id=profile.id,
        name=profile.name,
        latitude=profile.latitude,
        longitude=profile.longitude,
        h3_cell=profile.h3_cell,
        soil_data=dict(profile.soil_data),
        provenance=dict(profile.provenance),
    )


@router.put(
    "/profiles/{id}",
    status_code=status.HTTP_200_OK,
    response_model=SoilProfileResponse,
)
async def update_soil_profile(
    id: str,
    body: SoilProfileUpdateRequest,
    repo: SoilRepositoryDep,
) -> SoilProfileResponse:
    existing = await repo.get_profile_by_id(id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Soil profile '{id}' not found",
        )

    new_lat = body.latitude if body.latitude is not None else existing.latitude
    new_lon = body.longitude if body.longitude is not None else existing.longitude
    new_name = body.name if body.name is not None else existing.name
    new_soil_data = (
        body.soil_data.model_dump() if body.soil_data is not None else dict(existing.soil_data)
    )
    new_provenance = body.provenance if body.provenance is not None else dict(existing.provenance)

    if body.latitude is not None or body.longitude is not None:
        new_h3_cell = h3.latlng_to_cell(new_lat, new_lon, 6)
        await repo.map_cell_to_profile(new_h3_cell, id)
    else:
        new_h3_cell = existing.h3_cell

    updated_profile = SoilProfileDomain(
        id=id,
        name=new_name,
        latitude=new_lat,
        longitude=new_lon,
        h3_cell=new_h3_cell,
        soil_data=new_soil_data,
        provenance=new_provenance,
    )
    await repo.save_profile(updated_profile)
    return SoilProfileResponse(
        id=updated_profile.id,
        name=updated_profile.name,
        latitude=updated_profile.latitude,
        longitude=updated_profile.longitude,
        h3_cell=updated_profile.h3_cell,
        soil_data=dict(updated_profile.soil_data),
        provenance=dict(updated_profile.provenance),
    )


@router.delete(
    "/profiles/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_soil_profile(
    id: str,
    repo: SoilRepositoryDep,
) -> Response:
    deleted = await repo.delete_profile(id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Soil profile '{id}' not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
