# src/delivery_order/state_machine.py
"""D/O 상태 머신 + 게이트 조건.

H-1 이후 컨테이너 정규화로 인해 위치/일정/게이트 플래그가 ContainerModel 로 이동.
정밀 게이트 검증은 H-6 (leg_stop) 에서 컨테이너·leg 정합성과 함께 재설계.
H-1 단계에선:
  - 기본 전이 그래프 검증
  - 디스패처 수동 점프 허용 (관리자 권한이면 임의 전이)
"""
from __future__ import annotations
from dataclasses import dataclass

from common.exceptions.base import AppException
from delivery_order.const.status import DeliveryStatus
from delivery_order.model import DeliveryOrderModel
from leg.model import LegModel


class InvalidStateTransitionError(AppException):
    """D/O / Leg 상태 전이 게이트 위반."""
    def __init__(self, message: str = "Invalid state transition", *, details: dict | None = None):
        super().__init__(
            code="ERR_INVALID_STATE_TRANSITION",
            message=message,
            status_code=422,
            detail=details,
        )


@dataclass
class TransitionContext:
    """게이트 검증을 위한 컨텍스트 — service 가 사전 로드."""
    do: DeliveryOrderModel
    legs: list[LegModel]


# 재설계: DISPATCHING(자동 파생) 추가. PLANNING↔DISPATCHING↔DISPATCHED 는 보통
# delivery_order/state_derive.py 가 leg 기준으로 자동 관리. 수동 전이도 허용되도록 그래프에 포함.
_ALLOWED: dict[DeliveryStatus, set[DeliveryStatus]] = {
    DeliveryStatus.PLANNING:       {DeliveryStatus.DISPATCHING, DeliveryStatus.DISPATCHED},
    DeliveryStatus.DISPATCHING:    {DeliveryStatus.DISPATCHED, DeliveryStatus.PLANNING,
                                    DeliveryStatus.YARD_STAGED, DeliveryStatus.FINAL_DELIVERY},
    DeliveryStatus.DISPATCHED:     {DeliveryStatus.DISPATCHING, DeliveryStatus.YARD_STAGED,
                                    DeliveryStatus.FINAL_DELIVERY, DeliveryStatus.PLANNING},
    DeliveryStatus.YARD_STAGED:    {DeliveryStatus.FINAL_DELIVERY, DeliveryStatus.DISPATCHED},
    DeliveryStatus.FINAL_DELIVERY: {DeliveryStatus.EMPTY_STAGED, DeliveryStatus.COMPLETED, DeliveryStatus.YARD_STAGED},
    DeliveryStatus.EMPTY_STAGED:   {DeliveryStatus.COMPLETED, DeliveryStatus.FINAL_DELIVERY},
    DeliveryStatus.COMPLETED:      {DeliveryStatus.EMPTY_STAGED},  # 사후 보정 허용
}


def assert_can_transition(ctx: TransitionContext, target: DeliveryStatus, *, force: bool = False) -> None:
    """게이트 검증. force=True 면 그래프 검증도 생략 (관리자 점프)."""
    if force:
        return

    do = ctx.do
    src = do.status
    allowed = _ALLOWED.get(src, set())
    if target not in allowed:
        raise InvalidStateTransitionError(
            f"Cannot transition {src.value} → {target.value}",
            details={"from": src.value, "to": target.value, "allowed": [s.value for s in allowed]},
        )
