# src/rate_group/entry_service.py
"""그룹 단위 플랫 행 요율 입력/조회 — 리스트 뷰(이미지3) + Excel 임포트의 진입점.

ste 규약: 서비스가 다른 도메인 Repository 직접 주입(서비스→서비스 호출 지양).
플랫 행 1개 = rate_entry 셀 1개. (group, kind, move, service) 시트를 찾거나 만들고
versioning.set_rate 로 append-only 등록. kind 는 group.method 에서 파생.
"""
from __future__ import annotations
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, BadRequestException
from realtime.emit import emit_entity_event
from rate_group.repository import RateGroupRepository
from rate_group.const.status import RateMethod
from rate_group.schemas.request import FlatRateEntryRequest, BulkFlatRateEntryRequest
from rate_group.schemas.response import FlatRateEntrySchema, RateGroupEntriesResponse
from rate_sheet.repository import RateSheetRepository
from rate_sheet import versioning
from rate_sheet.const.status import SheetKind, RateMoveType

_LABEL = "Rate Group"

# group.method ↔ rate_sheet.kind (값 동일)
_METHOD_TO_KIND = {
    RateMethod.ZIP: SheetKind.ZIP,
    RateMethod.CITY: SheetKind.CITY,
    RateMethod.MILE: SheetKind.MILE,
    RateMethod.HOURLY: SheetKind.HOURLY,
}


def _cell_from_flat(row: FlatRateEntryRequest, kind: SheetKind) -> dict:
    """플랫 행 → rate_entry 셀 좌표 dict.

    양측 각각 zip|zone|city 혼합 허용 (사다리 ①·② 셀).
    MILE/HOURLY 는 전 좌표 None. 양방향 정규화는 versioning.set_rate 가 수행.
    """
    if kind in (SheetKind.ZIP, SheetKind.CITY):
        return {
            "from_zip": row.from_zip, "to_zip": row.to_zip,
            "from_zone_id": row.from_zone_id, "to_zone_id": row.to_zone_id,
            "from_city": row.from_city, "from_state": row.from_state,
            "to_city": row.to_city, "to_state": row.to_state,
        }
    # MILE / HOURLY
    return {
        "from_zip": None, "to_zip": None,
        "from_zone_id": None, "to_zone_id": None,
        "from_city": None, "from_state": None, "to_city": None, "to_state": None,
    }


class RateGroupEntryService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.group_repo = RateGroupRepository(db, team_id)
        self.sheet_repo = RateSheetRepository(db, team_id)

    async def _resolve_kind(self, group_id: int) -> tuple[int, RateMethod, SheetKind]:
        group = await self.group_repo.get(group_id)
        if not group:
            raise NotFoundException(_LABEL)
        return group.id, group.method, _METHOD_TO_KIND[group.method]

    async def _ensure_sheet(self, group_id: int, kind: SheetKind, row: FlatRateEntryRequest) -> int:
        """(group, kind, move, service) 시트를 찾거나 생성하고 sheet_id 반환."""
        if kind in (SheetKind.ZIP, SheetKind.CITY):
            if row.move_type is None:
                raise BadRequestException("ZIP/CITY 행은 move_type 이 필요합니다.")
            move_type: RateMoveType | None = row.move_type
            service_type = row.service_type
        else:  # MILE / HOURLY
            move_type = None
            service_type = None
        sheet = await self.sheet_repo.find_slot(group_id, kind, move_type, service_type=service_type)
        if sheet is None:
            sheet = await self.sheet_repo.create_sheet({
                "rate_group_id": group_id, "kind": kind,
                "move_type": move_type, "service_type": service_type,
            })
        return sheet.id

    async def set_entry(self, group_id: int, row: FlatRateEntryRequest, actor_user_id: int | None = None,
                        emit: bool = True) -> FlatRateEntrySchema:
        _, _method, kind = await self._resolve_kind(group_id)
        sheet_id = await self._ensure_sheet(group_id, kind, row)
        cell = _cell_from_flat(row, kind)
        # 존 좌표 검증 — 존재/팀/kind/스코프 (죽은 셀 차단). API 직접 호출·CSV import 공통.
        await versioning.validate_cell_zone_refs(
            self.db, self.team_id, cell, sheet_kind=kind, rate_group_id=group_id)
        entry = await versioning.set_rate(
            self.sheet_repo, sheet_id, cell,
            amount=row.amount, per_unit=row.per_unit,
            effective_from=row.effective_from, source=row.source,
            reason=row.reason, actor_user_id=actor_user_id,
        )
        if emit:  # bulk/import/seed 는 건별 발행 대신 호출부에서 1회 발행
            await emit_entity_event("rate_sheet.updated", self.team_id,
                                    {"rateGroupId": group_id, "rateSheetId": sheet_id}, actor_user_id)
        return FlatRateEntrySchema(
            rate_entry_id=entry.id, rate_sheet_id=sheet_id, kind=kind,
            move_type=row.move_type if kind in (SheetKind.ZIP, SheetKind.CITY) else None,
            service_type=row.service_type if kind in (SheetKind.ZIP, SheetKind.CITY) else None,
            from_zip=entry.from_zip, to_zip=entry.to_zip,
            from_zone_id=entry.from_zone_id, to_zone_id=entry.to_zone_id,
            from_city=entry.from_city, from_state=entry.from_state,
            to_city=entry.to_city, to_state=entry.to_state,
            amount=entry.amount, per_unit=entry.per_unit,
            effective_from=entry.effective_from, effective_to=entry.effective_to,
        )

    async def set_entries_bulk(self, group_id: int, payload: BulkFlatRateEntryRequest, actor_user_id: int | None = None) -> List[FlatRateEntrySchema]:
        out: List[FlatRateEntrySchema] = []
        for row in payload.items:
            out.append(await self.set_entry(group_id, row, actor_user_id=actor_user_id, emit=False))
        await emit_entity_event("rate_sheet.updated", self.team_id,
                                {"rateGroupId": group_id}, actor_user_id)
        return out

    async def list_entries(self, group_id: int) -> RateGroupEntriesResponse:
        """그룹의 모든 시트의 현재 유효 셀을 플랫 행으로 평탄화(리스트 뷰)."""
        _, method, _kind = await self._resolve_kind(group_id)
        sheets = await self.sheet_repo.list_sheets_by_group(group_id)
        rows: List[FlatRateEntrySchema] = []
        for sheet in sheets:
            entries = await self.sheet_repo.list_entries(sheet.id, only_open=True)
            for e in entries:
                rows.append(FlatRateEntrySchema(
                    rate_entry_id=e.id, rate_sheet_id=sheet.id, kind=sheet.kind,
                    move_type=sheet.move_type, service_type=sheet.service_type,
                    from_zip=e.from_zip, to_zip=e.to_zip,
                    from_zone_id=e.from_zone_id, to_zone_id=e.to_zone_id,
                    from_city=e.from_city, from_state=e.from_state,
                    to_city=e.to_city, to_state=e.to_state,
                    amount=e.amount, per_unit=e.per_unit,
                    effective_from=e.effective_from, effective_to=e.effective_to,
                ))
        return RateGroupEntriesResponse(rate_group_id=group_id, method=method, rows=rows)
