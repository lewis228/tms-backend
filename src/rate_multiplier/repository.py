# src/rate_multiplier/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from common.repository.team_scoped import TeamScopedRepoMixin
from rate_multiplier.model import RateMultiplierModel
from rate_sheet.const.status import RateContainerSize


class RateMultiplierRepository(TeamScopedRepoMixin):
    """컨테이너 배율 리포지토리 (scope = 팀 전역 / 그룹 override)."""

    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db

    async def get(self, multiplier_id: int) -> Optional[RateMultiplierModel]:
        q = select(RateMultiplierModel).where(
            RateMultiplierModel.team_id == self._require_team(),
            RateMultiplierModel.id == multiplier_id,
            RateMultiplierModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def find_scope(
        self, rate_group_id: int | None, container_size: RateContainerSize
    ) -> Optional[RateMultiplierModel]:
        q = select(RateMultiplierModel).where(
            RateMultiplierModel.team_id == self._require_team(),
            RateMultiplierModel.is_active.is_(True),
            RateMultiplierModel.container_size == container_size,
            RateMultiplierModel.rate_group_id.is_(None) if rate_group_id is None
            else RateMultiplierModel.rate_group_id == rate_group_id,
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def list_all(
        self, rate_group_id: int | None = None, include_inactive: bool = False
    ) -> List[RateMultiplierModel]:
        conds = [RateMultiplierModel.team_id == self._require_team()]
        if not include_inactive:
            conds.append(RateMultiplierModel.is_active.is_(True))
        if rate_group_id is not None:
            conds.append(RateMultiplierModel.rate_group_id == rate_group_id)
        q = select(RateMultiplierModel).where(*conds).order_by(RateMultiplierModel.id.asc())
        return list((await self.db.execute(q)).scalars().all())

    async def create(self, payload: dict, actor_user_id: int | None = None) -> RateMultiplierModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = RateMultiplierModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def update_row(self, row: RateMultiplierModel, payload: dict, actor_user_id: int | None = None) -> RateMultiplierModel:
        for k, v in payload.items():
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def soft_deactivate_by_id(self, multiplier_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(RateMultiplierModel).where(
                RateMultiplierModel.team_id == self._require_team(),
                RateMultiplierModel.id == multiplier_id,
                RateMultiplierModel.is_active.is_(True),
            ).values(**values)
        )
        await self.db.flush()
