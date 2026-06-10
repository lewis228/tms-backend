# src/invoice/cost.py
"""D/O 기사 원가 집계 (재설계 2c) — 인보이스 cost-plus 의 '원가' 축.

payroll 과 동일한 RateResolver(resolve_leg_rate) 로 그 D/O 의 COMPLETED leg base 를 합산한다.
컨테이너별 원가를 내서 라인 프리필에 사용. payroll 빌드 여부와 무관하게 계산.
"""
from __future__ import annotations
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leg.model import LegModel
from leg.const.status import LegStatus
from payroll.resolve import resolve_leg_rate
from payroll.flag_charges import collect_leg_flag_charges


async def compute_do_cost(db: AsyncSession, team_id: int, do_id: int) -> tuple[Decimal, dict[int | None, Decimal]]:
    """D/O 의 COMPLETED leg 원가 합계 + 컨테이너별 원가 맵 반환.

    각 leg 원가 = 기본료(RateResolver base) + leg 단위 Flag(Add-on/Charge Event/Stop Off) 합산.
    컨플루언스: 고객 청구 원가도 leg 의 3-Layer 를 다 합산(기사 정산과 같은 요금줄, cost-plus 의 cost 축).
    returns (total_cost, {container_id: cost}) — container_id None 은 컨테이너 미지정 leg.
    """
    legs = list((await db.execute(select(LegModel).where(
        LegModel.team_id == team_id,
        LegModel.delivery_order_id == do_id,
        LegModel.is_active.is_(True),
        LegModel.status == LegStatus.COMPLETED,
    ))).scalars().all())

    total = Decimal("0")
    by_container: dict[int | None, Decimal] = {}
    for leg in legs:
        res = await resolve_leg_rate(db, team_id, leg)
        base = res.base_amount if (res.found and res.base_amount is not None) else Decimal("0")
        leg_cost = base
        for ch in await collect_leg_flag_charges(db, team_id, leg, base_amount=base):
            leg_cost += ch["amount"]
        total += leg_cost
        by_container[leg.container_id] = by_container.get(leg.container_id, Decimal("0")) + leg_cost
    return total, by_container
