# src/leg_layer/charge.py
"""Add-on 기본 단가 산출 — addon 마스터(code) + 기사별 금액 override(addon_driver_rate).

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
    rule = await acc.find_for_code(code)
    if rule is None:
        return None
    # 기사별 금액 override(addon_driver_rate): 행이 있으면 그 amount/percent 가 마스터 기본값을 대체.
    eff_amount, eff_percent = rule.amount, rule.percent
    if driver_id is not None:
        ovr = await acc.get_driver_rate(rule.id, driver_id)
        if ovr is not None:
            if ovr.amount is not None:
                eff_amount = ovr.amount
            if ovr.percent is not None:
                eff_percent = ovr.percent
    if rule.unit == AddonUnit.PERCENT and eff_percent is not None:
        if base_amount is None:
            return None
        return ((base_amount * eff_percent).quantize(_Q), None, Decimal("1"))
    if rule.unit == AddonUnit.MILE and eff_amount is not None and rate_miles is not None:
        return ((eff_amount * rate_miles).quantize(_Q), eff_amount, rate_miles)
    if eff_amount is not None:
        return (eff_amount.quantize(_Q), eff_amount, Decimal("1"))
    return None
