"""Delivery Order 상태 머신.

별도 파일로 분리한 이유: 게이트 조건이 도메인 핵심 로직이라 service 와 분리해
독립적으로 테스트/리뷰가 용이.

게이트 조건 (요구사항 v3 기준):
- PLANNING → DISPATCHED:
    First Leg 생성 + bl_released + pier_pass_paid + customs_cleared
    + pickup_appointment + first_leg.driver_id + first_leg.pickup_date
- DISPATCHED → YARD_STAGED:
    First Leg COMPLETED + first_leg.delivery_location 이 야드(YARD)
- DISPATCHED → FINAL_DELIVERY:
    First Leg COMPLETED + first_leg.delivery_location 이 고객사(CUSTOMER)
    + delivery_appointment
- YARD_STAGED → FINAL_DELIVERY:
    야드→고객사 Leg COMPLETED + delivery_appointment
- FINAL_DELIVERY → EMPTY_STAGED:
    반납 Leg COMPLETED + delivery_location 이 야드(YARD)
- FINAL_DELIVERY → COMPLETED:
    반납 Leg COMPLETED + return_location + return_appointment + detention_lfd
    + (IMPORT 면 empty_date, EXPORT 면 loaded_date)
- EMPTY_STAGED → COMPLETED: 위와 동일
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.exceptions import InvalidStateTransitionError
from app.domains.delivery_orders.models import DeliveryOrder
from app.domains.legs.models import Leg
from app.domains.locations.models import Location
from app.models.enums import DeliveryStatus, LegStatus, LocationKind, ShipmentDirection


@dataclass
class TransitionContext:
    """상태 전이 검증을 위한 보조 컨텍스트.

    repository 에서 채워서 넘김 — state_machine 자체는 DB 모름.
    """

    do: DeliveryOrder
    legs: list[Leg] = field(default_factory=list)
    locations_by_id: dict[str, Location] = field(default_factory=dict)

    def first_leg(self) -> Leg | None:
        if not self.legs:
            return None
        return sorted(self.legs, key=lambda l: l.created_at)[0]

    def last_leg(self) -> Leg | None:
        if not self.legs:
            return None
        return sorted(self.legs, key=lambda l: l.created_at)[-1]

    def location_kind(self, loc_id: str | None) -> LocationKind | None:
        if not loc_id:
            return None
        loc = self.locations_by_id.get(loc_id)
        return loc.kind if loc else None


_ALLOWED: dict[DeliveryStatus, set[DeliveryStatus]] = {
    DeliveryStatus.PLANNING: {DeliveryStatus.DISPATCHED},
    DeliveryStatus.DISPATCHED: {
        DeliveryStatus.YARD_STAGED,
        DeliveryStatus.FINAL_DELIVERY,
    },
    DeliveryStatus.YARD_STAGED: {DeliveryStatus.FINAL_DELIVERY},
    DeliveryStatus.FINAL_DELIVERY: {
        DeliveryStatus.EMPTY_STAGED,
        DeliveryStatus.COMPLETED,
    },
    DeliveryStatus.EMPTY_STAGED: {DeliveryStatus.COMPLETED},
    DeliveryStatus.COMPLETED: set(),
}


def assert_can_transition(ctx: TransitionContext, target: DeliveryStatus) -> None:
    src = ctx.do.status
    if target not in _ALLOWED.get(src, set()):
        raise InvalidStateTransitionError(
            f"Cannot transition {src.value} → {target.value}",
            details={"from": src.value, "to": target.value},
        )

    if src == DeliveryStatus.PLANNING and target == DeliveryStatus.DISPATCHED:
        _check_planning_to_dispatched(ctx)
    elif src == DeliveryStatus.DISPATCHED and target == DeliveryStatus.YARD_STAGED:
        _check_dispatched_to_yard_staged(ctx)
    elif src == DeliveryStatus.DISPATCHED and target == DeliveryStatus.FINAL_DELIVERY:
        _check_dispatched_to_final_delivery(ctx)
    elif src == DeliveryStatus.YARD_STAGED and target == DeliveryStatus.FINAL_DELIVERY:
        _check_yard_staged_to_final_delivery(ctx)
    elif src == DeliveryStatus.FINAL_DELIVERY and target == DeliveryStatus.EMPTY_STAGED:
        _check_final_delivery_to_empty_staged(ctx)
    elif src in (DeliveryStatus.FINAL_DELIVERY, DeliveryStatus.EMPTY_STAGED) and target == DeliveryStatus.COMPLETED:
        _check_to_completed(ctx)


def _missing(name: str, target: DeliveryStatus) -> None:
    raise InvalidStateTransitionError(
        f"Missing prerequisite for transition to {target.value}: {name}",
        details={"missing": name, "to": target.value},
    )


def _check_planning_to_dispatched(ctx: TransitionContext) -> None:
    do = ctx.do
    leg = ctx.first_leg()
    if not leg:
        _missing("first_leg", DeliveryStatus.DISPATCHED)
    if not do.bl_released:
        _missing("bl_released", DeliveryStatus.DISPATCHED)
    if not do.pier_pass_paid:
        _missing("pier_pass_paid", DeliveryStatus.DISPATCHED)
    if not do.customs_cleared:
        _missing("customs_cleared", DeliveryStatus.DISPATCHED)
    if not do.pickup_appointment:
        _missing("pickup_appointment", DeliveryStatus.DISPATCHED)
    if leg and not leg.driver_id:
        _missing("first_leg.driver_id", DeliveryStatus.DISPATCHED)
    if leg and not leg.pickup_date:
        _missing("first_leg.pickup_date", DeliveryStatus.DISPATCHED)


def _require_completed(leg: Leg | None, target: DeliveryStatus, label: str) -> None:
    if leg is None:
        _missing(label, target)
    if leg and leg.status != LegStatus.COMPLETED:
        _missing(f"{label}.status=COMPLETED", target)


def _check_dispatched_to_yard_staged(ctx: TransitionContext) -> None:
    leg = ctx.first_leg()
    _require_completed(leg, DeliveryStatus.YARD_STAGED, "first_leg")
    if leg and ctx.location_kind(leg.delivery_location_id) != LocationKind.YARD:
        _missing("first_leg.delivery_location.kind=YARD", DeliveryStatus.YARD_STAGED)


def _check_dispatched_to_final_delivery(ctx: TransitionContext) -> None:
    leg = ctx.first_leg()
    _require_completed(leg, DeliveryStatus.FINAL_DELIVERY, "first_leg")
    if leg and ctx.location_kind(leg.delivery_location_id) != LocationKind.CUSTOMER:
        _missing("first_leg.delivery_location.kind=CUSTOMER", DeliveryStatus.FINAL_DELIVERY)
    if not ctx.do.delivery_appointment:
        _missing("delivery_appointment", DeliveryStatus.FINAL_DELIVERY)


def _check_yard_staged_to_final_delivery(ctx: TransitionContext) -> None:
    delivery_legs = [l for l in ctx.legs if l.step == DeliveryStatus.FINAL_DELIVERY]
    leg = max(delivery_legs, key=lambda l: l.created_at) if delivery_legs else None
    _require_completed(leg, DeliveryStatus.FINAL_DELIVERY, "yard_to_customer_leg")
    if not ctx.do.delivery_appointment:
        _missing("delivery_appointment", DeliveryStatus.FINAL_DELIVERY)


def _check_final_delivery_to_empty_staged(ctx: TransitionContext) -> None:
    return_legs = [l for l in ctx.legs if l.step == DeliveryStatus.EMPTY_STAGED]
    leg = max(return_legs, key=lambda l: l.created_at) if return_legs else None
    _require_completed(leg, DeliveryStatus.EMPTY_STAGED, "return_leg")
    if leg and ctx.location_kind(leg.delivery_location_id) != LocationKind.YARD:
        _missing("return_leg.delivery_location.kind=YARD", DeliveryStatus.EMPTY_STAGED)


def _check_to_completed(ctx: TransitionContext) -> None:
    do = ctx.do
    return_legs = [l for l in ctx.legs if l.step == DeliveryStatus.COMPLETED]
    leg = max(return_legs, key=lambda l: l.created_at) if return_legs else None
    _require_completed(leg, DeliveryStatus.COMPLETED, "return_leg")
    if not do.return_location_id:
        _missing("return_location_id", DeliveryStatus.COMPLETED)
    if not do.return_appointment:
        _missing("return_appointment", DeliveryStatus.COMPLETED)
    if not do.detention_lfd:
        _missing("detention_lfd", DeliveryStatus.COMPLETED)
    if do.direction == ShipmentDirection.IMPORT and not do.empty_date:
        _missing("empty_date", DeliveryStatus.COMPLETED)
    if do.direction == ShipmentDirection.EXPORT and not do.loaded_date:
        _missing("loaded_date", DeliveryStatus.COMPLETED)
