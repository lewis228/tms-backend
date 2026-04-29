# src/leg_driver_segment/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from common.repository.team_scoped import TeamScopedRepoMixin
from leg_driver_segment.model import LegDriverSegmentModel


class LegDriverSegmentRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db

    async def create(self, payload: dict, actor_user_id: int | None = None) -> LegDriverSegmentModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = LegDriverSegmentModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, id_: int) -> Optional[LegDriverSegmentModel]:
        q = select(LegDriverSegmentModel).where(
            LegDriverSegmentModel.team_id == self._require_team(),
            LegDriverSegmentModel.id == id_,
            LegDriverSegmentModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def list_by_leg(self, leg_id: int) -> List[LegDriverSegmentModel]:
        q = (
            select(LegDriverSegmentModel)
            .where(
                LegDriverSegmentModel.team_id == self._require_team(),
                LegDriverSegmentModel.leg_id == leg_id,
                LegDriverSegmentModel.is_active.is_(True),
            )
            .order_by(LegDriverSegmentModel.sequence_no.asc(), LegDriverSegmentModel.id.asc())
        )
        return list((await self.db.execute(q)).scalars().all())

    async def next_sequence_no(self, leg_id: int) -> int:
        q = select(func.max(LegDriverSegmentModel.sequence_no)).where(
            LegDriverSegmentModel.team_id == self._require_team(),
            LegDriverSegmentModel.leg_id == leg_id,
        )
        return ((await self.db.execute(q)).scalar() or 0) + 1

    async def update(
        self, id_: int, payload: dict, actor_user_id: int | None = None,
    ) -> Optional[LegDriverSegmentModel]:
        if not payload:
            return await self.get(id_)
        q = select(LegDriverSegmentModel).where(
            LegDriverSegmentModel.team_id == self._require_team(),
            LegDriverSegmentModel.id == id_,
            LegDriverSegmentModel.is_active.is_(True),
        )
        row = (await self.db.execute(q)).scalar_one_or_none()
        if not row:
            return None
        protected = {"id", "team_id", "is_active", "created_at", "created_by_user_id", "leg_id", "sequence_no"}
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
            update(LegDriverSegmentModel).where(
                LegDriverSegmentModel.team_id == self._require_team(),
                LegDriverSegmentModel.id == id_,
                LegDriverSegmentModel.is_active.is_(True),
            ).values(**values)
        )
        await self.db.flush()
