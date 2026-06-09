# src/delivery_order/state_derive.py
"""D/O dispatch-phase 자동 파생 (컨플루언스 + 사용자 규칙).

규칙(사용자 확정):
- D/O 는 컨테이너 N개, 컨테이너마다 leg N개.
- 활성 leg(PENDING/ASSIGNED) 중 **미배차(driver_id 없음)** leg 가
    · 0개  → DISPATCHED
    · ≥1개 → DISPATCHING
- 활성 leg 가 아예 없으면 → PLANNING
- 새 leg(미배차) 생기면 자동 DISPATCHING 회귀.

**dispatch-phase 한정**: 현재 status 가 {PLANNING, DISPATCHING, DISPATCHED} 일 때만 재계산.
진행 상태(YARD_STAGED/FINAL_DELIVERY/EMPTY_STAGED/COMPLETED)나 수동 전환은 건드리지 않는다.
leg 가 IN_TRANSIT 등으로 진행되면 디스패처가 transition 으로 진행상태로 올린다.
"""
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from delivery_order.model import DeliveryOrderModel
from delivery_order.const.status import DeliveryStatus
from leg.model import LegModel
from leg.const.status import LegStatus

# 자동 파생이 관여하는 dispatch-phase 상태들
_DISPATCH_PHASE = {DeliveryStatus.PLANNING, DeliveryStatus.DISPATCHING, DeliveryStatus.DISPATCHED}
# 아직 배차 단계인 leg (드라이버 필요)
_ASSIGNABLE = {LegStatus.PENDING, LegStatus.ASSIGNED}


def compute_dispatch_status(legs: list[LegModel]) -> DeliveryStatus:
    """활성 leg 목록 → dispatch-phase 상태."""
    active = [l for l in legs if l.is_active]
    if not active:
        return DeliveryStatus.PLANNING
    unassigned = [l for l in active if l.driver_id is None and l.status in _ASSIGNABLE]
    return DeliveryStatus.DISPATCHING if unassigned else DeliveryStatus.DISPATCHED


async def derive_do_dispatch_state(db: AsyncSession, team_id: int, do_id: int) -> DeliveryStatus | None:
    """D/O 의 dispatch-phase 상태를 leg 기준으로 재계산·저장. 변경된 새 status 반환(없으면 None).

    status_is_manual 컬럼이 없으므로, dispatch-phase 상태일 때만 자동 조정한다.
    """
    do = (await db.execute(select(DeliveryOrderModel).where(
        DeliveryOrderModel.team_id == team_id,
        DeliveryOrderModel.id == do_id,
        DeliveryOrderModel.is_active.is_(True),
    ))).scalar_one_or_none()
    if do is None:
        return None
    if do.is_on_hold or do.cancelled_at is not None:
        return None  # Hold/취소 D/O 는 자동 파생 정지
    if do.status not in _DISPATCH_PHASE:
        return None  # 진행/수동 상태는 건드리지 않음

    legs = list((await db.execute(select(LegModel).where(
        LegModel.team_id == team_id,
        LegModel.delivery_order_id == do_id,
        LegModel.is_active.is_(True),
    ))).scalars().all())

    new_status = compute_dispatch_status(legs)
    if new_status != do.status:
        do.status = new_status
        await db.flush()
        return new_status
    return None
