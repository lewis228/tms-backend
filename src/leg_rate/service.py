# src/leg_rate/service.py
"""v3 LegRate 서비스 — Snapshot Always Freeze 정책의 핵심.

- get_or_calc(leg_id): 기존 leg_rate 가 있으면 그대로, 없으면 lookup → snapshot 박아 INSERT.
- recalculate(leg_id): 명시적 재계산 — 새 마스터 값으로 LegRate 박힘. (정산 안전성을 위해 자동 X)
- update(): manual_override (base_amount 수동 입력).

Lookup 우선순위:
  1) RateQuote (정찰가) — exact location pair + size + move_type + customer 매칭
  2) RateTariff (거리×단가룰) — move_type + size + customer
     base = flat_base + per_value × distance + per_min × duration
  3) 둘 다 없으면 source=NONE, base=0
"""
from __future__ import annotations
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from common.exceptions.base import NotFoundException, BadRequestException
from leg_rate.model import LegRateModel
from leg.model import LegModel
from leg.const.status import LegRateSource
from rate_quote.model import RateQuoteModel
from rate_tariff.model import RateTariffModel
from distance_matrix.model import DistanceMatrixModel
from container.schemas.response import LegRateResponseSchema
from leg_rate.schemas.request import LegRateUpdateRequest, RateCalculateRequest


class LegRateService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id

    # ────────────────────────────────────────────────────────────
    # Lookup helpers
    # ────────────────────────────────────────────────────────────
    async def _quote_lookup(
        self, *, origin: int | None, dest: int | None,
        size: str | None, move_type: str | None, customer_id: int | None,
        asof: date,
    ) -> Optional[RateQuoteModel]:
        if not (origin and dest):
            return None
        conds = [
            RateQuoteModel.team_id == self.team_id,
            RateQuoteModel.is_active.is_(True),
            RateQuoteModel.origin_location_id == origin,
            RateQuoteModel.destination_location_id == dest,
            RateQuoteModel.effective_from <= asof,
            or_(RateQuoteModel.effective_to.is_(None), RateQuoteModel.effective_to >= asof),
        ]
        # size / move_type / customer 는 wildcard 허용 (NULL 또는 일치)
        if size:
            conds.append(or_(RateQuoteModel.container_size.is_(None), RateQuoteModel.container_size == size))
        if move_type:
            conds.append(or_(RateQuoteModel.move_type.is_(None), RateQuoteModel.move_type == move_type))
        if customer_id is not None:
            conds.append(or_(RateQuoteModel.customer_id.is_(None), RateQuoteModel.customer_id == customer_id))
        q = select(RateQuoteModel).where(and_(*conds)).order_by(RateQuoteModel.priority.desc()).limit(1)
        return (await self.db.execute(q)).scalar_one_or_none()

    async def _tariff_lookup(
        self, *, size: str | None, move_type: str | None, customer_id: int | None, asof: date,
    ) -> Optional[RateTariffModel]:
        conds = [
            RateTariffModel.team_id == self.team_id,
            RateTariffModel.is_active.is_(True),
            RateTariffModel.effective_from <= asof,
            or_(RateTariffModel.effective_to.is_(None), RateTariffModel.effective_to >= asof),
        ]
        if size:
            conds.append(or_(RateTariffModel.container_size.is_(None), RateTariffModel.container_size == size))
        if move_type:
            conds.append(or_(RateTariffModel.move_type.is_(None), RateTariffModel.move_type == move_type))
        if customer_id is not None:
            conds.append(or_(RateTariffModel.customer_id.is_(None), RateTariffModel.customer_id == customer_id))
        q = select(RateTariffModel).where(and_(*conds)).order_by(RateTariffModel.priority.desc()).limit(1)
        return (await self.db.execute(q)).scalar_one_or_none()

    async def _distance_lookup(self, origin: int, dest: int) -> Optional[DistanceMatrixModel]:
        q = select(DistanceMatrixModel).where(
            DistanceMatrixModel.team_id == self.team_id,
            DistanceMatrixModel.origin_location_id == origin,
            DistanceMatrixModel.destination_location_id == dest,
            DistanceMatrixModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    # ────────────────────────────────────────────────────────────
    # Compute (snapshot 박지 않고 dict 만 리턴)
    # ────────────────────────────────────────────────────────────
    async def compute(self, payload: RateCalculateRequest) -> dict:
        asof = datetime.now(timezone.utc).date()

        # 1) Quote
        quote = await self._quote_lookup(
            origin=payload.origin_location_id,
            dest=payload.destination_location_id,
            size=payload.container_size,
            move_type=payload.move_type,
            customer_id=payload.customer_id,
            asof=asof,
        )
        if quote:
            return {
                "rate_quote_id": quote.id,
                "rate_tariff_id": None,
                "snapshot_distance_value": None,
                "snapshot_duration_min": None,
                "snapshot_per_value": None,
                "snapshot_per_min": None,
                "snapshot_flat_base": None,
                "snapshot_quote_fixed": quote.fixed_amount,
                "base_amount": quote.fixed_amount,
                "source": LegRateSource.QUOTE_FIXED,
            }

        # 2) Tariff
        tariff = await self._tariff_lookup(
            size=payload.container_size,
            move_type=payload.move_type,
            customer_id=payload.customer_id,
            asof=asof,
        )
        distance_value = Decimal("0")
        duration_min = Decimal("0")
        dm = None
        if payload.origin_location_id and payload.destination_location_id:
            dm = await self._distance_lookup(payload.origin_location_id, payload.destination_location_id)
            if dm:
                distance_value = dm.distance_value
                duration_min = dm.duration_min

        if tariff is None:
            return {
                "rate_quote_id": None,
                "rate_tariff_id": None,
                "snapshot_distance_value": distance_value,
                "snapshot_duration_min": duration_min,
                "snapshot_per_value": None,
                "snapshot_per_min": None,
                "snapshot_flat_base": None,
                "snapshot_quote_fixed": None,
                "base_amount": Decimal("0"),
                "source": LegRateSource.NONE,
            }

        if dm is None:
            base = tariff.flat_base or Decimal("0")
            source = LegRateSource.TARIFF_FLAT
        else:
            base = (tariff.flat_base or Decimal("0")) \
                 + (tariff.per_value or Decimal("0")) * distance_value \
                 + (tariff.per_min   or Decimal("0")) * duration_min
            source = LegRateSource.TARIFF_CALC

        return {
            "rate_quote_id": None,
            "rate_tariff_id": tariff.id,
            "snapshot_distance_value": distance_value,
            "snapshot_duration_min": duration_min,
            "snapshot_per_value": tariff.per_value,
            "snapshot_per_min": tariff.per_min,
            "snapshot_flat_base": tariff.flat_base,
            "snapshot_quote_fixed": None,
            "base_amount": base.quantize(Decimal("0.01")),
            "source": source,
        }

    # ────────────────────────────────────────────────────────────
    # Get / Recalc / Update
    # ────────────────────────────────────────────────────────────
    async def _ensure_leg(self, leg_id: int) -> LegModel:
        leg = (await self.db.execute(
            select(LegModel).where(LegModel.team_id == self.team_id, LegModel.id == leg_id)
        )).scalar_one_or_none()
        if not leg:
            raise NotFoundException("Leg")
        return leg

    async def _get_existing(self, leg_id: int) -> Optional[LegRateModel]:
        return (await self.db.execute(
            select(LegRateModel).where(
                LegRateModel.team_id == self.team_id,
                LegRateModel.leg_id == leg_id,
                LegRateModel.is_active.is_(True),
            )
        )).scalar_one_or_none()

    async def get_or_calc(self, leg_id: int, *, actor_user_id: int | None = None) -> LegRateResponseSchema:
        existing = await self._get_existing(leg_id)
        if existing:
            return LegRateResponseSchema.model_validate(existing)

        leg = await self._ensure_leg(leg_id)
        # leg 의 from_stop / to_stop 에서 location 을 추출
        from container_stop.model import ContainerStopModel
        origin_id = None
        dest_id = None
        if leg.from_stop_id:
            s = (await self.db.execute(select(ContainerStopModel).where(ContainerStopModel.id == leg.from_stop_id))).scalar_one_or_none()
            if s: origin_id = s.location_id
        if leg.to_stop_id:
            s = (await self.db.execute(select(ContainerStopModel).where(ContainerStopModel.id == leg.to_stop_id))).scalar_one_or_none()
            if s: dest_id = s.location_id
        # 없으면 leg.pickup/delivery_location_id (legacy fallback)
        if origin_id is None:
            origin_id = leg.pickup_location_id
        if dest_id is None:
            dest_id = leg.delivery_location_id

        # container.size 조회 (옵션)
        size_value = None
        if leg.container_id:
            from container.model import ContainerModel
            c = (await self.db.execute(select(ContainerModel).where(ContainerModel.id == leg.container_id))).scalar_one_or_none()
            if c and c.size:
                size_value = c.size.value if hasattr(c.size, "value") else str(c.size)

        # customer
        customer_id = None
        if leg.delivery_order_id:
            from delivery_order.model import DeliveryOrderModel
            do = (await self.db.execute(select(DeliveryOrderModel).where(DeliveryOrderModel.id == leg.delivery_order_id))).scalar_one_or_none()
            if do:
                customer_id = do.customer_id

        move_type_v3 = leg.move_type_v3.value if leg.move_type_v3 and hasattr(leg.move_type_v3, "value") else (str(leg.move_type_v3) if leg.move_type_v3 else None)

        result = await self.compute(RateCalculateRequest(
            origin_location_id=origin_id,
            destination_location_id=dest_id,
            container_size=size_value,
            move_type=move_type_v3,
            customer_id=customer_id,
        ))

        row = LegRateModel(
            team_id=self.team_id,
            leg_id=leg_id,
            **result,
            payee_driver_id=leg.driver_id,
            computed_at=datetime.now(timezone.utc),
        )
        if actor_user_id is not None:
            row.created_by_user_id = actor_user_id
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return LegRateResponseSchema.model_validate(row)

    async def recalculate(self, leg_id: int, *, actor_user_id: int | None = None) -> LegRateResponseSchema:
        """⚠️ 명시적 재계산. 마스터의 현재 값으로 snapshot 새로 박음.

        정산 안전성: 자동 호출되면 안 됨. 디스패처가 명시적 버튼 클릭한 경우에만.
        """
        existing = await self._get_existing(leg_id)
        # 기존 row 비활성화
        if existing:
            existing.is_active = False
            if actor_user_id is not None:
                existing.updated_by_user_id = actor_user_id
            await self.db.flush()
        return await self.get_or_calc(leg_id, actor_user_id=actor_user_id)

    async def update(self, leg_id: int, payload: LegRateUpdateRequest, *, actor_user_id: int | None = None) -> LegRateResponseSchema:
        from realtime.v3_publish import safe_publish, EVT_LEG_RATE_UPDATED
        row = await self._get_existing(leg_id)
        if not row:
            # 없으면 자동 생성 후 update
            await self.get_or_calc(leg_id, actor_user_id=actor_user_id)
            row = await self._get_existing(leg_id)
            if not row:
                raise NotFoundException("Leg Rate")
        data = payload.model_dump(exclude_unset=True)
        if "base_amount" in data and data["base_amount"] is not None:
            row.base_amount = data["base_amount"]
            row.manual_override = True
            row.source = LegRateSource.MANUAL
        if "payee_driver_id" in data:
            row.payee_driver_id = data["payee_driver_id"]
        if "note" in data:
            row.note = data["note"]
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        await safe_publish(
            type=EVT_LEG_RATE_UPDATED, team_id=self.team_id, actor_id=actor_user_id,
            payload={"leg_id": leg_id, "base_amount": str(row.base_amount), "source": row.source.value},
        )
        return LegRateResponseSchema.model_validate(row)
