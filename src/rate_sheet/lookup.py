# src/rate_sheet/lookup.py
"""요율 조회 엔진 — work_date 기준 셀 단가 해석.

셀 단위 해석만 담당(시트/셀 좌표 + work_date). 드라이버→유효그룹→method→시트 선택과
컨테이너 배율 적용 등 leg 단위 종합 해석(resolve_leg_rate)은 leg 재설계(Phase 3) 에서
이 모듈의 resolve_cell 을 호출해 조립한다.
"""
from __future__ import annotations
from datetime import date

from rate_sheet.repository import RateSheetRepository
from rate_sheet.schemas.response import RateLookupResultSchema


async def resolve_cell(
    repo: RateSheetRepository, sheet_id: int, cell: dict, work_date: date,
) -> RateLookupResultSchema:
    """work_date 에 유효한 셀 값을 찾는다. 없으면 found=False + 경고 메시지."""
    entry = await repo.find_open_entry(sheet_id, cell, work_date)
    if entry is None:
        return RateLookupResultSchema(
            found=False,
            message=f"요율 미등록: sheet={sheet_id}, date={work_date.isoformat()} 구간에 등록된 요율이 없습니다.",
        )
    return RateLookupResultSchema(
        found=True,
        amount=entry.amount,
        per_unit=entry.per_unit,
        rate_entry_id=entry.id,
        effective_from=entry.effective_from,
    )
