# src/leg_layer/service.py
from __future__ import annotations
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, ConflictException
from leg_layer.repository import LegLayerRepository
from leg_layer.schemas.request import (
    LegAddonCreateRequest, LegAddonUpdateRequest,
    LegChargeEventUpsertRequest, LegStopOffCreateRequest, LegStopOffUpdateRequest,
)
from leg_layer.schemas.response import (
    LegAddonResponseSchema, LegChargeEventResponseSchema, LegStopOffResponseSchema,
    LegLayerDeleteResponseSchema,
)


class LegLayerService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = LegLayerRepository(db, team_id)

    # ── Add-on ──────────────────────────────────────────────────
    async def list_addons(self, leg_id: int) -> List[LegAddonResponseSchema]:
        return [LegAddonResponseSchema.model_validate(r) for r in await self.repo.list_addons(leg_id)]

    async def add_addon(self, payload: LegAddonCreateRequest, actor_user_id: int | None = None) -> LegAddonResponseSchema:
        existing = [a for a in await self.repo.list_addons(payload.leg_id) if a.code == payload.code]
        if existing:
            raise ConflictException(f"이미 추가된 Add-on: {payload.code.value}")
        row = await self.repo.create_addon(payload.model_dump(), actor_user_id=actor_user_id)
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

    # ── Charge Event ────────────────────────────────────────────
    async def list_charge_events(self, leg_id: int) -> List[LegChargeEventResponseSchema]:
        return [LegChargeEventResponseSchema.model_validate(r) for r in await self.repo.list_charge_events(leg_id)]

    async def upsert_charge_event(self, payload: LegChargeEventUpsertRequest, actor_user_id: int | None = None) -> LegChargeEventResponseSchema:
        row = await self.repo.upsert_charge_event(payload.model_dump(), actor_user_id=actor_user_id)
        return LegChargeEventResponseSchema.model_validate(row)

    async def delete_charge_event(self, event_id: int) -> LegLayerDeleteResponseSchema:
        await self.repo.delete_charge_event(event_id)
        return LegLayerDeleteResponseSchema(id=event_id)

    # ── Stop Off ────────────────────────────────────────────────
    async def list_stop_offs(self, leg_id: int) -> List[LegStopOffResponseSchema]:
        return [LegStopOffResponseSchema.model_validate(r) for r in await self.repo.list_stop_offs(leg_id)]

    async def add_stop_off(self, payload: LegStopOffCreateRequest, actor_user_id: int | None = None) -> LegStopOffResponseSchema:
        row = await self.repo.create_stop_off(payload.model_dump(), actor_user_id=actor_user_id)
        return LegStopOffResponseSchema.model_validate(row)

    async def update_stop_off(self, stop_id: int, payload: LegStopOffUpdateRequest, actor_user_id: int | None = None) -> LegStopOffResponseSchema:
        row = await self.repo.get_stop_off(stop_id)
        if not row:
            raise NotFoundException("Leg Stop Off")
        row = await self.repo.update_stop_off(row, payload.model_dump(exclude_unset=True), actor_user_id=actor_user_id)
        return LegStopOffResponseSchema.model_validate(row)

    async def delete_stop_off(self, stop_id: int) -> LegLayerDeleteResponseSchema:
        if not await self.repo.get_stop_off(stop_id):
            raise NotFoundException("Leg Stop Off")
        await self.repo.delete_stop_off(stop_id)
        return LegLayerDeleteResponseSchema(id=stop_id)
