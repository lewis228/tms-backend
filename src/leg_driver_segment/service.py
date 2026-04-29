# src/leg_driver_segment/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from common.exceptions.base import NotFoundException
from leg_driver_segment.repository import LegDriverSegmentRepository
from leg_driver_segment.schemas.request import (
    LegDriverSegmentCreateRequest, LegDriverSegmentUpdateRequest,
)
from container.schemas.response import DriverSegmentResponseSchema
from leg.model import LegModel
from driver.model import DriverModel
from user.model import UserModel


class LegDriverSegmentService:
    """v3 LegDriverSegment CRUD."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = LegDriverSegmentRepository(db, team_id)

    async def _attach_name(self, row) -> DriverSegmentResponseSchema:
        name = (await self.db.execute(
            select(func.coalesce(UserModel.name, UserModel.email))
            .select_from(DriverModel)
            .outerjoin(UserModel, UserModel.id == DriverModel.user_id)
            .where(DriverModel.id == row.driver_id)
        )).scalar()
        return DriverSegmentResponseSchema.model_validate(row).model_copy(
            update={"driver_name": name},
        )

    async def _refresh_leg_active_driver(self, leg_id: int) -> None:
        """leg.driver_id 캐시: 활성 segment 중 가장 마지막을 가리킴 (ended_at IS NULL 우선)."""
        from leg_driver_segment.model import LegDriverSegmentModel
        seg = (await self.db.execute(
            select(LegDriverSegmentModel.driver_id)
            .where(
                LegDriverSegmentModel.team_id == self.team_id,
                LegDriverSegmentModel.leg_id == leg_id,
                LegDriverSegmentModel.is_active.is_(True),
                LegDriverSegmentModel.ended_at.is_(None),
            )
            .order_by(LegDriverSegmentModel.sequence_no.desc())
            .limit(1)
        )).scalar_one_or_none()
        if seg is None:
            seg = (await self.db.execute(
                select(LegDriverSegmentModel.driver_id)
                .where(
                    LegDriverSegmentModel.team_id == self.team_id,
                    LegDriverSegmentModel.leg_id == leg_id,
                    LegDriverSegmentModel.is_active.is_(True),
                )
                .order_by(LegDriverSegmentModel.sequence_no.desc())
                .limit(1)
            )).scalar_one_or_none()
        # leg 캐시 갱신
        leg = (await self.db.execute(
            select(LegModel).where(
                LegModel.team_id == self.team_id, LegModel.id == leg_id
            )
        )).scalar_one_or_none()
        if leg is not None:
            leg.driver_id = seg
            await self.db.flush()

    async def list_by_leg(self, leg_id: int) -> List[DriverSegmentResponseSchema]:
        rows = await self.repo.list_by_leg(leg_id)
        out = []
        for r in rows:
            out.append(await self._attach_name(r))
        return out

    async def create(
        self, payload: LegDriverSegmentCreateRequest, actor_user_id: int | None = None,
    ) -> DriverSegmentResponseSchema:
        from realtime.v3_publish import safe_publish, EVT_LEG_SEGMENT_CREATED
        data = payload.model_dump()
        if data.get("sequence_no") is None:
            data["sequence_no"] = await self.repo.next_sequence_no(data["leg_id"])
        row = await self.repo.create(data, actor_user_id=actor_user_id)
        await self._refresh_leg_active_driver(row.leg_id)
        await safe_publish(
            type=EVT_LEG_SEGMENT_CREATED, team_id=self.team_id, actor_id=actor_user_id,
            payload={"segment_id": row.id, "leg_id": row.leg_id, "driver_id": row.driver_id},
        )
        return await self._attach_name(row)

    async def update(
        self, id_: int, payload: LegDriverSegmentUpdateRequest, actor_user_id: int | None = None,
    ) -> DriverSegmentResponseSchema:
        from realtime.v3_publish import safe_publish, EVT_LEG_SEGMENT_UPDATED
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(id_, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("Driver Segment")
        await self._refresh_leg_active_driver(row.leg_id)
        await safe_publish(
            type=EVT_LEG_SEGMENT_UPDATED, team_id=self.team_id, actor_id=actor_user_id,
            payload={"segment_id": row.id, "leg_id": row.leg_id, "driver_id": row.driver_id},
        )
        return await self._attach_name(row)

    async def delete(self, id_: int, actor_user_id: int | None = None) -> bool:
        from realtime.v3_publish import safe_publish, EVT_LEG_SEGMENT_DELETED
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Driver Segment")
        leg_id = row.leg_id
        await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
        await self._refresh_leg_active_driver(leg_id)
        await safe_publish(
            type=EVT_LEG_SEGMENT_DELETED, team_id=self.team_id, actor_id=actor_user_id,
            payload={"segment_id": id_, "leg_id": leg_id},
        )
        return True
