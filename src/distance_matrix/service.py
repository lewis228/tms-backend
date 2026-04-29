# src/distance_matrix/service.py
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.exceptions.base import NotFoundException, BadRequestException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from distance_matrix.repository import DistanceMatrixRepository
from distance_matrix.schemas.request import (
    DistanceMatrixCreateRequest, DistanceMatrixUpdateRequest,
    DistanceMatrixMeasureRequest, PaginateDistanceMatrixRequest,
)
from distance_matrix.schemas.response import DistanceMatrixResponseSchema
from distance_matrix.providers import get_provider
from location.model import LocationModel
from team.model import TeamModel


class DistanceMatrixService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = DistanceMatrixRepository(db, team_id)

    async def create(self, payload: DistanceMatrixCreateRequest, actor_user_id: int | None = None) -> DistanceMatrixResponseSchema:
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return DistanceMatrixResponseSchema.model_validate(row)

    async def get(self, id_: int) -> DistanceMatrixResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Distance Matrix")
        return DistanceMatrixResponseSchema.model_validate(row)

    async def list_paginated(self, request: PaginateDistanceMatrixRequest) -> CursorPaginationResult[DistanceMatrixResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [DistanceMatrixResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(self, id_: int, payload: DistanceMatrixUpdateRequest, actor_user_id: int | None = None) -> DistanceMatrixResponseSchema:
        row = await self.repo.update(id_, payload.model_dump(exclude_unset=True), actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("Distance Matrix")
        return DistanceMatrixResponseSchema.model_validate(row)

    async def delete(self, id_: int, actor_user_id: int | None = None) -> bool:
        await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
        return True

    async def measure(self, payload: DistanceMatrixMeasureRequest, actor_user_id: int | None = None) -> DistanceMatrixResponseSchema:
        # location 좌표 조회
        rows = (await self.db.execute(
            select(LocationModel).where(
                LocationModel.id.in_([payload.origin_location_id, payload.destination_location_id]),
                LocationModel.team_id == self.team_id,
            )
        )).scalars().all()
        loc_map = {l.id: l for l in rows}
        o = loc_map.get(payload.origin_location_id)
        d = loc_map.get(payload.destination_location_id)
        if not o or not d:
            raise NotFoundException("Location")
        if not (o.latitude and o.longitude and d.latitude and d.longitude):
            raise BadRequestException("Location 좌표 미등록")

        # team 설정으로 provider 결정
        provider_name = payload.provider
        config_json = None
        team = (await self.db.execute(
            select(TeamModel).where(TeamModel.id == self.team_id)
        )).scalar_one_or_none()
        if provider_name is None:
            provider_name = team.distance_provider if team and team.distance_provider else "MANUAL"
        if team:
            config_json = team.distance_provider_config

        provider = get_provider(str(provider_name), config_json=config_json)
        result = await provider.measure(
            float(o.latitude), float(o.longitude),
            float(d.latitude), float(d.longitude),
        )

        # upsert
        row = await self.repo.upsert_pair(
            origin_id=payload.origin_location_id,
            dest_id=payload.destination_location_id,
            distance=result.distance_value,
            duration_min=result.duration_min,
            source=result.source,
            actor_user_id=actor_user_id,
        )
        return DistanceMatrixResponseSchema.model_validate(row)
