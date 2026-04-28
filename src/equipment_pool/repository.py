# src/equipment_pool/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from equipment_pool.model import EquipmentPoolModel
from equipment_pool.schemas.request import PaginateEquipmentPoolRequest
from equipment_pool.schemas.response import EquipmentPoolResponseSchema


class EquipmentPoolRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def create(self, payload: dict, actor_user_id: int | None = None) -> EquipmentPoolModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = EquipmentPoolModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, id_: int) -> Optional[EquipmentPoolModel]:
        q = select(EquipmentPoolModel).where(
            EquipmentPoolModel.team_id == self._require_team(),
            EquipmentPoolModel.id == id_,
            EquipmentPoolModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_many(self, ids: List[int]) -> List[EquipmentPoolModel]:
        if not ids:
            return []
        q = select(EquipmentPoolModel).where(
            EquipmentPoolModel.team_id == self._require_team(),
            EquipmentPoolModel.id.in_(ids),
            EquipmentPoolModel.is_active.is_(True),
        )
        return list((await self.db.execute(q)).scalars().all())

    async def get_paginated(
        self, request: PaginateEquipmentPoolRequest,
    ) -> CursorPaginationResult[EquipmentPoolResponseSchema]:
        team_id = self._require_team()
        base_conditions = [EquipmentPoolModel.team_id == team_id]
        if not request.include_inactive:
            base_conditions.append(EquipmentPoolModel.is_active.is_(True))
        base_query = select(EquipmentPoolModel).where(*base_conditions)
        result = await self._common_service.paginate(
            request=request, model=EquipmentPoolModel,
            session=self.db, base_query=base_query,
        )
        result.data = [EquipmentPoolResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(
        self, id_: int, payload: dict, actor_user_id: int | None = None,
    ) -> Optional[EquipmentPoolModel]:
        if not payload:
            return await self.get(id_)
        q = select(EquipmentPoolModel).where(
            EquipmentPoolModel.team_id == self._require_team(),
            EquipmentPoolModel.id == id_,
            EquipmentPoolModel.is_active.is_(True),
        )
        row = (await self.db.execute(q)).scalar_one_or_none()
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

    async def soft_deactivate_by_id(
        self, id_: int, actor_user_id: int | None = None,
    ) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(EquipmentPoolModel).where(
                EquipmentPoolModel.team_id == self._require_team(),
                EquipmentPoolModel.id == id_,
                EquipmentPoolModel.is_active.is_(True),
            ).values(**values)
        )
        await self.db.flush()

    async def hard_delete_by_id(self, id_: int) -> None:
        await self.db.execute(
            delete(EquipmentPoolModel).where(
                EquipmentPoolModel.team_id == self._require_team(),
                EquipmentPoolModel.id == id_,
            )
        )
        await self.db.flush()
