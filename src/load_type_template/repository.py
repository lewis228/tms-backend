# src/load_type_template/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from load_type_template.model import LoadTypeTemplateModel, LoadTypeTemplateStepModel
from load_type_template.schemas.request import PaginateLoadTypeTemplateRequest
from load_type_template.schemas.response import LoadTypeTemplateResponseSchema


class LoadTypeTemplateRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def create(self, header: dict, steps: List[dict], actor_user_id: int | None = None) -> LoadTypeTemplateModel:
        team_id = self._require_team()
        header["team_id"] = team_id
        if actor_user_id is not None:
            header["created_by_user_id"] = actor_user_id
        tpl = LoadTypeTemplateModel(**header)
        self.db.add(tpl)
        await self.db.flush()
        for s in steps:
            self.db.add(LoadTypeTemplateStepModel(team_id=team_id, template_id=tpl.id, created_by_user_id=actor_user_id, **s))
        await self.db.flush()
        return await self.get_with_steps(tpl.id)

    async def get_with_steps(self, tpl_id: int) -> Optional[LoadTypeTemplateModel]:
        q = (
            select(LoadTypeTemplateModel)
            .where(
                LoadTypeTemplateModel.team_id == self._require_team(),
                LoadTypeTemplateModel.id == tpl_id,
                LoadTypeTemplateModel.is_active.is_(True),
            )
            .options(selectinload(LoadTypeTemplateModel.steps))
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_header(self, tpl_id: int) -> Optional[LoadTypeTemplateModel]:
        q = select(LoadTypeTemplateModel).where(
            LoadTypeTemplateModel.team_id == self._require_team(),
            LoadTypeTemplateModel.id == tpl_id,
            LoadTypeTemplateModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def find_by_code(self, code: str) -> Optional[LoadTypeTemplateModel]:
        q = select(LoadTypeTemplateModel).where(
            LoadTypeTemplateModel.team_id == self._require_team(),
            LoadTypeTemplateModel.code == code,
            LoadTypeTemplateModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_paginated(self, request: PaginateLoadTypeTemplateRequest):
        team_id = self._require_team()
        base = [LoadTypeTemplateModel.team_id == team_id]
        if not request.include_inactive:
            base.append(LoadTypeTemplateModel.is_active.is_(True))
        return await self._common_service.paginate(
            request=request, model=LoadTypeTemplateModel, session=self.db,
            base_query=select(LoadTypeTemplateModel).where(*base),
        )

    async def update_header(self, tpl_id: int, payload: dict, actor_user_id: int | None = None) -> Optional[LoadTypeTemplateModel]:
        tpl = await self.get_header(tpl_id)
        if not tpl:
            return None
        for k, v in payload.items():
            if k in {"id", "team_id", "is_active", "created_at", "created_by_user_id", "code"}:
                continue
            setattr(tpl, k, v)
        if actor_user_id is not None:
            tpl.updated_by_user_id = actor_user_id
        await self.db.flush()
        return await self.get_with_steps(tpl_id)

    async def replace_steps(self, tpl_id: int, steps: List[dict], actor_user_id: int | None = None) -> LoadTypeTemplateModel:
        team_id = self._require_team()
        await self.db.execute(
            delete(LoadTypeTemplateStepModel).where(
                LoadTypeTemplateStepModel.team_id == team_id,
                LoadTypeTemplateStepModel.template_id == tpl_id,
            )
        )
        for s in steps:
            self.db.add(LoadTypeTemplateStepModel(team_id=team_id, template_id=tpl_id, created_by_user_id=actor_user_id, **s))
        await self.db.flush()
        return await self.get_with_steps(tpl_id)

    async def soft_deactivate_by_id(self, tpl_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(LoadTypeTemplateModel).where(
                LoadTypeTemplateModel.team_id == self._require_team(),
                LoadTypeTemplateModel.id == tpl_id,
                LoadTypeTemplateModel.is_active.is_(True),
            ).values(**values)
        )
        await self.db.flush()

    async def sync_delta(self, since):
        team_id = self._require_team()
        base_query = select(LoadTypeTemplateModel).where(LoadTypeTemplateModel.team_id == team_id)
        return await self._common_service.sync_delta(
            model=LoadTypeTemplateModel, session=self.db, since=since,
            team_id=team_id, base_query=base_query, use_soft_delete=True,
        )
