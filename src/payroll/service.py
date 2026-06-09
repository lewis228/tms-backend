# src/payroll/service.py
from __future__ import annotations
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, ConflictException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from payroll.repository import PayrollRepository
from payroll.resolve import resolve_leg_rate
from payroll.const.status import PayrollStatus, PayrollLineSource
from payroll.model import PayrollSettlementModel
from payroll.schemas.request import (
    PayrollBuildRequest, PayrollChargeAddRequest, PaginatePayrollRequest,
)
from payroll.schemas.response import (
    PayrollSummarySchema, PayrollDetailSchema, PayrollDeleteResponseSchema,
    PayrollLineResponseSchema, PayrollChargeResponseSchema,
    PayrollPreviewSchema, PayrollPreviewLine,
)

_LABEL = "Payroll Settlement"


def _snapshot(res) -> dict:
    return {
        "method": res.method, "amount": str(res.amount) if res.amount is not None else None,
        "per_unit": str(res.per_unit) if res.per_unit is not None else None,
        "quantity": str(res.quantity) if res.quantity is not None else None,
        "multiplier": str(res.multiplier) if res.multiplier is not None else None,
        "base_amount": str(res.base_amount) if res.base_amount is not None else None,
        "rate_sheet_id": res.rate_sheet_id, "rate_entry_id": res.rate_entry_id,
        "zone_id": res.zone_id, "rate_group_id": res.rate_group_id,
    }


class PayrollService:
    """드라이버 정산 — RateResolver 로 leg base 해석 → 라인 snapshot → 확정."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = PayrollRepository(db, team_id)

    # ── Preview (저장 안 함) ────────────────────────────────────
    async def preview(self, req: PayrollBuildRequest) -> PayrollPreviewSchema:
        legs = await self.repo.collect_settleable_legs(req.driver_id, req.period_start, req.period_end)
        lines: list[PayrollPreviewLine] = []
        base_total = Decimal("0")
        unresolved = 0
        for leg in legs:
            res = await resolve_leg_rate(self.db, self.team_id, leg)
            base = res.base_amount if (res.found and res.base_amount is not None) else Decimal("0")
            src = PayrollLineSource.RESOLVED if res.found else PayrollLineSource.UNRESOLVED
            if not res.found:
                unresolved += 1
            base_total += base
            wd = (leg.completed_at or leg.assigned_at)
            lines.append(PayrollPreviewLine(
                leg_id=leg.id, work_date=wd.date() if wd else None,
                base_amount=base, source=src, message=res.message,
            ))
        return PayrollPreviewSchema(
            driver_id=req.driver_id, period_start=req.period_start, period_end=req.period_end,
            line_count=len(lines), unresolved_count=unresolved, base_total=base_total, lines=lines,
        )

    # ── Build (저장) ────────────────────────────────────────────
    async def build(self, req: PayrollBuildRequest, actor_user_id: int | None = None) -> PayrollDetailSchema:
        legs = await self.repo.collect_settleable_legs(req.driver_id, req.period_start, req.period_end)
        header = await self.repo.create_settlement({
            "driver_id": req.driver_id, "period_start": req.period_start, "period_end": req.period_end,
            "status": PayrollStatus.DRAFT,
        }, actor_user_id=actor_user_id)
        for leg in legs:
            res = await resolve_leg_rate(self.db, self.team_id, leg)
            base = res.base_amount if (res.found and res.base_amount is not None) else Decimal("0")
            src = PayrollLineSource.RESOLVED if res.found else PayrollLineSource.UNRESOLVED
            wd = (leg.completed_at or leg.assigned_at)
            await self.repo.add_line(header.id, {
                "leg_id": leg.id, "work_date": wd.date() if wd else None,
                "base_amount": base, "source": src, "rate_snapshot": _snapshot(res),
                "message": res.message,
            }, actor_user_id=actor_user_id)
        await self.repo.update_totals(header)
        return await self._to_detail(header.id)

    # ── Bi-weekly 일괄 생성 + 집계 (재설계 2c) ──────────────────
    async def build_period(self, req, actor_user_id: int | None = None) -> "PayrollBuildPeriodResultSchema":
        """기간 내 대상 leg 있는 드라이버 전체(또는 지정)에 대해 정산 일괄 생성."""
        from payroll.schemas.request import PayrollBuildRequest
        from payroll.schemas.response import PayrollBuildPeriodResultSchema

        if req.driver_ids:
            driver_ids = list(dict.fromkeys(req.driver_ids))  # 중복 제거, 순서 유지
        else:
            driver_ids = await self.repo.list_settleable_driver_ids(req.period_start, req.period_end)

        built: list[PayrollSummarySchema] = []
        skipped: list[int] = []
        for did in driver_ids:
            legs = await self.repo.collect_settleable_legs(did, req.period_start, req.period_end)
            if not legs:
                skipped.append(did)
                continue
            detail = await self.build(
                PayrollBuildRequest(driver_id=did, period_start=req.period_start, period_end=req.period_end),
                actor_user_id=actor_user_id,
            )
            built.append(PayrollSummarySchema.model_validate(detail.model_dump()))
        return PayrollBuildPeriodResultSchema(
            period_start=req.period_start, period_end=req.period_end,
            built_count=len(built), skipped_drivers=skipped, settlements=built,
        )

    async def period_summary(self, start: date, end: date) -> "PayrollPeriodSummarySchema":
        from payroll.schemas.response import PayrollPeriodSummarySchema
        agg = await self.repo.aggregate_period(start, end)
        return PayrollPeriodSummarySchema(period_start=start, period_end=end, **agg)

    # ── Read ────────────────────────────────────────────────────
    async def get(self, settlement_id: int) -> PayrollDetailSchema:
        if not await self.repo.get(settlement_id):
            raise NotFoundException(_LABEL)
        return await self._to_detail(settlement_id)

    async def _to_detail(self, settlement_id: int) -> PayrollDetailSchema:
        header = await self.repo.get_with_lines(settlement_id)
        if not header:
            raise NotFoundException(_LABEL)
        charges = await self.repo.list_charges(settlement_id)
        detail = PayrollDetailSchema(**PayrollSummarySchema.model_validate(header).model_dump())
        detail.lines = [PayrollLineResponseSchema.model_validate(l) for l in header.lines]
        detail.charges = [PayrollChargeResponseSchema.model_validate(c) for c in charges]
        return detail

    async def list_paginated(self, request: PaginatePayrollRequest) -> CursorPaginationResult[PayrollSummarySchema]:
        result = await self.repo.get_paginated(request)
        result.data = [PayrollSummarySchema.model_validate(r) for r in result.data]
        return result

    async def sync_delta(self, since_str: str):
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)
        result.items = [PayrollSummarySchema.model_validate(r) for r in result.items]
        return result

    # ── 상태 전이 ───────────────────────────────────────────────
    async def confirm(self, settlement_id: int, actor_user_id: int | None = None) -> PayrollDetailSchema:
        header = await self.repo.get_with_lines(settlement_id)
        if not header:
            raise NotFoundException(_LABEL)
        if header.status != PayrollStatus.DRAFT:
            raise ConflictException(f"DRAFT 상태만 확정 가능 (현재 {header.status.value}).")
        unresolved = [l for l in header.lines if l.source == PayrollLineSource.UNRESOLVED]
        if unresolved:
            raise ConflictException(
                f"미등록 요율 라인 {len(unresolved)}건 — 요율 등록/그룹 배정 후 확정하세요.",
            )
        await self.repo.set_status(header, PayrollStatus.CONFIRMED, actor_user_id=actor_user_id)
        return await self._to_detail(settlement_id)

    async def mark_paid(self, settlement_id: int, actor_user_id: int | None = None) -> PayrollDetailSchema:
        header = await self.repo.get(settlement_id)
        if not header:
            raise NotFoundException(_LABEL)
        if header.status != PayrollStatus.CONFIRMED:
            raise ConflictException("CONFIRMED 상태만 PAID 가능.")
        await self.repo.set_status(header, PayrollStatus.PAID, actor_user_id=actor_user_id)
        return await self._to_detail(settlement_id)

    async def void(self, settlement_id: int, actor_user_id: int | None = None) -> PayrollDetailSchema:
        header = await self.repo.get(settlement_id)
        if not header:
            raise NotFoundException(_LABEL)
        await self.repo.set_status(header, PayrollStatus.VOID, actor_user_id=actor_user_id)
        return await self._to_detail(settlement_id)

    # ── Accessorial ─────────────────────────────────────────────
    async def add_charge(self, settlement_id: int, body: PayrollChargeAddRequest, actor_user_id: int | None = None) -> PayrollDetailSchema:
        header = await self.repo.get(settlement_id)
        if not header:
            raise NotFoundException(_LABEL)
        if header.status not in (PayrollStatus.DRAFT,):
            raise ConflictException("DRAFT 상태에서만 charge 추가 가능.")
        await self.repo.add_charge(settlement_id, body.model_dump(), actor_user_id=actor_user_id)
        await self.repo.update_totals(header)
        return await self._to_detail(settlement_id)

    async def delete(self, settlement_id: int, actor_user_id: int | None = None) -> PayrollDeleteResponseSchema:
        if not await self.repo.get(settlement_id):
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_by_id(settlement_id, actor_user_id=actor_user_id)
        return PayrollDeleteResponseSchema(id=settlement_id, deleted=True, soft_deleted=True)
