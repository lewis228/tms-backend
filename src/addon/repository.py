# src/addon/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from addon.model import AddonModel, AddonDriverRateModel
from addon.schemas.request import PaginateAddonRequest
from addon.schemas.response import AddonResponseSchema


class AddonRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def create(self, payload: dict, actor_user_id: int | None = None) -> AddonModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = AddonModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, acc_id: int) -> Optional[AddonModel]:
        q = select(AddonModel).where(
            AddonModel.team_id == self._require_team(),
            AddonModel.id == acc_id,
            AddonModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def find_for_code(self, code: str) -> Optional[AddonModel]:
        """code 의 마스터 정의 조회 (팀당 code 유일)."""
        q = select(AddonModel).where(
            AddonModel.team_id == self._require_team(),
            AddonModel.code == code,
            AddonModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    # ── 기사별 금액 override (addon_driver_rate) ────────────────
    async def get_driver_rate(self, addon_id: int, driver_id: int) -> Optional[AddonDriverRateModel]:
        q = select(AddonDriverRateModel).where(
            AddonDriverRateModel.team_id == self._require_team(),
            AddonDriverRateModel.addon_id == addon_id,
            AddonDriverRateModel.driver_id == driver_id,
            AddonDriverRateModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def list_driver_rates(self, addon_id: int) -> List[AddonDriverRateModel]:
        q = select(AddonDriverRateModel).where(
            AddonDriverRateModel.team_id == self._require_team(),
            AddonDriverRateModel.addon_id == addon_id,
            AddonDriverRateModel.is_active.is_(True),
        ).order_by(AddonDriverRateModel.id.asc())
        return list((await self.db.execute(q)).scalars().all())

    async def upsert_driver_rate(
        self, addon_id: int, driver_id: int, *, amount, percent, note: str | None,
        actor_user_id: int | None = None,
    ) -> AddonDriverRateModel:
        row = await self.get_driver_rate(addon_id, driver_id)
        if row is None:
            row = AddonDriverRateModel(
                team_id=self._require_team(), addon_id=addon_id, driver_id=driver_id,
                amount=amount, percent=percent, note=note, created_by_user_id=actor_user_id,
            )
            self.db.add(row)
        else:
            row.amount, row.percent, row.note = amount, percent, note
            if actor_user_id is not None:
                row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete_driver_rate(self, addon_id: int, driver_id: int, actor_user_id: int | None = None) -> bool:
        row = await self.get_driver_rate(addon_id, driver_id)
        if row is None:
            return False
        row.is_active = False
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        return True

    async def get_paginated(self, request: PaginateAddonRequest):
        team_id = self._require_team()
        base = [AddonModel.team_id == team_id]
        if not request.include_inactive:
            base.append(AddonModel.is_active.is_(True))
        return await self._common_service.paginate(
            request=request, model=AddonModel, session=self.db,
            base_query=select(AddonModel).where(*base),
        )

    async def update(self, acc_id: int, payload: dict, actor_user_id: int | None = None) -> Optional[AddonModel]:
        if not payload:
            return await self.get(acc_id)
        row = await self.get(acc_id)
        if not row:
            return None
        for k, v in payload.items():
            if k in {"id", "team_id", "is_active", "created_at", "created_by_user_id", "code", "driver_id"}:
                continue
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def soft_deactivate_by_id(self, acc_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(AddonModel).where(
                AddonModel.team_id == self._require_team(),
                AddonModel.id == acc_id,
                AddonModel.is_active.is_(True),
            ).values(**values)
        )
        await self.db.flush()

    async def sync_delta(self, since):
        team_id = self._require_team()
        base_query = select(AddonModel).where(AddonModel.team_id == team_id)
        return await self._common_service.sync_delta(
            model=AddonModel, session=self.db, since=since,
            team_id=team_id, base_query=base_query, use_soft_delete=True,
        )
