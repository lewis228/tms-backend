# src/driver_mobile/service.py
"""Driver mobile 비즈니스 로직 — leg/file/user 재사용 + driver 매핑."""
from __future__ import annotations
from collections import namedtuple
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, AppException
from driver.model import DriverModel

# leg from_point/to_point(container_stop) 의 타입별 마스터에서 추출한 표시 정보
_PointInfo = namedtuple("_PointInfo", ["name", "address", "latitude", "longitude"])
from driver.const.status import DutyStatus
from leg.const.status import LegStatus
from leg.model import LegModel
from delivery_order.model import DeliveryOrderModel
from customer.model import CustomerModel
from location.model import LocationModel
from payroll.model import PayrollLineModel, PayrollSettlementModel
from payroll.const.status import PayrollStatus
from user.model import UserModel
from truck.model import TruckModel


class DriverMobileService:
    def __init__(self, db: AsyncSession, team_id: int) -> None:
        self.db = db
        self.team_id = team_id

    async def _earnings_by_leg(self, leg_ids: list[int]) -> dict[int, dict]:
        """leg_id → {amount, settled, pending} — payroll_line 기반.

        leg 의 payroll base(비-VOID 정산 라인) + 부모 정산 status 로 수익/상태 표시.
        """
        if not leg_ids:
            return {}
        stmt = (
            select(
                PayrollLineModel.leg_id,
                PayrollLineModel.base_amount,
                PayrollSettlementModel.status,
            )
            .join(PayrollSettlementModel, and_(
                PayrollSettlementModel.team_id == PayrollLineModel.team_id,
                PayrollSettlementModel.id == PayrollLineModel.settlement_id,
            ))
            .where(
                PayrollLineModel.team_id == self.team_id,
                PayrollLineModel.leg_id.in_(leg_ids),
                PayrollSettlementModel.status != PayrollStatus.VOID,
                PayrollSettlementModel.is_active.is_(True),
            )
        )
        out: dict[int, dict] = {}
        for leg_id, base, status in (await self.db.execute(stmt)).all():
            cur = out.setdefault(leg_id, {"amount": Decimal(0), "settled": False, "pending": False})
            cur["amount"] += base or Decimal(0)
            if status == PayrollStatus.PAID:
                cur["settled"] = True
            else:
                cur["pending"] = True
        return out

    async def resolve_driver_id(self, user_id: int) -> int:
        """User → 그 team 의 Driver row.id 매핑."""
        stmt = select(DriverModel.id).where(
            DriverModel.team_id == self.team_id,
            DriverModel.user_id == user_id,
            DriverModel.is_active.is_(True),
        )
        driver_id = (await self.db.execute(stmt)).scalar_one_or_none()
        if driver_id is None:
            raise NotFoundException("Driver profile not found for current user")
        return driver_id

    async def today_legs(self, user_id: int) -> list[LegModel]:
        """오늘 (UTC 기준 0시~24시) 본 driver 에 할당된 Leg 목록."""
        driver_id = await self.resolve_driver_id(user_id)
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        stmt = (
            select(LegModel)
            .where(
                LegModel.team_id == self.team_id,
                LegModel.driver_id == driver_id,
                LegModel.is_active.is_(True),
                # pickup_date 또는 delivery_date 가 오늘 범위 또는 진행 중
                # 단순화: 진행 중 (PENDING/IN_TRANSIT) + 오늘 picked-up 예정/시작
            )
            .order_by(LegModel.pickup_date.asc(), LegModel.id.asc())
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        # 오늘 범위 + 진행 중 필터 (Python 측에서)
        out: list[LegModel] = []
        for leg in rows:
            if leg.status not in (LegStatus.PENDING, LegStatus.IN_TRANSIT):
                continue
            anchor = leg.pickup_date or leg.delivery_date
            if anchor and (anchor < start or anchor >= end):
                # 오늘 범위 밖이지만 IN_TRANSIT 면 포함
                if leg.status != LegStatus.IN_TRANSIT:
                    continue
            out.append(leg)
        return out

    async def checkpoint_leg(
        self,
        leg_id: int,
        target,                  # LegStatus
        *,
        user_id: int,
        failure_reason: str | None = None,
    ) -> LegModel:
        """leg.service.transition 위임 + 본인 leg 검증."""
        from leg.service import LegService

        driver_id = await self.resolve_driver_id(user_id)
        # 본인 leg 인지 검증
        stmt = select(LegModel).where(
            LegModel.team_id == self.team_id,
            LegModel.id == leg_id,
            LegModel.is_active.is_(True),
        )
        leg = (await self.db.execute(stmt)).scalar_one_or_none()
        if not leg:
            raise NotFoundException("Leg")
        if leg.driver_id != driver_id:
            raise AppException(
                code="ERR_FORBIDDEN_LEG",
                message="Leg not assigned to current driver",
                status_code=403,
            )

        svc = LegService(self.db, self.team_id)
        result = await svc.transition(
            leg_id, target,
            failure_reason=failure_reason,
            actor_user_id=user_id,
        )
        return result

    # ══════════════════════════════════════════════════════════════
    # 신규 BFF 메서드 (데모용)
    # ══════════════════════════════════════════════════════════════

    async def get_me(self, user_id: int) -> dict:
        """본인 driver 정보 + user.name + 차량."""
        stmt = (
            select(DriverModel, UserModel, TruckModel)
            .join(UserModel, DriverModel.user_id == UserModel.id)
            .outerjoin(TruckModel, and_(
                TruckModel.team_id == DriverModel.team_id,
                TruckModel.id == DriverModel.default_truck_id,
            ))
            .where(
                DriverModel.team_id == self.team_id,
                DriverModel.user_id == user_id,
                DriverModel.is_active.is_(True),
            )
        )
        row = (await self.db.execute(stmt)).first()
        if not row:
            raise NotFoundException("Driver profile not found for current user")
        driver, user, truck = row
        return {
            "id": driver.id,
            "user_id": driver.user_id,
            "name": user.name or "기사",
            "phone": user.phone,
            "license_number": driver.license_number,
            "license_expires_at": driver.license_expires_at,
            "employment_kind": driver.employment_kind.value if driver.employment_kind else None,
            "duty_status": driver.duty_status.value,
            "duty_changed_at": driver.duty_changed_at,
            "truck_id": truck.id if truck else None,
            "truck_plate": truck.plate_no if truck else None,
            "truck_model": (
                f"{truck.make or ''} {truck.model or ''}".strip()
                if truck else None
            ),
        }

    async def toggle_duty(self, user_id: int, target: str) -> dict:
        """근무 상태 토글."""
        try:
            target_enum = DutyStatus(target)
        except ValueError:
            raise AppException(code="INVALID_DUTY_STATUS", message=f"Unknown: {target}", status_code=400)

        driver_id = await self.resolve_driver_id(user_id)
        stmt = select(DriverModel).where(
            DriverModel.team_id == self.team_id,
            DriverModel.id == driver_id,
        )
        driver = (await self.db.execute(stmt)).scalar_one_or_none()
        if not driver:
            raise NotFoundException("Driver")

        now = datetime.now(timezone.utc)
        driver.duty_status = target_enum
        driver.duty_changed_at = now
        driver.updated_by_user_id = user_id
        await self.db.flush()
        await self.db.refresh(driver)
        return {
            "duty_status": driver.duty_status.value,
            "duty_changed_at": driver.duty_changed_at,
        }

    async def today_summary(self, user_id: int) -> dict:
        """오늘 요약 — 완료 수 + 예상 수익 + 거리 + on_duty 분."""
        driver_id = await self.resolve_driver_id(user_id)
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        # 완료된 leg
        stmt = select(LegModel).where(
            LegModel.team_id == self.team_id,
            LegModel.driver_id == driver_id,
            LegModel.is_active.is_(True),
            LegModel.completed_at >= start,
            LegModel.completed_at < end,
        )
        completed_legs = list((await self.db.execute(stmt)).scalars().all())

        completed_count = len(completed_legs)

        # 예상 수익 — 해당 leg 의 payroll base 합
        leg_ids = [l.id for l in completed_legs]
        earnings = await self._earnings_by_leg(leg_ids)
        revenue = sum((e["amount"] for e in earnings.values()), Decimal(0))

        # 거리 — 데모용 단순화: 완료된 leg 1건당 35km 가정 (실제 거리 연동은 추후)
        distance_km = Decimal(completed_count * 35)

        # on_duty 누적 — duty_changed_at 기반 단순 계산 (현재 ON_DUTY 면 now - changed_at)
        # 정확한 구현은 별도 duty_log 테이블 필요. 데모는 단순.
        on_duty_minutes = 0
        # 단순 추정: 완료된 운행 1건당 90분
        on_duty_minutes = completed_count * 90

        return {
            "completed_count": completed_count,
            "expected_revenue": revenue,
            "distance_km": distance_km,
            "on_duty_minutes": on_duty_minutes,
        }

    async def list_active_legs(self, user_id: int) -> list[LegModel]:
        """진행 중 leg (status=IN_TRANSIT, accepted_at != NULL) — 홈 진행 카드."""
        driver_id = await self.resolve_driver_id(user_id)
        stmt = (
            select(LegModel)
            .where(
                LegModel.team_id == self.team_id,
                LegModel.driver_id == driver_id,
                LegModel.is_active.is_(True),
                LegModel.status == LegStatus.IN_TRANSIT,
                LegModel.accepted_at.isnot(None),
            )
            .order_by(LegModel.started_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def _resolve_point(self, point_id: int | None) -> "_PointInfo | None":
        """leg.from_point_id/to_point_id(container_stop) → 타입별 마스터 표시정보."""
        if not point_id:
            return None
        from container_stop.model import ContainerStopModel
        from terminal.model import TerminalModel
        p = (await self.db.execute(
            select(ContainerStopModel).where(
                ContainerStopModel.team_id == self.team_id,
                ContainerStopModel.id == point_id,
            )
        )).scalar_one_or_none()
        if p is None:
            return None
        if p.terminal_id:
            t = (await self.db.execute(
                select(TerminalModel).where(TerminalModel.id == p.terminal_id)
            )).scalar_one_or_none()
            if t:
                return _PointInfo(t.name, t.address, t.latitude, t.longitude)
        elif p.location_id:
            loc = (await self.db.execute(
                select(LocationModel).where(LocationModel.id == p.location_id)
            )).scalar_one_or_none()
            if loc:
                return _PointInfo(loc.name, loc.address, loc.latitude, loc.longitude)
        elif p.customer_id:
            c = (await self.db.execute(
                select(CustomerModel).where(CustomerModel.id == p.customer_id)
            )).scalar_one_or_none()
            if c:
                return _PointInfo(c.name, getattr(c, "billing_address", None), None, None)
        return None

    async def list_pending_offers(self, user_id: int) -> list[dict]:
        """미수락 배차 — offered_at != NULL AND accepted_at IS NULL AND rejected_at IS NULL."""
        driver_id = await self.resolve_driver_id(user_id)
        stmt = (
            select(LegModel, DeliveryOrderModel, CustomerModel)
            .join(DeliveryOrderModel, and_(
                DeliveryOrderModel.team_id == LegModel.team_id,
                DeliveryOrderModel.id == LegModel.delivery_order_id,
            ))
            .outerjoin(CustomerModel, and_(
                CustomerModel.team_id == DeliveryOrderModel.team_id,
                CustomerModel.id == DeliveryOrderModel.customer_id,
            ))
            .where(
                LegModel.team_id == self.team_id,
                LegModel.driver_id == driver_id,
                LegModel.is_active.is_(True),
                LegModel.offered_at.isnot(None),
                LegModel.accepted_at.is_(None),
                LegModel.rejected_at.is_(None),
            )
            .order_by(LegModel.offered_at.desc())
        )
        rows = (await self.db.execute(stmt)).all()
        # pickup/delivery = leg 의 from_point/to_point(타입별 마스터) 해석
        offers: list[dict] = []
        for row in rows:
            leg, do, customer = row
            pickup_loc = await self._resolve_point(leg.from_point_id)
            delivery_loc = await self._resolve_point(leg.to_point_id)
            offers.append({
                "leg_id": leg.id,
                "delivery_order_id": leg.delivery_order_id,
                "bl_number": do.bl_number,
                "customer_name": customer.name if customer else None,
                "pickup_location_name": pickup_loc.name if pickup_loc else None,
                "pickup_address": getattr(pickup_loc, "address", None) if pickup_loc else None,
                "delivery_location_name": delivery_loc.name if delivery_loc else None,
                "delivery_address": getattr(delivery_loc, "address", None) if delivery_loc else None,
                # 데모용 단순화: 거리 / 예상시간 / 운임 임의 산출
                "distance_km": Decimal("42.5"),
                "expected_minutes": 75,
                "expected_revenue": Decimal("180000"),
                "pickup_date": leg.pickup_date,
                "offered_at": leg.offered_at,
            })
        return offers

    async def accept_offer(self, leg_id: int, *, user_id: int) -> LegModel:
        """배차 수락 — accepted_at 기록."""
        leg = await self._get_owned_leg(leg_id, user_id)
        if leg.accepted_at is not None:
            raise AppException(code="ALREADY_ACCEPTED", message="이미 수락된 배차입니다.", status_code=409)
        if leg.rejected_at is not None:
            raise AppException(code="ALREADY_REJECTED", message="이미 거절한 배차입니다.", status_code=409)
        leg.accepted_at = datetime.now(timezone.utc)
        leg.updated_by_user_id = user_id
        await self.db.flush()
        await self.db.refresh(leg)
        return leg

    async def reject_offer(self, leg_id: int, *, user_id: int, reason: str) -> LegModel:
        """배차 거절 — rejected_at + reason 기록 + driver_id NULL 처리 (다른 driver 재배정 가능)."""
        leg = await self._get_owned_leg(leg_id, user_id)
        if leg.accepted_at is not None:
            raise AppException(code="ALREADY_ACCEPTED", message="이미 수락한 배차는 거절할 수 없습니다.", status_code=409)
        leg.rejected_at = datetime.now(timezone.utc)
        leg.rejection_reason = reason
        leg.driver_id = None        # 디스패처가 다른 driver 에 재배정할 수 있도록
        leg.updated_by_user_id = user_id
        await self.db.flush()
        await self.db.refresh(leg)
        return leg

    async def list_history(self, user_id: int, *, before_id: int | None = None, limit: int = 20) -> dict:
        """운행 이력 — 완료된 leg 페이지네이션 (단순 cursor: leg.id DESC)."""
        driver_id = await self.resolve_driver_id(user_id)
        stmt = (
            select(LegModel, DeliveryOrderModel, CustomerModel)
            .join(DeliveryOrderModel, and_(
                DeliveryOrderModel.team_id == LegModel.team_id,
                DeliveryOrderModel.id == LegModel.delivery_order_id,
            ))
            .outerjoin(CustomerModel, and_(
                CustomerModel.team_id == DeliveryOrderModel.team_id,
                CustomerModel.id == DeliveryOrderModel.customer_id,
            ))
            .where(
                LegModel.team_id == self.team_id,
                LegModel.driver_id == driver_id,
                LegModel.is_active.is_(True),
                LegModel.status == LegStatus.COMPLETED,
            )
            .order_by(LegModel.id.desc())
            .limit(limit + 1)
        )
        if before_id is not None:
            stmt = stmt.where(LegModel.id < before_id)

        rows = (await self.db.execute(stmt)).all()
        has_more = len(rows) > limit
        rows = rows[:limit]

        items = []
        leg_ids = [r[0].id for r in rows]
        # leg 별 수익 — payroll base
        earnings = await self._earnings_by_leg(leg_ids)

        for leg, do, customer in rows:
            e = earnings.get(leg.id)
            items.append({
                "leg_id": leg.id,
                "delivery_order_id": leg.delivery_order_id,
                "status": leg.status.value,
                "customer_name": customer.name if customer else None,
                "pickup_location_name": None,         # 필요 시 join 확장
                "delivery_location_name": None,
                "pickup_date": leg.pickup_date,
                "delivery_date": leg.delivery_date,
                "completed_at": leg.completed_at,
                "distance_km": Decimal("35"),       # 데모 단순화
                "revenue": e["amount"] if e else None,
            })

        next_cursor = items[-1]["leg_id"] if has_more and items else None
        return {"items": items, "has_more": has_more, "next_cursor": next_cursor}

    async def monthly_settlement_summary(
        self,
        user_id: int,
        *,
        year: int | None = None,
        month: int | None = None,
    ) -> dict:
        """정산 — 월간 통계 (총액/주간추이/상태별)."""
        driver_id = await self.resolve_driver_id(user_id)
        now = datetime.now(timezone.utc)
        y = year or now.year
        m = month or now.month

        month_start = datetime(y, m, 1, tzinfo=timezone.utc)
        if m == 12:
            month_end = datetime(y + 1, 1, 1, tzinfo=timezone.utc)
        else:
            month_end = datetime(y, m + 1, 1, tzinfo=timezone.utc)

        # 해당 driver 의 leg_id 들 (해당 월에 완료된)
        leg_ids_stmt = select(LegModel.id).where(
            LegModel.team_id == self.team_id,
            LegModel.driver_id == driver_id,
            LegModel.is_active.is_(True),
            LegModel.completed_at >= month_start,
            LegModel.completed_at < month_end,
        )
        leg_ids = [r[0] for r in (await self.db.execute(leg_ids_stmt)).all()]

        if not leg_ids:
            return {
                "year": y, "month": m,
                "total_amount": Decimal(0),
                "completed_count": 0, "pending_count": 0, "on_hold_count": 0,
                "weekly_trend": [],
            }

        # 정산 모음 — payroll base
        earnings = await self._earnings_by_leg(leg_ids)

        total_amount = sum((e["amount"] for e in earnings.values()), Decimal(0))

        # 상태별 카운트 (payroll 정산 status 기반)
        completed_count = sum(1 for e in earnings.values() if e["settled"])
        pending_count   = sum(1 for e in earnings.values() if e["pending"] and not e["settled"])
        on_hold_count   = 0  # payroll 엔 hold 개념 없음

        # 주간 추이 — leg.completed_at 기준 4~5 주 split
        weekly_buckets: dict[int, Decimal] = {}
        weekly_starts: dict[int, datetime] = {}
        leg_map: dict[int, LegModel] = {
            l.id: l for l in (await self.db.execute(
                select(LegModel).where(LegModel.id.in_(leg_ids))
            )).scalars().all()
        }
        for leg_id, e in earnings.items():
            leg = leg_map.get(leg_id)
            if not leg or not leg.completed_at:
                continue
            # 월 내 몇 번째 주인지 (1-based)
            week_no = (leg.completed_at.day - 1) // 7 + 1
            weekly_buckets.setdefault(week_no, Decimal(0))
            weekly_buckets[week_no] += e["amount"]
            weekly_starts.setdefault(week_no, datetime(y, m, (week_no - 1) * 7 + 1, tzinfo=timezone.utc))

        weekly_trend = [
            {
                "week_label": f"{m}월 {wn}주차",
                "week_start": weekly_starts[wn],
                "amount": amt,
            }
            for wn, amt in sorted(weekly_buckets.items())
        ]

        return {
            "year": y, "month": m,
            "total_amount": total_amount,
            "completed_count": completed_count,
            "pending_count": pending_count,
            "on_hold_count": on_hold_count,
            "weekly_trend": weekly_trend,
        }

    async def list_settlements(
        self,
        user_id: int,
        *,
        before_id: int | None = None,
        limit: int = 20,
        status_filter: str | None = None,
    ) -> dict:
        """정산 목록 — driver 의 COMPLETED leg 를 payroll 라인 수익과 함께 페이지네이션."""
        driver_id = await self.resolve_driver_id(user_id)

        # 본 driver 의 완료 leg (leg 단위로 정산 표시 — per-leg settlement 폐지, payroll_line 으로 대체)
        stmt = (
            select(LegModel, DeliveryOrderModel, CustomerModel)
            .join(DeliveryOrderModel, and_(
                DeliveryOrderModel.team_id == LegModel.team_id,
                DeliveryOrderModel.id == LegModel.delivery_order_id,
            ))
            .outerjoin(CustomerModel, and_(
                CustomerModel.team_id == DeliveryOrderModel.team_id,
                CustomerModel.id == DeliveryOrderModel.customer_id,
            ))
            .where(
                LegModel.team_id == self.team_id,
                LegModel.is_active.is_(True),
                LegModel.driver_id == driver_id,
                LegModel.status == LegStatus.COMPLETED,
            )
            .order_by(LegModel.id.desc())
            .limit(limit + 1)
        )
        if before_id is not None:
            stmt = stmt.where(LegModel.id < before_id)

        rows = (await self.db.execute(stmt)).all()
        has_more = len(rows) > limit
        rows = rows[:limit]

        earnings = await self._earnings_by_leg([leg.id for leg, _do, _c in rows])
        items = []
        for leg, _do, customer in rows:
            e = earnings.get(leg.id)
            status = "PAID" if (e and e["settled"]) else ("PENDING" if e else "UNBILLED")
            if status_filter and status_filter.upper() != status:
                continue
            items.append({
                "settlement_id": leg.id,   # leg 기준 (per-leg settlement 폐지)
                "leg_id": leg.id,
                "delivery_order_id": leg.delivery_order_id,
                "customer_name": customer.name if customer else None,
                "settlement_status": status,
                "final_amount": e["amount"] if e else None,
                "completed_at": leg.completed_at,
            })
        next_cursor = items[-1]["settlement_id"] if has_more and items else None
        return {"items": items, "has_more": has_more, "next_cursor": next_cursor}

    # ── leg detail (오더 상세 — 화면 4) ──────────────

    async def get_leg_detail(self, leg_id: int, *, user_id: int) -> dict:
        """본인 leg 의 상세 — D/O / customer / pickup / delivery / container 한 응답에 조립.

        반환 dict — driver_mobile.schemas.response.LegDetailResponse 와 1:1.
        """
        from container.model import ContainerModel

        driver_id = await self.resolve_driver_id(user_id)

        # 본인 leg + nested 정보 한 번에
        stmt = (
            select(LegModel, DeliveryOrderModel, CustomerModel,
                   ContainerModel)
            .join(DeliveryOrderModel, and_(
                DeliveryOrderModel.team_id == LegModel.team_id,
                DeliveryOrderModel.id == LegModel.delivery_order_id,
            ))
            .outerjoin(CustomerModel, and_(
                CustomerModel.team_id == DeliveryOrderModel.team_id,
                CustomerModel.id == DeliveryOrderModel.customer_id,
            ))
            .outerjoin(ContainerModel, and_(
                ContainerModel.team_id == LegModel.team_id,
                ContainerModel.id == LegModel.container_id,
            ))
            .where(
                LegModel.team_id == self.team_id,
                LegModel.id == leg_id,
                LegModel.is_active.is_(True),
            )
        )
        row = (await self.db.execute(stmt)).first()
        if not row:
            raise NotFoundException("Leg")

        leg, do, customer, container = row
        if leg.driver_id != driver_id:
            raise AppException(
                code="ERR_FORBIDDEN_LEG",
                message="Leg not assigned to you",
                status_code=403,
            )

        # pickup/delivery = leg 의 from_point/to_point(타입별 마스터) 해석
        pickup_loc = await self._resolve_point(leg.from_point_id)
        delivery_loc = await self._resolve_point(leg.to_point_id)

        # 운임 — payroll 라인 base
        revenue: Decimal | None = None
        earnings = await self._earnings_by_leg([leg.id])
        e = earnings.get(leg.id)
        if e:
            revenue = e["amount"]

        return {
            "leg_id": leg.id,
            "delivery_order_id": leg.delivery_order_id,
            "status": leg.status.value,
            "step": leg.step.value if leg.step else None,
            "bl_number": do.bl_number,
            "booking_number": do.booking_number,
            "reference": do.reference,
            "customer_name": customer.name if customer else None,
            "customer_contact": customer.contact_phone if customer else None,
            "container_number": container.container_number if container else None,
            "container_size": container.size.value if (container and container.size) else None,
            "pickup_location_name": pickup_loc.name if pickup_loc else None,
            "pickup_address": pickup_loc.address if pickup_loc else None,
            "pickup_latitude": float(pickup_loc.latitude) if (pickup_loc and pickup_loc.latitude) else None,
            "pickup_longitude": float(pickup_loc.longitude) if (pickup_loc and pickup_loc.longitude) else None,
            "delivery_location_name": delivery_loc.name if delivery_loc else None,
            "delivery_address": delivery_loc.address if delivery_loc else None,
            "delivery_latitude": float(delivery_loc.latitude) if (delivery_loc and delivery_loc.latitude) else None,
            "delivery_longitude": float(delivery_loc.longitude) if (delivery_loc and delivery_loc.longitude) else None,
            "pickup_date": leg.pickup_date,
            "delivery_date": leg.delivery_date,
            "started_at": leg.started_at,
            "arrived_at": leg.arrived_at,
            "completed_at": leg.completed_at,
            "offered_at": leg.offered_at,
            "accepted_at": leg.accepted_at,
            "distance_km": Decimal("42.5"),     # 데모 단순화
            "expected_minutes": 75,
            "expected_revenue": revenue or Decimal("180000"),
            "internal_note": do.internal_note,
        }

    # ── private ──────────────────────────────────────

    async def _get_owned_leg(self, leg_id: int, user_id: int) -> LegModel:
        driver_id = await self.resolve_driver_id(user_id)
        stmt = select(LegModel).where(
            LegModel.team_id == self.team_id,
            LegModel.id == leg_id,
            LegModel.is_active.is_(True),
        )
        leg = (await self.db.execute(stmt)).scalar_one_or_none()
        if not leg:
            raise NotFoundException("Leg")
        if leg.driver_id != driver_id:
            raise AppException(code="ERR_FORBIDDEN_LEG", message="Leg not assigned to you", status_code=403)
        return leg
