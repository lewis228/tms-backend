# src/driver_mobile/service.py
"""Driver mobile 비즈니스 로직 — leg/file/user 재사용 + driver 매핑."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, AppException
from driver.model import DriverModel
from leg.const.status import LegStatus
from leg.model import LegModel


class DriverMobileService:
    def __init__(self, db: AsyncSession, tenant_id: int) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def resolve_driver_id(self, user_id: int) -> int:
        """User → 그 tenant 의 Driver row.id 매핑."""
        stmt = select(DriverModel.id).where(
            DriverModel.tenant_id == self.tenant_id,
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
                LegModel.tenant_id == self.tenant_id,
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
            LegModel.tenant_id == self.tenant_id,
            LegModel.id == leg_id,
            LegModel.is_active.is_(True),
        )
        leg = (await self.db.execute(stmt)).scalar_one_or_none()
        if not leg:
            raise NotFoundException("Leg")
        if leg.driver_id != driver_id:
            class ForbiddenLegError(AppException):
                code = "ERR_FORBIDDEN_LEG"
                status_code = 403
            raise ForbiddenLegError("Leg not assigned to current driver")

        svc = LegService(self.db, self.tenant_id)
        result = await svc.transition(
            leg_id, target,
            failure_reason=failure_reason,
            actor_user_id=user_id,
        )
        return result
