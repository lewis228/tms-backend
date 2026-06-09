# src/payroll/repository.py
from __future__ import annotations
from typing import Optional, List
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_
from sqlalchemy.orm import selectinload

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from payroll.model import PayrollSettlementModel, PayrollLineModel, PayrollChargeModel
from payroll.const.status import PayrollStatus
from payroll.schemas.request import PaginatePayrollRequest
from leg.model import LegModel
from leg.const.status import LegStatus


class PayrollRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    # ── 정산 대상 leg 수집 ───────────────────────────────────────
    async def collect_settleable_legs(self, driver_id: int, start: date, end: date) -> List[LegModel]:
        """driver 의 기간 내 COMPLETED leg 중 아직 (비-VOID) 정산에 안 들어간 것."""
        team_id = self._require_team()
        settled = (
            select(PayrollLineModel.leg_id)
            .join(PayrollSettlementModel, and_(
                PayrollSettlementModel.team_id == PayrollLineModel.team_id,
                PayrollSettlementModel.id == PayrollLineModel.settlement_id,
            ))
            .where(
                PayrollLineModel.team_id == team_id,
                PayrollLineModel.leg_id.isnot(None),
                PayrollSettlementModel.status != PayrollStatus.VOID,
            )
        )
        q = (
            select(LegModel)
            .where(
                LegModel.team_id == team_id,
                LegModel.is_active.is_(True),
                LegModel.driver_id == driver_id,
                LegModel.status == LegStatus.COMPLETED,
                func.date(LegModel.completed_at) >= start,
                func.date(LegModel.completed_at) <= end,
                LegModel.id.notin_(settled),
            )
            .order_by(LegModel.completed_at.asc(), LegModel.id.asc())
        )
        return list((await self.db.execute(q)).scalars().all())

    async def list_settleable_driver_ids(self, start: date, end: date) -> List[int]:
        """기간 내 정산 대상 COMPLETED leg(비-VOID 정산 미포함)를 가진 driver_id 목록."""
        team_id = self._require_team()
        settled = (
            select(PayrollLineModel.leg_id)
            .join(PayrollSettlementModel, and_(
                PayrollSettlementModel.team_id == PayrollLineModel.team_id,
                PayrollSettlementModel.id == PayrollLineModel.settlement_id,
            ))
            .where(
                PayrollLineModel.team_id == team_id,
                PayrollLineModel.leg_id.isnot(None),
                PayrollSettlementModel.status != PayrollStatus.VOID,
            )
        )
        q = (
            select(LegModel.driver_id)
            .where(
                LegModel.team_id == team_id,
                LegModel.is_active.is_(True),
                LegModel.driver_id.isnot(None),
                LegModel.status == LegStatus.COMPLETED,
                func.date(LegModel.completed_at) >= start,
                func.date(LegModel.completed_at) <= end,
                LegModel.id.notin_(settled),
            )
            .group_by(LegModel.driver_id)
            .order_by(LegModel.driver_id.asc())
        )
        return [r for (r,) in (await self.db.execute(q)).all()]

    async def aggregate_period(self, start: date, end: date) -> dict:
        """기간과 겹치는 비-VOID 정산 헤더들의 합계(드라이버 수/건수/금액)."""
        team_id = self._require_team()
        q = (
            select(
                func.count(PayrollSettlementModel.id).label("count"),
                func.count(func.distinct(PayrollSettlementModel.driver_id)).label("driver_count"),
                func.coalesce(func.sum(PayrollSettlementModel.base_total), 0).label("base_total"),
                func.coalesce(func.sum(PayrollSettlementModel.accessorial_total), 0).label("accessorial_total"),
                func.coalesce(func.sum(PayrollSettlementModel.grand_total), 0).label("grand_total"),
            )
            .where(
                PayrollSettlementModel.team_id == team_id,
                PayrollSettlementModel.is_active.is_(True),
                PayrollSettlementModel.status != PayrollStatus.VOID,
                PayrollSettlementModel.period_start <= end,
                PayrollSettlementModel.period_end >= start,
            )
        )
        row = (await self.db.execute(q)).one()
        return {
            "count": int(row.count or 0),
            "driver_count": int(row.driver_count or 0),
            "base_total": row.base_total or 0,
            "accessorial_total": row.accessorial_total or 0,
            "grand_total": row.grand_total or 0,
        }

    # ── 헤더 ────────────────────────────────────────────────────
    async def create_settlement(self, payload: dict, actor_user_id: int | None = None) -> PayrollSettlementModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = PayrollSettlementModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, settlement_id: int) -> Optional[PayrollSettlementModel]:
        q = select(PayrollSettlementModel).where(
            PayrollSettlementModel.team_id == self._require_team(),
            PayrollSettlementModel.id == settlement_id,
            PayrollSettlementModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_with_lines(self, settlement_id: int) -> Optional[PayrollSettlementModel]:
        q = (
            select(PayrollSettlementModel)
            .where(
                PayrollSettlementModel.team_id == self._require_team(),
                PayrollSettlementModel.id == settlement_id,
                PayrollSettlementModel.is_active.is_(True),
            )
            .options(selectinload(PayrollSettlementModel.lines))
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_paginated(self, request: PaginatePayrollRequest):
        team_id = self._require_team()
        base = [PayrollSettlementModel.team_id == team_id]
        if not request.include_inactive:
            base.append(PayrollSettlementModel.is_active.is_(True))
        return await self._common_service.paginate(
            request=request, model=PayrollSettlementModel, session=self.db,
            base_query=select(PayrollSettlementModel).where(*base),
        )

    async def set_status(self, row: PayrollSettlementModel, status: PayrollStatus, actor_user_id: int | None = None) -> None:
        row.status = status
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()

    async def update_totals(self, row: PayrollSettlementModel) -> None:
        base = (await self.db.execute(select(func.coalesce(func.sum(PayrollLineModel.base_amount), 0)).where(
            PayrollLineModel.team_id == self._require_team(), PayrollLineModel.settlement_id == row.id,
        ))).scalar_one()
        acc = (await self.db.execute(select(func.coalesce(func.sum(PayrollChargeModel.amount), 0)).where(
            PayrollChargeModel.team_id == self._require_team(), PayrollChargeModel.settlement_id == row.id,
        ))).scalar_one()
        row.base_total = base
        row.accessorial_total = acc
        row.grand_total = base + acc
        await self.db.flush()

    async def soft_deactivate_by_id(self, settlement_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(update(PayrollSettlementModel).where(
            PayrollSettlementModel.team_id == self._require_team(),
            PayrollSettlementModel.id == settlement_id,
            PayrollSettlementModel.is_active.is_(True),
        ).values(**values))
        await self.db.flush()

    async def sync_delta(self, since):
        team_id = self._require_team()
        base_query = select(PayrollSettlementModel).where(PayrollSettlementModel.team_id == team_id)
        return await self._common_service.sync_delta(
            model=PayrollSettlementModel, session=self.db, since=since,
            team_id=team_id, base_query=base_query, use_soft_delete=True,
        )

    # ── 라인 / charge ───────────────────────────────────────────
    async def add_line(self, settlement_id: int, data: dict, actor_user_id: int | None = None) -> PayrollLineModel:
        row = PayrollLineModel(team_id=self._require_team(), settlement_id=settlement_id,
                               created_by_user_id=actor_user_id, **data)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def list_lines(self, settlement_id: int) -> List[PayrollLineModel]:
        q = select(PayrollLineModel).where(
            PayrollLineModel.team_id == self._require_team(),
            PayrollLineModel.settlement_id == settlement_id,
        ).order_by(PayrollLineModel.id.asc())
        return list((await self.db.execute(q)).scalars().all())

    async def add_charge(self, settlement_id: int, data: dict, actor_user_id: int | None = None) -> PayrollChargeModel:
        row = PayrollChargeModel(team_id=self._require_team(), settlement_id=settlement_id,
                                 created_by_user_id=actor_user_id, **data)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def list_charges(self, settlement_id: int) -> List[PayrollChargeModel]:
        q = select(PayrollChargeModel).where(
            PayrollChargeModel.team_id == self._require_team(),
            PayrollChargeModel.settlement_id == settlement_id,
        ).order_by(PayrollChargeModel.id.asc())
        return list((await self.db.execute(q)).scalars().all())
