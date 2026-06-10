# src/delivery_order/addon_service.py
"""D/O 단위 Add-on 서비스 (고객 청구용). leg add-on 과 동일 패턴, D/O 스코프."""
from __future__ import annotations
from decimal import Decimal
from typing import List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.repository.team_scoped import TeamScopedRepoMixin
from delivery_order.addon_model import DeliveryOrderAddonModel
from delivery_order.addon_schemas import (
    DoAddonCreateRequest, DoAddonUpdateRequest, DoAddonResponseSchema, DoAddonDeleteResponseSchema,
)
from leg_layer.charge import resolve_addon_amount


class DoAddonService(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int):
        super().__init__(team_id)
        self.db = db

    async def list_addons(self, do_id: int) -> List[DoAddonResponseSchema]:
        q = select(DeliveryOrderAddonModel).where(
            DeliveryOrderAddonModel.team_id == self._require_team(),
            DeliveryOrderAddonModel.delivery_order_id == do_id,
            DeliveryOrderAddonModel.is_active.is_(True),
        ).order_by(DeliveryOrderAddonModel.id.asc())
        return [DoAddonResponseSchema.model_validate(r) for r in (await self.db.execute(q)).scalars().all()]

    async def add_addon(self, payload: DoAddonCreateRequest, actor_user_id: int | None = None) -> DoAddonResponseSchema:
        data = payload.model_dump()
        if data.get("amount") in (None, Decimal("0")):
            filled = await resolve_addon_amount(self.db, self._require_team(), payload.code)  # D/O = driver 없음 → 팀 기본
            if filled is not None:
                data["amount"], data["unit_amount"], data["quantity"] = filled
        if data.get("amount") is None:
            data["amount"] = Decimal("0")
        data["team_id"] = self._require_team()
        if actor_user_id is not None:
            data["created_by_user_id"] = actor_user_id
        row = DeliveryOrderAddonModel(**data)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return DoAddonResponseSchema.model_validate(row)

    async def _get(self, addon_id: int) -> DeliveryOrderAddonModel | None:
        q = select(DeliveryOrderAddonModel).where(
            DeliveryOrderAddonModel.team_id == self._require_team(),
            DeliveryOrderAddonModel.id == addon_id,
            DeliveryOrderAddonModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def update_addon(self, addon_id: int, payload: DoAddonUpdateRequest, actor_user_id: int | None = None) -> DoAddonResponseSchema:
        row = await self._get(addon_id)
        if not row:
            raise NotFoundException("D/O Add-on")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return DoAddonResponseSchema.model_validate(row)

    async def delete_addon(self, addon_id: int) -> DoAddonDeleteResponseSchema:
        if not await self._get(addon_id):
            raise NotFoundException("D/O Add-on")
        await self.db.execute(delete(DeliveryOrderAddonModel).where(
            DeliveryOrderAddonModel.team_id == self._require_team(),
            DeliveryOrderAddonModel.id == addon_id,
        ))
        await self.db.flush()
        return DoAddonDeleteResponseSchema(id=addon_id)
