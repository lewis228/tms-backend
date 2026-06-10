# src/leg_layer/charge.py
"""Add-on 기본 단가 산출 — addon 마스터(code + driver override)에서.

컨플루언스 재정의: leg 의 추가요금은 모두 Add-on. 생성 시 시스템이 기본 금액을 채우고,
사용자가 수정/삭제 가능. 단가 출처 = addon 마스터(code 일치, driver override 우선).
"""
from __future__ import annotations
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from addon.repository import AddonRepository
from addon.const.status import AddonUnit

_Q = Decimal("0.01")


async def resolve_addon_amount(
    db: AsyncSession, team_id: int, code: str, *,
    driver_id: int | None = None, rate_miles: Decimal | None = None,
    base_amount: Decimal | None = None,
) -> tuple[Decimal, Decimal | None, Decimal] | None:
    """(amount, unit_amount, quantity) 또는 None.

    - PERCENT(FUEL 등): base_amount × % (base 없으면 None — 정산 시점에 해석)
    - MILE: 단가 × rate_miles
    - FLAT/HOUR/MINUTE/DAY: 정액(quantity 1)
    addon 정의 없으면 None.
    """
    acc = AddonRepository(db, team_id)
    rule = await acc.find_for_code(code, driver_id)
    if rule is None:
        return None
    if rule.unit == AddonUnit.PERCENT and rule.percent is not None:
        if base_amount is None:
            return None
        return ((base_amount * rule.percent).quantize(_Q), None, Decimal("1"))
    if rule.unit == AddonUnit.MILE and rule.amount is not None and rate_miles is not None:
        return ((rule.amount * rate_miles).quantize(_Q), rule.amount, rate_miles)
    if rule.amount is not None:
        return (rule.amount.quantize(_Q), rule.amount, Decimal("1"))
    return None
