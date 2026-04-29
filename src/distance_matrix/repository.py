# src/distance_matrix/repository.py
from __future__ import annotations
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from distance_matrix.model import DistanceMatrixModel
from distance_matrix.schemas.request import PaginateDistanceMatrixRequest


class DistanceMatrixRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def create(self, payload: dict, actor_user_id: int | None = None) -> DistanceMatrixModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = DistanceMatrixModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, id_: int) -> Optional[DistanceMatrixModel]:
        q = select(DistanceMatrixModel).where(
            DistanceMatrixModel.team_id == self._require_team(),
            DistanceMatrixModel.id == id_,
            DistanceMatrixModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_by_pair(self, origin_id: int, dest_id: int) -> Optional[DistanceMatrixModel]:
        q = select(DistanceMatrixModel).where(
            DistanceMatrixModel.team_id == self._require_team(),
            DistanceMatrixModel.origin_location_id == origin_id,
            DistanceMatrixModel.destination_location_id == dest_id,
            DistanceMatrixModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def upsert_pair(
        self, origin_id: int, dest_id: int, distance: float, duration_min: float,
        source: str, actor_user_id: int | None = None,
    ) -> DistanceMatrixModel:
        existing = await self.get_by_pair(origin_id, dest_id)
        from datetime import datetime, timezone
        from decimal import Decimal as _D
        if existing:
            existing.distance_value = _D(f"{distance:.4f}")
            existing.duration_min = _D(f"{duration_min:.4f}")
            existing.source = source
            existing.measured_at = datetime.now(timezone.utc)
            if actor_user_id is not None:
                existing.updated_by_user_id = actor_user_id
            await self.db.flush()
            await self.db.refresh(existing)
            return existing
        return await self.create({
            "origin_location_id": origin_id,
            "destination_location_id": dest_id,
            "distance_value": _D(f"{distance:.4f}"),
            "duration_min": _D(f"{duration_min:.4f}"),
            "source": source,
            "measured_at": datetime.now(timezone.utc),
        }, actor_user_id=actor_user_id)

    async def get_paginated(self, request: PaginateDistanceMatrixRequest):
        team_id = self._require_team()
        base = [DistanceMatrixModel.team_id == team_id]
        if not request.include_inactive:
            base.append(DistanceMatrixModel.is_active.is_(True))
        base_query = select(DistanceMatrixModel).where(*base)
        return await self._common_service.paginate(
            request=request, model=DistanceMatrixModel,
            session=self.db, base_query=base_query,
        )

    async def update(self, id_: int, payload: dict, actor_user_id: int | None = None) -> Optional[DistanceMatrixModel]:
        if not payload:
            return await self.get(id_)
        row = (await self.db.execute(select(DistanceMatrixModel).where(
            DistanceMatrixModel.team_id == self._require_team(),
            DistanceMatrixModel.id == id_,
            DistanceMatrixModel.is_active.is_(True),
        ))).scalar_one_or_none()
        if not row:
            return None
        protected = {"id", "team_id", "is_active", "created_at", "created_by_user_id"}
        for k, v in payload.items():
            if k in protected:
                continue
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def soft_deactivate_by_id(self, id_: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(update(DistanceMatrixModel).where(
            DistanceMatrixModel.team_id == self._require_team(),
            DistanceMatrixModel.id == id_,
            DistanceMatrixModel.is_active.is_(True),
        ).values(**values))
        await self.db.flush()
