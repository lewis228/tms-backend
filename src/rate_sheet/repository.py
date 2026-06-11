# src/rate_sheet/repository.py
from __future__ import annotations
from typing import Optional, List
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from rate_sheet.model import RateSheetModel, RateEntryModel, RateEntryHistoryModel
from rate_sheet.const.status import SheetKind, RateMoveType, RateEntryAction
from rate_sheet.schemas.request import PaginateRateSheetRequest
from rate_sheet.schemas.response import RateSheetResponseSchema


# 셀 좌표 키 (rate_entry 컬럼명과 동일) — from→to (zone/city). 사이즈는 정산에 무관(폐기).
_CELL_KEYS = ("from_zone_id", "to_zone_id", "from_city", "from_state", "to_city", "to_state")


def _cell_conditions(cell: dict):
    """셀 좌표 dict → SQL 조건들 (None 은 IS NULL 매칭)."""
    conds = []
    for k in _CELL_KEYS:
        col = getattr(RateEntryModel, k)
        v = cell.get(k)
        conds.append(col.is_(None) if v is None else col == v)
    return conds


class RateSheetRepository(TeamScopedRepoMixin):
    """RateSheet(슬롯) + RateEntry(셀, append-only 버전) + RateEntryHistory 리포지토리."""

    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    # ═══════════════ Sheet (슬롯) ═══════════════
    async def create_sheet(self, payload: dict, actor_user_id: int | None = None) -> RateSheetModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = RateSheetModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get_sheet(self, sheet_id: int) -> Optional[RateSheetModel]:
        q = select(RateSheetModel).where(
            RateSheetModel.team_id == self._require_team(),
            RateSheetModel.id == sheet_id,
            RateSheetModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def list_sheets_by_group(self, rate_group_id: int) -> List[RateSheetModel]:
        """그룹의 활성 시트 전부(리스트/매트릭스 플랫 조회용)."""
        q = select(RateSheetModel).where(
            RateSheetModel.team_id == self._require_team(),
            RateSheetModel.rate_group_id == rate_group_id,
            RateSheetModel.is_active.is_(True),
        ).order_by(RateSheetModel.id.asc())
        return list((await self.db.execute(q)).scalars().all())

    async def find_slot(
        self, rate_group_id: int, kind: SheetKind,
        move_type: RateMoveType | None,
        service_type=None,
    ) -> Optional[RateSheetModel]:
        """슬롯 식별자로 기존 시트 조회 (중복 생성 방지 + 해석).

        재설계(Zone×Zone): 슬롯 = (group, kind, move_type, service_type). row_point 폐기.
        service_type None 이면 service_type 무관(NULL) 슬롯.
        """
        conds = [
            RateSheetModel.team_id == self._require_team(),
            RateSheetModel.rate_group_id == rate_group_id,
            RateSheetModel.kind == kind,
            RateSheetModel.is_active.is_(True),
            RateSheetModel.move_type.is_(None) if move_type is None else RateSheetModel.move_type == move_type,
            RateSheetModel.service_type.is_(None) if service_type is None else RateSheetModel.service_type == service_type,
        ]
        return (await self.db.execute(select(RateSheetModel).where(*conds))).scalar_one_or_none()

    async def get_paginated(self, request: PaginateRateSheetRequest):
        team_id = self._require_team()
        base = [RateSheetModel.team_id == team_id]
        if not request.include_inactive:
            base.append(RateSheetModel.is_active.is_(True))
        result = await self._common_service.paginate(
            request=request, model=RateSheetModel, session=self.db,
            base_query=select(RateSheetModel).where(*base),
        )
        return result

    async def update_sheet(self, sheet_id: int, payload: dict, actor_user_id: int | None = None) -> Optional[RateSheetModel]:
        row = await self.get_sheet(sheet_id)
        if not row:
            return None
        for k, v in payload.items():
            if k in {"id", "team_id", "is_active", "created_at", "created_by_user_id",
                     "rate_group_id", "kind", "move_type", "service_type"}:
                continue
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def soft_deactivate_sheet(self, sheet_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(RateSheetModel).where(
                RateSheetModel.team_id == self._require_team(),
                RateSheetModel.id == sheet_id,
                RateSheetModel.is_active.is_(True),
            ).values(**values)
        )
        await self.db.flush()

    async def count_open_entries(self, sheet_id: int) -> int:
        """현재(무제한) 유효 셀 수 — effective_to IS NULL & 활성."""
        q = select(func.count()).select_from(RateEntryModel).where(
            RateEntryModel.team_id == self._require_team(),
            RateEntryModel.rate_sheet_id == sheet_id,
            RateEntryModel.is_active.is_(True),
            RateEntryModel.effective_to.is_(None),
        )
        return int((await self.db.execute(q)).scalar_one())

    async def sync_delta(self, since):
        team_id = self._require_team()
        base_query = select(RateSheetModel).where(RateSheetModel.team_id == team_id)
        return await self._common_service.sync_delta(
            model=RateSheetModel, session=self.db, since=since,
            team_id=team_id, base_query=base_query, use_soft_delete=True,
        )

    # ═══════════════ Entry (셀 버전) ═══════════════
    async def find_open_entry(self, sheet_id: int, cell: dict, on_date: date) -> Optional[RateEntryModel]:
        """on_date 에 유효한 셀 1건 (가장 최근 effective_from)."""
        q = (
            select(RateEntryModel)
            .where(
                RateEntryModel.team_id == self._require_team(),
                RateEntryModel.rate_sheet_id == sheet_id,
                RateEntryModel.is_active.is_(True),
                *_cell_conditions(cell),
                RateEntryModel.effective_from <= on_date,
                or_(RateEntryModel.effective_to.is_(None), RateEntryModel.effective_to >= on_date),
            )
            .order_by(RateEntryModel.effective_from.desc())
            .limit(1)
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def find_next_entry(self, sheet_id: int, cell: dict, after_date: date) -> Optional[RateEntryModel]:
        """after_date 이후 시작하는 가장 이른 셀 버전 (미래 버전 캡핑용)."""
        q = (
            select(RateEntryModel)
            .where(
                RateEntryModel.team_id == self._require_team(),
                RateEntryModel.rate_sheet_id == sheet_id,
                RateEntryModel.is_active.is_(True),
                *_cell_conditions(cell),
                RateEntryModel.effective_from > after_date,
            )
            .order_by(RateEntryModel.effective_from.asc())
            .limit(1)
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def insert_entry(self, sheet_id: int, cell: dict, *, amount: Decimal | None,
                           per_unit: Decimal | None, effective_from: date, source,
                           reason: str | None, actor_user_id: int | None) -> RateEntryModel:
        row = RateEntryModel(
            team_id=self._require_team(),
            rate_sheet_id=sheet_id,
            amount=amount, per_unit=per_unit,
            effective_from=effective_from, effective_to=None,
            source=source, change_reason=reason,
            created_by_user_id=actor_user_id,
            **{k: cell.get(k) for k in _CELL_KEYS},
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def close_entry(self, entry: RateEntryModel, effective_to: date, actor_user_id: int | None = None) -> None:
        entry.effective_to = effective_to
        if actor_user_id is not None:
            entry.updated_by_user_id = actor_user_id
        await self.db.flush()

    async def supersede_entry(self, entry: RateEntryModel, actor_user_id: int | None = None) -> None:
        entry.is_active = False
        if actor_user_id is not None:
            entry.updated_by_user_id = actor_user_id
        await self.db.flush()

    async def list_entries(self, sheet_id: int, *, as_of: date | None = None,
                           only_open: bool = True) -> List[RateEntryModel]:
        conds = [
            RateEntryModel.team_id == self._require_team(),
            RateEntryModel.rate_sheet_id == sheet_id,
            RateEntryModel.is_active.is_(True),
        ]
        if as_of is not None:
            conds += [
                RateEntryModel.effective_from <= as_of,
                or_(RateEntryModel.effective_to.is_(None), RateEntryModel.effective_to >= as_of),
            ]
        elif only_open:
            conds.append(RateEntryModel.effective_to.is_(None))
        q = select(RateEntryModel).where(*conds).order_by(RateEntryModel.id.asc())
        return list((await self.db.execute(q)).scalars().all())

    # ═══════════════ History ═══════════════
    async def add_history(self, *, sheet_id: int, rate_entry_id: int | None, cell: dict,
                          old_amount, new_amount, old_per_unit, new_per_unit,
                          effective_from, action: RateEntryAction, reason: str | None,
                          actor_user_id: int | None) -> None:
        h = RateEntryHistoryModel(
            team_id=self._require_team(),
            rate_sheet_id=sheet_id, rate_entry_id=rate_entry_id,
            from_zone_id=cell.get("from_zone_id"), to_zone_id=cell.get("to_zone_id"),
            from_city=cell.get("from_city"), from_state=cell.get("from_state"),
            to_city=cell.get("to_city"), to_state=cell.get("to_state"),
            old_amount=old_amount, new_amount=new_amount,
            old_per_unit=old_per_unit, new_per_unit=new_per_unit,
            effective_from=effective_from, action=action, reason=reason,
            created_by_user_id=actor_user_id,
        )
        self.db.add(h)
        await self.db.flush()

    async def list_history(self, sheet_id: int) -> List[RateEntryHistoryModel]:
        q = (
            select(RateEntryHistoryModel)
            .where(
                RateEntryHistoryModel.team_id == self._require_team(),
                RateEntryHistoryModel.rate_sheet_id == sheet_id,
            )
            .order_by(RateEntryHistoryModel.id.desc())
            .limit(500)
        )
        return list((await self.db.execute(q)).scalars().all())
