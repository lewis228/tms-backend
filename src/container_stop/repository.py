# src/container_stop/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from container_stop.model import ContainerStopModel
from container_stop.schemas.request import PaginateContainerStopRequest


class ContainerStopRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def create(self, payload: dict, actor_user_id: int | None = None) -> ContainerStopModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = ContainerStopModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, id_: int) -> Optional[ContainerStopModel]:
        q = select(ContainerStopModel).where(
            ContainerStopModel.team_id == self._require_team(),
            ContainerStopModel.id == id_,
            ContainerStopModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def list_by_container(self, container_id: int) -> List[ContainerStopModel]:
        q = (
            select(ContainerStopModel)
            .where(
                ContainerStopModel.team_id == self._require_team(),
                ContainerStopModel.container_id == container_id,
                ContainerStopModel.is_active.is_(True),
            )
            .order_by(ContainerStopModel.sequence_no.asc(), ContainerStopModel.id.asc())
        )
        return list((await self.db.execute(q)).scalars().all())

    async def get_paginated(
        self, request: PaginateContainerStopRequest,
    ):
        team_id = self._require_team()
        base_conditions = [ContainerStopModel.team_id == team_id]
        if not request.include_inactive:
            base_conditions.append(ContainerStopModel.is_active.is_(True))
        base_query = select(ContainerStopModel).where(*base_conditions)
        result = await self._common_service.paginate(
            request=request, model=ContainerStopModel,
            session=self.db, base_query=base_query,
        )
        return result

    async def next_sequence_no(self, container_id: int) -> int:
        team_id = self._require_team()
        q = select(func.max(ContainerStopModel.sequence_no)).where(
            ContainerStopModel.team_id == team_id,
            ContainerStopModel.container_id == container_id,
        )
        result = await self.db.execute(q)
        return (result.scalar() or 0) + 1

    async def update(
        self, id_: int, payload: dict, actor_user_id: int | None = None,
    ) -> Optional[ContainerStopModel]:
        if not payload:
            return await self.get(id_)
        q = select(ContainerStopModel).where(
            ContainerStopModel.team_id == self._require_team(),
            ContainerStopModel.id == id_,
            ContainerStopModel.is_active.is_(True),
        )
        row = (await self.db.execute(q)).scalar_one_or_none()
        if not row:
            return None
        protected = {"id", "team_id", "is_active", "created_at", "created_by_user_id", "container_id"}
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
            update(ContainerStopModel).where(
                ContainerStopModel.team_id == self._require_team(),
                ContainerStopModel.id == id_,
                ContainerStopModel.is_active.is_(True),
            ).values(**values)
        )
        await self.db.flush()

    async def hard_delete_by_id(self, id_: int) -> None:
        await self.db.execute(
            delete(ContainerStopModel).where(
                ContainerStopModel.team_id == self._require_team(),
                ContainerStopModel.id == id_,
            )
        )
        await self.db.flush()
