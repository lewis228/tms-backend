# src/leg_layer/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from common.repository.team_scoped import TeamScopedRepoMixin
from leg_layer.model import LegAddonModel, LegChargeEventModel, LegStopOffModel
from leg_layer.const.status import LegChargeEventCode


class LegLayerRepository(TeamScopedRepoMixin):
    """Leg 3-Layer(addon/charge_event/stop_off) 리포지토리 — leg 스코프 child 관리.

    삭제는 하드(child config 라인). leg 삭제 시 복합FK CASCADE 로 자동 정리.
    """

    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db

    # ── 공통 helper ─────────────────────────────────────────────
    async def _add(self, row):
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    # ── Add-on ──────────────────────────────────────────────────
    async def list_addons(self, leg_id: int) -> List[LegAddonModel]:
        q = select(LegAddonModel).where(
            LegAddonModel.team_id == self._require_team(),
            LegAddonModel.leg_id == leg_id,
        ).order_by(LegAddonModel.id.asc())
        return list((await self.db.execute(q)).scalars().all())

    async def get_addon(self, addon_id: int) -> Optional[LegAddonModel]:
        q = select(LegAddonModel).where(
            LegAddonModel.team_id == self._require_team(), LegAddonModel.id == addon_id,
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def create_addon(self, payload: dict, actor_user_id: int | None = None) -> LegAddonModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        return await self._add(LegAddonModel(**payload))

    async def update_addon(self, row: LegAddonModel, payload: dict, actor_user_id: int | None = None) -> LegAddonModel:
        for k, v in payload.items():
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete_addon(self, addon_id: int) -> None:
        await self.db.execute(delete(LegAddonModel).where(
            LegAddonModel.team_id == self._require_team(), LegAddonModel.id == addon_id,
        ))
        await self.db.flush()

    # ── Charge Event ────────────────────────────────────────────
    async def list_charge_events(self, leg_id: int) -> List[LegChargeEventModel]:
        q = select(LegChargeEventModel).where(
            LegChargeEventModel.team_id == self._require_team(),
            LegChargeEventModel.leg_id == leg_id,
        ).order_by(LegChargeEventModel.id.asc())
        return list((await self.db.execute(q)).scalars().all())

    async def find_charge_event(self, leg_id: int, code: LegChargeEventCode) -> Optional[LegChargeEventModel]:
        q = select(LegChargeEventModel).where(
            LegChargeEventModel.team_id == self._require_team(),
            LegChargeEventModel.leg_id == leg_id,
            LegChargeEventModel.code == code,
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def upsert_charge_event(self, payload: dict, actor_user_id: int | None = None) -> LegChargeEventModel:
        existing = await self.find_charge_event(payload["leg_id"], payload["code"])
        if existing is not None:
            for k, v in payload.items():
                if k in {"leg_id", "code"}:
                    continue
                setattr(existing, k, v)
            if actor_user_id is not None:
                existing.updated_by_user_id = actor_user_id
            await self.db.flush()
            await self.db.refresh(existing)
            return existing
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        return await self._add(LegChargeEventModel(**payload))

    async def delete_charge_event(self, event_id: int) -> None:
        await self.db.execute(delete(LegChargeEventModel).where(
            LegChargeEventModel.team_id == self._require_team(), LegChargeEventModel.id == event_id,
        ))
        await self.db.flush()

    # ── Stop Off ────────────────────────────────────────────────
    async def list_stop_offs(self, leg_id: int) -> List[LegStopOffModel]:
        q = select(LegStopOffModel).where(
            LegStopOffModel.team_id == self._require_team(),
            LegStopOffModel.leg_id == leg_id,
        ).order_by(LegStopOffModel.seq.asc(), LegStopOffModel.id.asc())
        return list((await self.db.execute(q)).scalars().all())

    async def get_stop_off(self, stop_id: int) -> Optional[LegStopOffModel]:
        q = select(LegStopOffModel).where(
            LegStopOffModel.team_id == self._require_team(), LegStopOffModel.id == stop_id,
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def create_stop_off(self, payload: dict, actor_user_id: int | None = None) -> LegStopOffModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        return await self._add(LegStopOffModel(**payload))

    async def update_stop_off(self, row: LegStopOffModel, payload: dict, actor_user_id: int | None = None) -> LegStopOffModel:
        for k, v in payload.items():
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete_stop_off(self, stop_id: int) -> None:
        await self.db.execute(delete(LegStopOffModel).where(
            LegStopOffModel.team_id == self._require_team(), LegStopOffModel.id == stop_id,
        ))
        await self.db.flush()
