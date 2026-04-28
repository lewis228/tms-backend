# src/analytics/service.py
"""H-9 Dashboard 집계 서비스.

설계 원칙:
- 모든 쿼리는 team_id 로 스코프
- 날짜 버킷팅: leg.completed_at / settlement.created_at / chassis_event.occurred_at
- 모든 수치는 Decimal/int 로 반환 (Pydantic 직렬화)
"""
from __future__ import annotations
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from typing import List

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from charge_code.const.status import PartyKind
from container.const.status import ContainerEventKind
from container.model import ContainerEventModel
from driver.model import DriverModel
from leg.const.status import LegStatus
from leg.model import LegModel
from user.model import UserModel
from leg_charge.model import LegChargeModel
from street_turn.const.status import StreetTurnStatus
from street_turn.model import StreetTurnModel

from analytics.schemas.response import (
    MarginTrendPoint, MarginTrendResponse,
    DriverUtilizationRow, DriverUtilizationResponse,
    ContainerTurnoverPoint, ContainerTurnoverResponse,
    StreetTurnSavingsResponse,
)

# Street turn 1 건당 예상 절감액 (per diem 35 * 3일 + handling 50)
STREET_TURN_SAVING_PER = Decimal("155.00")


class AnalyticsService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id

    async def margin_trend(self, days: int = 30) -> MarginTrendResponse:
        """leg_charge 기반 일자별 매출/지급/마진."""
        days = max(1, min(days, 90))
        since = datetime.now(tz=timezone.utc) - timedelta(days=days)

        # leg.completed_at 으로 매출/지급을 그루핑
        bucket = func.date(LegModel.completed_at).label("bucket")
        revenue = func.coalesce(
            func.sum(case(
                (LegChargeModel.payer_kind == PartyKind.CUSTOMER, LegChargeModel.amount),
                else_=0,
            )),
            0,
        ).label("revenue")
        payouts = func.coalesce(
            func.sum(case(
                (LegChargeModel.payee_kind.in_([
                    PartyKind.DRIVER, PartyKind.CARRIER, PartyKind.POOL,
                ]), LegChargeModel.amount),
                else_=0,
            )),
            0,
        ).label("payouts")

        q = (
            select(bucket, revenue, payouts)
            .select_from(LegChargeModel)
            .join(LegModel, LegModel.id == LegChargeModel.leg_id)
            .where(
                LegChargeModel.team_id == self.team_id,
                LegChargeModel.is_active.is_(True),
                LegModel.completed_at.is_not(None),
                LegModel.completed_at >= since,
            )
            .group_by(bucket)
            .order_by(bucket.asc())
        )
        rows = (await self.db.execute(q)).all()

        points: List[MarginTrendPoint] = []
        total_rev = Decimal("0")
        total_pay = Decimal("0")
        for r in rows:
            rev = Decimal(r.revenue or 0)
            pay = Decimal(r.payouts or 0)
            total_rev += rev
            total_pay += pay
            points.append(MarginTrendPoint(
                bucket=r.bucket,
                revenue=rev,
                payouts=pay,
                margin=rev - pay,
            ))
        return MarginTrendResponse(
            days=days,
            points=points,
            total_revenue=total_rev,
            total_payouts=total_pay,
            total_margin=total_rev - total_pay,
        )

    async def driver_utilization(self, days: int = 7) -> DriverUtilizationResponse:
        """기사별 leg 가동률 (completed / total) 최근 N 일."""
        days = max(1, min(days, 30))
        since = datetime.now(tz=timezone.utc) - timedelta(days=days)

        completed_n = func.sum(case(
            (LegModel.status == LegStatus.COMPLETED, 1), else_=0,
        )).label("completed_legs")
        in_transit_n = func.sum(case(
            (LegModel.status == LegStatus.IN_TRANSIT, 1), else_=0,
        )).label("in_transit_legs")
        total_n = func.count(LegModel.id).label("total_legs")

        q = (
            select(
                DriverModel.id.label("driver_id"),
                func.coalesce(UserModel.name, UserModel.email, "Driver").label("driver_name"),
                completed_n,
                in_transit_n,
                total_n,
            )
            .select_from(DriverModel)
            .join(UserModel, UserModel.id == DriverModel.user_id)
            .join(LegModel, and_(
                LegModel.driver_id == DriverModel.id,
                LegModel.team_id == self.team_id,
                LegModel.is_active.is_(True),
                LegModel.created_at >= since,
            ))
            .where(
                DriverModel.team_id == self.team_id,
                DriverModel.is_active.is_(True),
            )
            .group_by(DriverModel.id, UserModel.name, UserModel.email)
            .order_by(total_n.desc())
        )
        rows = (await self.db.execute(q)).all()
        out: List[DriverUtilizationRow] = []
        for r in rows:
            total = int(r.total_legs or 0)
            completed = int(r.completed_legs or 0)
            in_transit = int(r.in_transit_legs or 0)
            pct = (completed / total * 100.0) if total > 0 else 0.0
            out.append(DriverUtilizationRow(
                driver_id=r.driver_id,
                driver_name=r.driver_name,
                total_legs=total,
                completed_legs=completed,
                in_transit_legs=in_transit,
                utilization_pct=round(pct, 1),
            ))
        return DriverUtilizationResponse(days=days, rows=out)

    async def container_turnover(self, days: int = 30) -> ContainerTurnoverResponse:
        """컨테이너 lifecycle 이벤트 일자별 집계 + 평균 보유일수."""
        days = max(1, min(days, 90))
        since = datetime.now(tz=timezone.utc) - timedelta(days=days)

        bucket = func.date(ContainerEventModel.occurred_at).label("bucket")
        picked = func.sum(case(
            (ContainerEventModel.event_kind == ContainerEventKind.GATE_OUT, 1), else_=0,
        )).label("picked")
        returned = func.sum(case(
            (ContainerEventModel.event_kind == ContainerEventKind.RETURNED, 1), else_=0,
        )).label("returned")
        st = func.sum(case(
            (ContainerEventModel.event_kind == ContainerEventKind.STREET_TURNED, 1), else_=0,
        )).label("street_turned")

        q = (
            select(bucket, picked, returned, st)
            .where(
                ContainerEventModel.team_id == self.team_id,
                ContainerEventModel.is_active.is_(True),
                ContainerEventModel.occurred_at >= since,
            )
            .group_by(bucket)
            .order_by(bucket.asc())
        )
        rows = (await self.db.execute(q)).all()
        points: List[ContainerTurnoverPoint] = [
            ContainerTurnoverPoint(
                bucket=r.bucket,
                picked=int(r.picked or 0),
                returned=int(r.returned or 0),
                street_turned=int(r.street_turned or 0),
            ) for r in rows
        ]

        # 평균 dwell = container_id 별 GATE_OUT~RETURNED 시간차
        dwell_q = (
            select(
                ContainerEventModel.container_id,
                func.min(case(
                    (ContainerEventModel.event_kind == ContainerEventKind.GATE_OUT,
                     ContainerEventModel.occurred_at)
                )).label("picked_at"),
                func.max(case(
                    (ContainerEventModel.event_kind == ContainerEventKind.RETURNED,
                     ContainerEventModel.occurred_at)
                )).label("returned_at"),
            )
            .where(
                ContainerEventModel.team_id == self.team_id,
                ContainerEventModel.is_active.is_(True),
                ContainerEventModel.occurred_at >= since,
                ContainerEventModel.container_id.is_not(None),
            )
            .group_by(ContainerEventModel.container_id)
        )
        drows = (await self.db.execute(dwell_q)).all()
        diffs: List[float] = []
        for r in drows:
            if r.picked_at and r.returned_at and r.returned_at > r.picked_at:
                diffs.append((r.returned_at - r.picked_at).total_seconds() / 86400.0)
        avg_dwell = round(sum(diffs) / len(diffs), 2) if diffs else 0.0

        return ContainerTurnoverResponse(
            days=days, points=points, avg_dwell_days=avg_dwell,
        )

    async def street_turn_savings(self, days: int = 30) -> StreetTurnSavingsResponse:
        """Street turn 상태별 카운트 + 누적 절감액 (approved 만)."""
        days = max(1, min(days, 365))
        since = datetime.now(tz=timezone.utc) - timedelta(days=days)

        q = (
            select(
                StreetTurnModel.status,
                func.count(StreetTurnModel.id),
            )
            .where(
                StreetTurnModel.team_id == self.team_id,
                StreetTurnModel.is_active.is_(True),
                StreetTurnModel.requested_at >= since,
            )
            .group_by(StreetTurnModel.status)
        )
        rows = (await self.db.execute(q)).all()
        counts = {s: 0 for s in StreetTurnStatus}
        for status, c in rows:
            counts[status] = int(c)

        approved = counts.get(StreetTurnStatus.APPROVED, 0)
        savings = STREET_TURN_SAVING_PER * Decimal(approved)

        return StreetTurnSavingsResponse(
            days=days,
            approved_count=approved,
            requested_count=counts.get(StreetTurnStatus.REQUESTED, 0),
            rejected_count=counts.get(StreetTurnStatus.REJECTED, 0),
            savings_amount=savings,
            saving_per_turn=STREET_TURN_SAVING_PER,
        )
