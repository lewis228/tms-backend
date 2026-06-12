# src/rate_sheet/versioning.py
"""요율 셀(rate_entry) 유효일자 버전관리 — append-only set_rate.

핵심 규약 (컨플루언스 + 우리 결정):
- 셀 값을 바꿔도 이전 기록은 절대 UPDATE 하지 않는다.
- 변경 시 effective_from(>= 가능; 당일/이후) 을 지정 → 기존 유효 버전을 그 전날로 close,
  같은 시작일이면 기존 버전을 supersede(is_active=False) 후 새 버전 insert.
- 미래에 이미 등록된 버전이 있으면 새 버전의 effective_to 를 그 전날로 capping.
- 공백 구간(요율 미등록일) 은 lookup 에서 found=False → 정산 시 "미등록" 경고.
- 셀은 양방향(↔) — 진입 시 lane.normalize_cell 로 정규화하므로 역순 입력도 같은 셀.
"""
from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import AppException, NotFoundException
from rate_sheet.repository import RateSheetRepository
from rate_sheet.model import RateEntryModel
from rate_sheet.lane import normalize_cell
from rate_sheet.const.status import RateEntrySource, RateEntryAction, SheetKind


async def validate_cell_zone_refs(
    db: AsyncSession, team_id: int, cell: dict, *,
    sheet_kind: SheetKind, rate_group_id: int,
) -> None:
    """셀 좌표의 from_zone_id/to_zone_id 참조 검증 — set_rate 진입 전 가드.

    (a) 존재 + (b) 같은 팀(team 스코프 repo 가 강제) + (c) 시트 kind 와 존 kind 일치
    (ZIP 시트=ZIP존 / CITY 시트=도시존 — kind 강제 3층의 entry 좌표 레이어) +
    (d) 스코프 일치(글로벌 또는 해당 그룹 전용 존). 위반 시 404/422 — 해석기가
    영원히 매칭하지 못하는 죽은 셀이 만들어지는 것을 차단한다.
    """
    zone_ids = [v for v in (cell.get("from_zone_id"), cell.get("to_zone_id")) if v is not None]
    if not zone_ids:
        return
    # ste 규약: 다른 도메인 Repository 직접 주입 (지연 import — 순환참조 회피)
    from rate_zone.repository import RateZoneRepository
    from rate_zone.const.status import ZoneKind

    if sheet_kind not in (SheetKind.ZIP, SheetKind.CITY):
        raise AppException(
            code="ZONE_KIND_MISMATCH",
            message="MILE/HOURLY 시트 셀에는 존 좌표를 사용할 수 없습니다.",
            status_code=422,
        )
    expected_kind = ZoneKind.ZIP if sheet_kind == SheetKind.ZIP else ZoneKind.CITY
    zone_repo = RateZoneRepository(db, team_id)
    for zid in zone_ids:
        zone = await zone_repo.get_header(zid)
        if zone is None:
            raise NotFoundException("Rate Zone", detail={"zone_id": zid})
        if zone.kind != expected_kind:
            raise AppException(
                code="ZONE_KIND_MISMATCH",
                message=f"존 '{zone.name}'(id={zid}) 의 종류({zone.kind.value})가 "
                        f"시트 방식({sheet_kind.value})과 맞지 않습니다.",
                status_code=422,
            )
        if zone.rate_group_id is not None and zone.rate_group_id != rate_group_id:
            raise AppException(
                code="ZONE_SCOPE_MISMATCH",
                message=f"존 '{zone.name}'(id={zid}) 은(는) 다른 그룹 전용 존입니다 — "
                        "글로벌 존 또는 이 그룹 스코프 존만 셀 좌표로 쓸 수 있습니다.",
                status_code=422,
            )


async def set_rate(
    repo: RateSheetRepository,
    sheet_id: int,
    cell: dict,
    *,
    amount: Decimal | None,
    per_unit: Decimal | None,
    effective_from: date,
    source: RateEntrySource,
    reason: str | None,
    actor_user_id: int | None,
) -> RateEntryModel:
    # 0) 양방향 정규화 — 어느 방향으로 입력해도 같은 셀로 수렴 (이중 입력 차단)
    cell = normalize_cell(cell)
    # 1) effective_from 시점에 유효한 기존 버전 찾기
    existing = await repo.find_open_entry(sheet_id, cell, effective_from)
    old_amount = existing.amount if existing else None
    old_per_unit = existing.per_unit if existing else None

    if existing is not None:
        if existing.effective_from == effective_from:
            # 같은 시작일 — 기존 버전 폐기(supersede). 정산에 이미 박힌 값은 snapshot 이라 영향 없음.
            await repo.supersede_entry(existing, actor_user_id)
            await repo.add_history(
                sheet_id=sheet_id, rate_entry_id=existing.id, cell=cell,
                old_amount=old_amount, new_amount=amount,
                old_per_unit=old_per_unit, new_per_unit=per_unit,
                effective_from=effective_from, action=RateEntryAction.SUPERSEDE,
                reason=reason, actor_user_id=actor_user_id,
            )
        else:
            # 기존 버전을 새 시작일 전날로 종료(동결).
            await repo.close_entry(existing, effective_from - timedelta(days=1), actor_user_id)
            await repo.add_history(
                sheet_id=sheet_id, rate_entry_id=existing.id, cell=cell,
                old_amount=old_amount, new_amount=old_amount,
                old_per_unit=old_per_unit, new_per_unit=old_per_unit,
                effective_from=existing.effective_from, action=RateEntryAction.CLOSE,
                reason=reason, actor_user_id=actor_user_id,
            )

    # 2) 새 버전 insert
    new_entry = await repo.insert_entry(
        sheet_id, cell, amount=amount, per_unit=per_unit,
        effective_from=effective_from, source=source, reason=reason,
        actor_user_id=actor_user_id,
    )

    # 3) 미래 버전이 있으면 새 버전 종료일 capping
    future = await repo.find_next_entry(sheet_id, cell, effective_from)
    if future is not None:
        await repo.close_entry(new_entry, future.effective_from - timedelta(days=1), actor_user_id)

    # 4) SET 이력
    await repo.add_history(
        sheet_id=sheet_id, rate_entry_id=new_entry.id, cell=cell,
        old_amount=old_amount, new_amount=amount,
        old_per_unit=old_per_unit, new_per_unit=per_unit,
        effective_from=effective_from, action=RateEntryAction.SET,
        reason=reason, actor_user_id=actor_user_id,
    )
    return new_entry
