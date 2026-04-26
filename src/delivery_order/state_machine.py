# src/delivery_order/state_machine.py
"""D/O 상태 머신 + 게이트 조건.

전이:
  PLANNING → DISPATCHED ─┬─► YARD_STAGED ─► FINAL_DELIVERY ─┬─► EMPTY_STAGED ─► COMPLETED
                         │                                  │
                         └──► FINAL_DELIVERY ───────────────┴─► COMPLETED

게이트는 service.transition 가 검증. 위반 시 InvalidStateTransitionError.
"""
from __future__ import annotations
from dataclasses import dataclass

from common.exceptions.base import AppException
from delivery_order.const.status import DeliveryStatus, ShipmentDirection
from delivery_order.model import DeliveryOrderModel
from leg.const.status import LegStatus
from leg.model import LegModel
from location.const.kind import LocationKind
from location.model import LocationModel


class InvalidStateTransitionError(AppException):
    code = "ERR_INVALID_STATE_TRANSITION"
    status_code = 422


@dataclass
class TransitionContext:
    """게이트 검증을 위한 컨텍스트 — service 가 사전 로드."""
    do: DeliveryOrderModel
    legs: list[LegModel]
    delivery_location: LocationModel | None
    return_location: LocationModel | None


def _first_leg(ctx: TransitionContext) -> LegModel | None:
    return ctx.legs[0] if ctx.legs else None


def _last_completed_leg(ctx: TransitionContext) -> LegModel | None:
    """가장 최근 완료된 Leg."""
    completed = [l for l in ctx.legs if l.status == LegStatus.COMPLETED]
    if not completed:
        return None
    return max(completed, key=lambda l: l.completed_at or l.created_at)


_ALLOWED: dict[DeliveryStatus, set[DeliveryStatus]] = {
    DeliveryStatus.PLANNING:       {DeliveryStatus.DISPATCHED},
    DeliveryStatus.DISPATCHED:     {DeliveryStatus.YARD_STAGED, DeliveryStatus.FINAL_DELIVERY},
    DeliveryStatus.YARD_STAGED:    {DeliveryStatus.FINAL_DELIVERY},
    DeliveryStatus.FINAL_DELIVERY: {DeliveryStatus.EMPTY_STAGED, DeliveryStatus.COMPLETED},
    DeliveryStatus.EMPTY_STAGED:   {DeliveryStatus.COMPLETED},
    DeliveryStatus.COMPLETED:      set(),
}


def assert_can_transition(ctx: TransitionContext, target: DeliveryStatus) -> None:
    """게이트 검증. 위반 시 InvalidStateTransitionError raise."""
    do = ctx.do
    src = do.status

    # 1) 기본 전이 그래프
    allowed = _ALLOWED.get(src, set())
    if target not in allowed:
        raise InvalidStateTransitionError(
            f"Cannot transition {src.value} → {target.value}",
            details={"from": src.value, "to": target.value, "allowed": [s.value for s in allowed]},
        )

    # 2) 도메인별 게이트
    if src == DeliveryStatus.PLANNING and target == DeliveryStatus.DISPATCHED:
        # First Leg + 모든 게이트 플래그 + pickup 필수
        first = _first_leg(ctx)
        if not first:
            raise InvalidStateTransitionError("DISPATCHED 전이는 first leg 필수")
        if not (do.bl_released and do.pier_pass_paid and do.customs_cleared):
            raise InvalidStateTransitionError(
                "DISPATCHED 전이는 bl_released + pier_pass_paid + customs_cleared 필수",
            )
        if not do.pickup_appointment:
            raise InvalidStateTransitionError("DISPATCHED 전이는 pickup_appointment 필수")
        if not first.driver_id:
            raise InvalidStateTransitionError("DISPATCHED 전이는 first leg 의 driver_id 필수")
        if not first.pickup_date:
            raise InvalidStateTransitionError("DISPATCHED 전이는 first leg 의 pickup_date 필수")

    elif src == DeliveryStatus.DISPATCHED and target == DeliveryStatus.YARD_STAGED:
        first = _first_leg(ctx)
        if not first or first.status != LegStatus.COMPLETED:
            raise InvalidStateTransitionError("YARD_STAGED 전이는 first leg COMPLETED 필수")
        if not ctx.delivery_location or ctx.delivery_location.kind != LocationKind.YARD:
            raise InvalidStateTransitionError("YARD_STAGED 전이는 delivery_location 이 YARD 여야 함")

    elif src == DeliveryStatus.DISPATCHED and target == DeliveryStatus.FINAL_DELIVERY:
        first = _first_leg(ctx)
        if not first or first.status != LegStatus.COMPLETED:
            raise InvalidStateTransitionError("FINAL_DELIVERY 전이는 first leg COMPLETED 필수")
        if not ctx.delivery_location or ctx.delivery_location.kind != LocationKind.CUSTOMER:
            raise InvalidStateTransitionError("FINAL_DELIVERY 전이는 delivery_location 이 CUSTOMER 여야 함")
        if not do.delivery_appointment:
            raise InvalidStateTransitionError("FINAL_DELIVERY 전이는 delivery_appointment 필수")

    elif src == DeliveryStatus.YARD_STAGED and target == DeliveryStatus.FINAL_DELIVERY:
        last = _last_completed_leg(ctx)
        if not last:
            raise InvalidStateTransitionError("FINAL_DELIVERY 전이는 야드→고객사 Leg COMPLETED 필수")
        if not do.delivery_appointment:
            raise InvalidStateTransitionError("FINAL_DELIVERY 전이는 delivery_appointment 필수")

    elif src == DeliveryStatus.FINAL_DELIVERY and target == DeliveryStatus.EMPTY_STAGED:
        last = _last_completed_leg(ctx)
        if not last:
            raise InvalidStateTransitionError("EMPTY_STAGED 전이는 반납 Leg COMPLETED 필수")
        if not ctx.delivery_location or ctx.delivery_location.kind != LocationKind.YARD:
            raise InvalidStateTransitionError("EMPTY_STAGED 전이는 delivery_location 이 YARD 여야 함")

    elif target == DeliveryStatus.COMPLETED:
        # FINAL_DELIVERY → COMPLETED 또는 EMPTY_STAGED → COMPLETED
        last = _last_completed_leg(ctx)
        if not last:
            raise InvalidStateTransitionError("COMPLETED 전이는 반납 Leg COMPLETED 필수")
        if not do.return_location_id:
            raise InvalidStateTransitionError("COMPLETED 전이는 return_location 필수")
        if not do.return_appointment:
            raise InvalidStateTransitionError("COMPLETED 전이는 return_appointment 필수")
        if not do.detention_lfd:
            raise InvalidStateTransitionError("COMPLETED 전이는 detention_lfd 필수")
        if do.direction == ShipmentDirection.IMPORT and not do.empty_date:
            raise InvalidStateTransitionError("IMPORT COMPLETED 전이는 empty_date 필수")
        if do.direction == ShipmentDirection.EXPORT and not do.loaded_date:
            raise InvalidStateTransitionError("EXPORT COMPLETED 전이는 loaded_date 필수")
