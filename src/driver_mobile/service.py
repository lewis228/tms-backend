# src/driver_mobile/service.py
"""Driver mobile 비즈니스 로직 — leg/file/user 재사용 + driver 매핑."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, AppException
from driver.model import DriverModel
from driver.const.status import DutyStatus
from leg.const.status import LegStatus
from leg.model import LegModel
from delivery_order.model import DeliveryOrderModel
from customer.model import CustomerModel
from location.model import LocationModel
from settlement.model import SettlementModel
from settlement.const.status import SettlementStatus
from user.model import UserModel
from truck.model import TruckModel


class DriverMobileService:
    def __init__(self, db: AsyncSession, team_id: int) -> None:
        self.db = db
        self.team_id = team_id

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

        # 예상 수익 — 해당 leg 의 settlement.final_amount (없으면 0)
        leg_ids = [l.id for l in completed_legs]
        revenue = Decimal(0)
        if leg_ids:
            sum_stmt = select(func.coalesce(func.sum(SettlementModel.final_amount), 0)).where(
                SettlementModel.team_id == self.team_id,
                SettlementModel.leg_id.in_(leg_ids),
                SettlementModel.is_active.is_(True),
            )
            revenue = Decimal(str((await self.db.execute(sum_stmt)).scalar_one() or 0))

        # 거리 — 데모용 단순화: 완료된 leg 1건당 35km 가정 (실제는 distance_matrix join)
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

    async def list_pending_offers(self, user_id: int) -> list[dict]:
        """미수락 배차 — offered_at != NULL AND accepted_at IS NULL AND rejected_at IS NULL."""
        driver_id = await self.resolve_driver_id(user_id)
        stmt = (
            select(LegModel, DeliveryOrderModel, CustomerModel,
                   LocationModel, LocationModel)
            .join(DeliveryOrderModel, and_(
                DeliveryOrderModel.team_id == LegModel.team_id,
                DeliveryOrderModel.id == LegModel.delivery_order_id,
            ))
            .outerjoin(CustomerModel, and_(
                CustomerModel.team_id == DeliveryOrderModel.team_id,
                CustomerModel.id == DeliveryOrderModel.customer_id,
            ))
            .outerjoin(LocationModel, LocationModel.id == LegModel.pickup_location_id)
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
        # delivery location 별도 조회 (alias 복잡해서 단순화)
        offers: list[dict] = []
        for row in rows:
            leg, do, customer, pickup_loc, _ = row
            delivery_loc = None
            if leg.delivery_location_id:
                delivery_loc = (await self.db.execute(
                    select(LocationModel).where(LocationModel.id == leg.delivery_location_id)
                )).scalar_one_or_none()
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
        # settlement final_amount 같이 조회
        settlements = {}
        if leg_ids:
            s_stmt = select(SettlementModel).where(
                SettlementModel.team_id == self.team_id,
                SettlementModel.leg_id.in_(leg_ids),
                SettlementModel.is_active.is_(True),
            )
            for s in (await self.db.execute(s_stmt)).scalars().all():
                settlements[s.leg_id] = s

        for leg, do, customer in rows:
            s = settlements.get(leg.id)
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
                "revenue": s.final_amount if s else None,
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

        # 정산 모음
        s_stmt = select(SettlementModel).where(
            SettlementModel.team_id == self.team_id,
            SettlementModel.leg_id.in_(leg_ids),
            SettlementModel.is_active.is_(True),
        )
        settlements = list((await self.db.execute(s_stmt)).scalars().all())

        total_amount = sum((s.final_amount or Decimal(0) for s in settlements), Decimal(0))

        # 상태별 카운트 (단순 매핑)
        completed_count = sum(1 for s in settlements if s.is_settled)
        pending_count   = sum(1 for s in settlements if not s.is_settled and not s.has_flag)
        on_hold_count   = sum(1 for s in settlements if s.has_flag)

        # 주간 추이 — leg.completed_at 기준 4~5 주 split
        weekly_buckets: dict[int, Decimal] = {}
        weekly_starts: dict[int, datetime] = {}
        leg_map: dict[int, LegModel] = {
            l.id: l for l in (await self.db.execute(
                select(LegModel).where(LegModel.id.in_(leg_ids))
            )).scalars().all()
        }
        for s in settlements:
            leg = leg_map.get(s.leg_id)
            if not leg or not leg.completed_at:
                continue
            # 월 내 몇 번째 주인지 (1-based)
            week_no = (leg.completed_at.day - 1) // 7 + 1
            weekly_buckets.setdefault(week_no, Decimal(0))
            weekly_buckets[week_no] += s.final_amount or Decimal(0)
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
        """정산 목록 — driver 의 leg 들의 settlement 페이지네이션."""
        driver_id = await self.resolve_driver_id(user_id)

        # 본 driver 의 settlement 만 (leg.driver_id 매칭)
        stmt = (
            select(SettlementModel, LegModel, DeliveryOrderModel, CustomerModel)
            .join(LegModel, and_(
                LegModel.team_id == SettlementModel.team_id,
                LegModel.id == SettlementModel.leg_id,
            ))
            .join(DeliveryOrderModel, and_(
                DeliveryOrderModel.team_id == LegModel.team_id,
                DeliveryOrderModel.id == LegModel.delivery_order_id,
            ))
            .outerjoin(CustomerModel, and_(
                CustomerModel.team_id == DeliveryOrderModel.team_id,
                CustomerModel.id == DeliveryOrderModel.customer_id,
            ))
            .where(
                SettlementModel.team_id == self.team_id,
                SettlementModel.is_active.is_(True),
                LegModel.driver_id == driver_id,
            )
            .order_by(SettlementModel.id.desc())
            .limit(limit + 1)
        )
        if status_filter:
            try:
                status_enum = SettlementStatus(status_filter)
                stmt = stmt.where(SettlementModel.settlement_status == status_enum)
            except ValueError:
                pass
        if before_id is not None:
            stmt = stmt.where(SettlementModel.id < before_id)

        rows = (await self.db.execute(stmt)).all()
        has_more = len(rows) > limit
        rows = rows[:limit]

        items = [
            {
                "settlement_id": s.id,
                "leg_id": s.leg_id,
                "delivery_order_id": leg.delivery_order_id,
                "customer_name": customer.name if customer else None,
                "settlement_status": s.settlement_status.value,
                "final_amount": s.final_amount,
                "completed_at": leg.completed_at,
            }
            for s, leg, _do, customer in rows
        ]
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

        # location 정보 별도 조회
        pickup_loc = None
        delivery_loc = None
        if leg.pickup_location_id:
            pickup_loc = (await self.db.execute(
                select(LocationModel).where(LocationModel.id == leg.pickup_location_id)
            )).scalar_one_or_none()
        if leg.delivery_location_id:
            delivery_loc = (await self.db.execute(
                select(LocationModel).where(LocationModel.id == leg.delivery_location_id)
            )).scalar_one_or_none()

        # settlement 가 있으면 운임 가져옴
        revenue: Decimal | None = None
        s_stmt = select(SettlementModel).where(
            SettlementModel.team_id == self.team_id,
            SettlementModel.leg_id == leg.id,
            SettlementModel.is_active.is_(True),
        )
        settle = (await self.db.execute(s_stmt)).scalar_one_or_none()
        if settle:
            revenue = settle.final_amount or settle.system_total

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
