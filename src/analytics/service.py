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

from container.const.status import ContainerEventKind
from container.model import ContainerEventModel
from driver.model import DriverModel
from leg.const.status import LegStatus
from leg.model import LegModel
from user.model import UserModel
from payroll.model import PayrollLineModel, PayrollSettlementModel
from payroll.const.status import PayrollStatus
from invoice.model import InvoiceModel, InvoiceLineModel
from invoice.const.status import InvoiceStatus
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
        """일자별 매출/지급/마진 (재설계: 지급=payroll base@leg완료일, 매출=invoice 청구@발행일)."""
        days = max(1, min(days, 90))
        since = datetime.now(tz=timezone.utc) - timedelta(days=days)
        since_date = since.date()

        # 지급(payout) — payroll base, leg.completed_at 버킷
        pay_bucket = func.date(LegModel.completed_at).label("bucket")
        pay_q = (
            select(pay_bucket, func.coalesce(func.sum(PayrollLineModel.base_amount), 0).label("payouts"))
            .select_from(PayrollLineModel)
            .join(LegModel, LegModel.id == PayrollLineModel.leg_id)
            .join(PayrollSettlementModel, and_(
                PayrollSettlementModel.team_id == PayrollLineModel.team_id,
                PayrollSettlementModel.id == PayrollLineModel.settlement_id,
            ))
            .where(
                PayrollLineModel.team_id == self.team_id,
                PayrollSettlementModel.status != PayrollStatus.VOID,
                LegModel.completed_at.is_not(None),
                LegModel.completed_at >= since,
            )
            .group_by(pay_bucket)
        )

        # 매출(revenue) — invoice 청구액, issue_date(없으면 created_at) 버킷, ISSUED/PAID 만 인식
        rev_bucket = func.coalesce(InvoiceModel.issue_date, func.date(InvoiceModel.created_at)).label("bucket")
        rev_q = (
            select(rev_bucket, func.coalesce(func.sum(InvoiceLineModel.amount), 0).label("revenue"))
            .select_from(InvoiceLineModel)
            .join(InvoiceModel, and_(
                InvoiceModel.team_id == InvoiceLineModel.team_id,
                InvoiceModel.id == InvoiceLineModel.invoice_id,
            ))
            .where(
                InvoiceLineModel.team_id == self.team_id,
                InvoiceModel.is_active.is_(True),
                InvoiceModel.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.PAID]),
                func.coalesce(InvoiceModel.issue_date, func.date(InvoiceModel.created_at)) >= since_date,
            )
            .group_by(rev_bucket)
        )

        buckets: dict[date, dict] = {}
        for b, payouts in (await self.db.execute(pay_q)).all():
            if b is None:
                continue
            buckets.setdefault(b, {"revenue": Decimal("0"), "payouts": Decimal("0")})["payouts"] = Decimal(payouts or 0)
        for b, revenue in (await self.db.execute(rev_q)).all():
            if b is None:
                continue
            buckets.setdefault(b, {"revenue": Decimal("0"), "payouts": Decimal("0")})["revenue"] = Decimal(revenue or 0)

        points: List[MarginTrendPoint] = []
        total_rev = Decimal("0")
        total_pay = Decimal("0")
        for b in sorted(buckets):
            rev = buckets[b]["revenue"]
            pay = buckets[b]["payouts"]
            total_rev += rev
            total_pay += pay
            points.append(MarginTrendPoint(bucket=b, revenue=rev, payouts=pay, margin=rev - pay))
        return MarginTrendResponse(
            days=days, points=points,
            total_revenue=total_rev, total_payouts=total_pay,
            total_margin=total_rev - total_pay,
        )

    async def expiring_compliance(self, days: int = 30):
        """truck/chassis/driver 의 만료 임박/만료된 장비·DQ 항목 (Phase 6)."""
        from datetime import date as _date
        from truck.model import TruckModel
        from chassis.model import ChassisModel
        from driver.model import DriverModel
        from user.model import UserModel
        from analytics.schemas.response import ExpiringItem, ExpiringComplianceResponse

        days = max(1, min(days, 365))
        today = datetime.now(tz=timezone.utc).date()
        cutoff = today + timedelta(days=days)
        items: list[ExpiringItem] = []

        def _add(entity_type, eid, label, field, exp):
            if exp is None or exp > cutoff:
                return
            items.append(ExpiringItem(
                entity_type=entity_type, entity_id=eid, label=label or str(eid),
                field=field, expires_at=exp, days_left=(exp - today).days,
            ))

        trucks = (await self.db.execute(select(TruckModel).where(
            TruckModel.team_id == self.team_id, TruckModel.is_active.is_(True),
        ))).scalars().all()
        for t in trucks:
            _add("truck", t.id, t.plate_no, "registration", t.registration_expires_at)
            _add("truck", t.id, t.plate_no, "insurance", t.insurance_expires_at)
            _add("truck", t.id, t.plate_no, "inspection", t.inspection_expires_at)

        chs = (await self.db.execute(select(ChassisModel).where(
            ChassisModel.team_id == self.team_id, ChassisModel.is_active.is_(True),
        ))).scalars().all()
        for c in chs:
            _add("chassis", c.id, c.chassis_number, "registration", c.registration_expires_at)
            _add("chassis", c.id, c.chassis_number, "inspection", c.inspection_expires_at)

        drv = (await self.db.execute(
            select(DriverModel, func.coalesce(UserModel.name, UserModel.email))
            .outerjoin(UserModel, UserModel.id == DriverModel.user_id)
            .where(DriverModel.team_id == self.team_id, DriverModel.is_active.is_(True))
        )).all()
        for d, name in drv:
            _add("driver", d.id, name, "license", d.license_expires_at)
            _add("driver", d.id, name, "medical", d.medical_cert_expires_at)
            _add("driver", d.id, name, "twic", d.twic_expires_at)

        items.sort(key=lambda x: x.days_left)
        return ExpiringComplianceResponse(
            days=days,
            expired_count=sum(1 for i in items if i.days_left < 0),
            soon_count=sum(1 for i in items if i.days_left >= 0),
            items=items,
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
