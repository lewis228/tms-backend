# src/rate_sheet/service.py
from __future__ import annotations
from datetime import datetime, date
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, ConflictException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from rate_sheet.repository import RateSheetRepository, _CELL_KEYS
from rate_sheet import versioning, lookup
from rate_sheet.const.status import SheetStatus
from rate_sheet.model import RateSheetModel
from rate_sheet.schemas.request import (
    RateSheetCreateRequest, RateSheetUpdateRequest, PaginateRateSheetRequest,
    SetRateEntryRequest, BulkSetRateEntryRequest,
)
from rate_sheet.schemas.response import (
    RateSheetResponseSchema, RateSheetDetailResponseSchema, RateSheetDeleteResponseSchema,
    RateEntryResponseSchema, RateEntryHistoryResponseSchema, RateLookupResultSchema,
)

_LABEL = "Rate Sheet"


def _cell_from(req: SetRateEntryRequest) -> dict:
    return {k: getattr(req, k) for k in _CELL_KEYS}


class RateSheetService:
    """RateSheet(슬롯) + RateEntry(셀 유효일자 버전) 비즈니스 로직."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = RateSheetRepository(db, team_id)

    # ── 슬롯 status 계산 ─────────────────────────────────────────
    async def _to_response(self, sheet: RateSheetModel) -> RateSheetResponseSchema:
        open_count = await self.repo.count_open_entries(sheet.id)
        if not sheet.is_active:
            status = SheetStatus.INACTIVE
        elif open_count == 0:
            status = SheetStatus.EMPTY
        else:
            status = SheetStatus.ACTIVE
        base = RateSheetResponseSchema.model_validate(sheet)
        base.status = status
        base.open_entry_count = open_count
        return base

    # ── Sheet CRUD ──────────────────────────────────────────────
    async def create_sheet(
        self, payload: RateSheetCreateRequest, actor_user_id: int | None = None
    ) -> RateSheetResponseSchema:
        existing = await self.repo.find_slot(
            payload.rate_group_id, payload.kind, payload.move_type, payload.row_point_id,
            service_type=payload.service_type,
        )
        if existing is not None:
            raise ConflictException("이미 같은 슬롯의 Rate Sheet 가 존재합니다.")
        sheet = await self.repo.create_sheet(payload.model_dump(), actor_user_id=actor_user_id)
        return await self._to_response(sheet)

    async def get_sheet(self, sheet_id: int) -> RateSheetDetailResponseSchema:
        sheet = await self.repo.get_sheet(sheet_id)
        if not sheet:
            raise NotFoundException(_LABEL)
        base = await self._to_response(sheet)
        entries = await self.repo.list_entries(sheet_id, only_open=True)
        detail = RateSheetDetailResponseSchema(**base.model_dump())
        detail.entries = [RateEntryResponseSchema.model_validate(e) for e in entries]
        return detail

    async def list_sheets(
        self, request: PaginateRateSheetRequest
    ) -> CursorPaginationResult[RateSheetResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [await self._to_response(r) for r in result.data]
        return result

    async def update_sheet(
        self, sheet_id: int, payload: RateSheetUpdateRequest, actor_user_id: int | None = None
    ) -> RateSheetResponseSchema:
        sheet = await self.repo.update_sheet(sheet_id, payload.model_dump(exclude_unset=True), actor_user_id=actor_user_id)
        if not sheet:
            raise NotFoundException(_LABEL)
        return await self._to_response(sheet)

    async def delete_sheet(
        self, sheet_id: int, actor_user_id: int | None = None
    ) -> RateSheetDeleteResponseSchema:
        sheet = await self.repo.get_sheet(sheet_id)
        if not sheet:
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_sheet(sheet_id, actor_user_id=actor_user_id)
        return RateSheetDeleteResponseSchema(id=sheet_id, deleted=True, soft_deleted=True)

    async def sync_delta(self, since_str: str):
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)
        result.items = [RateSheetResponseSchema.model_validate(r) for r in result.items]
        return result

    # ── Entry 버전 등록 (set_rate) ──────────────────────────────
    async def set_rate(
        self, sheet_id: int, payload: SetRateEntryRequest, actor_user_id: int | None = None
    ) -> RateEntryResponseSchema:
        sheet = await self.repo.get_sheet(sheet_id)
        if not sheet:
            raise NotFoundException(_LABEL)
        entry = await versioning.set_rate(
            self.repo, sheet_id, _cell_from(payload),
            amount=payload.amount, per_unit=payload.per_unit,
            effective_from=payload.effective_from, source=payload.source,
            reason=payload.reason, actor_user_id=actor_user_id,
        )
        return RateEntryResponseSchema.model_validate(entry)

    async def set_rate_bulk(
        self, sheet_id: int, payload: BulkSetRateEntryRequest, actor_user_id: int | None = None
    ) -> List[RateEntryResponseSchema]:
        sheet = await self.repo.get_sheet(sheet_id)
        if not sheet:
            raise NotFoundException(_LABEL)
        out: List[RateEntryResponseSchema] = []
        for item in payload.items:
            entry = await versioning.set_rate(
                self.repo, sheet_id, _cell_from(item),
                amount=item.amount, per_unit=item.per_unit,
                effective_from=item.effective_from, source=item.source,
                reason=item.reason, actor_user_id=actor_user_id,
            )
            out.append(RateEntryResponseSchema.model_validate(entry))
        return out

    async def list_entries(
        self, sheet_id: int, as_of: date | None = None, only_open: bool = True
    ) -> List[RateEntryResponseSchema]:
        sheet = await self.repo.get_sheet(sheet_id)
        if not sheet:
            raise NotFoundException(_LABEL)
        rows = await self.repo.list_entries(sheet_id, as_of=as_of, only_open=only_open)
        return [RateEntryResponseSchema.model_validate(r) for r in rows]

    async def get_history(self, sheet_id: int) -> List[RateEntryHistoryResponseSchema]:
        sheet = await self.repo.get_sheet(sheet_id)
        if not sheet:
            raise NotFoundException(_LABEL)
        rows = await self.repo.list_history(sheet_id)
        return [RateEntryHistoryResponseSchema.model_validate(r) for r in rows]

    async def lookup(
        self, sheet_id: int, cell: dict, work_date: date
    ) -> RateLookupResultSchema:
        sheet = await self.repo.get_sheet(sheet_id)
        if not sheet:
            raise NotFoundException(_LABEL)
        return await lookup.resolve_cell(self.repo, sheet_id, cell, work_date)
