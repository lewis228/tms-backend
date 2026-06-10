# src/leg_layer/service.py
from __future__ import annotations
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from decimal import Decimal
from sqlalchemy import select

from common.exceptions.base import NotFoundException
from leg_layer.repository import LegLayerRepository
from leg_layer.charge import resolve_addon_amount
from leg_layer.schemas.request import (
    LegAddonCreateRequest, LegAddonUpdateRequest,
)
from leg_layer.schemas.response import (
    LegAddonResponseSchema, LegLayerDeleteResponseSchema,
)


class LegLayerService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = LegLayerRepository(db, team_id)

    # ── Add-on ──────────────────────────────────────────────────
    async def list_addons(self, leg_id: int) -> List[LegAddonResponseSchema]:
        return [LegAddonResponseSchema.model_validate(r) for r in await self.repo.list_addons(leg_id)]

    async def _get_leg(self, leg_id: int):
        from leg.model import LegModel
        q = select(LegModel).where(
            LegModel.team_id == self.repo._require_team(), LegModel.id == leg_id,
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def add_addon(self, payload: LegAddonCreateRequest, actor_user_id: int | None = None) -> LegAddonResponseSchema:
        # 컨플루언스 재정의: 같은 code 중복 허용(Stop Off ×3 등). 시스템이 amount 기본값 자동 채움.
        data = payload.model_dump()
        if data.get("amount") in (None, Decimal("0")) and data.get("amount_override") is None:
            leg = await self._get_leg(payload.leg_id)
            filled = await resolve_addon_amount(
                self.db, self.repo._require_team(), payload.code.value,
                driver_id=getattr(leg, "driver_id", None), rate_miles=getattr(leg, "rate_miles", None),
            )
            if filled is not None:
                data["amount"], data["unit_amount"], data["quantity"] = filled
        if data.get("amount") is None:
            data["amount"] = Decimal("0")
        row = await self.repo.create_addon(data, actor_user_id=actor_user_id)
        return LegAddonResponseSchema.model_validate(row)

    async def update_addon(self, addon_id: int, payload: LegAddonUpdateRequest, actor_user_id: int | None = None) -> LegAddonResponseSchema:
        row = await self.repo.get_addon(addon_id)
        if not row:
            raise NotFoundException("Leg Add-on")
        row = await self.repo.update_addon(row, payload.model_dump(exclude_unset=True), actor_user_id=actor_user_id)
        return LegAddonResponseSchema.model_validate(row)

    async def delete_addon(self, addon_id: int) -> LegLayerDeleteResponseSchema:
        if not await self.repo.get_addon(addon_id):
            raise NotFoundException("Leg Add-on")
        await self.repo.delete_addon(addon_id)
        return LegLayerDeleteResponseSchema(id=addon_id)
