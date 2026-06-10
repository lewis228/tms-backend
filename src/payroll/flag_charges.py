# src/payroll/flag_charges.py
"""Leg Add-on → 정산/청구 charge 합산.

컨플루언스 재정의(2026-06-10): Layer 1/2/3 폐기. leg 의 추가요금은 모두 **Add-on** 한 개념
(같은 code 중복 가능, 예: Stop Off ×3). 시스템이 생성 시 기본 금액을 채우고 사용자가 수정/삭제.
정산/청구는 leg 에 **저장된 add-on 금액을 합산**한다(저장값 우선, 미설정이면 마스터 단가로 해석).
"""
from __future__ import annotations
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from leg_layer.repository import LegLayerRepository
from leg_layer.charge import resolve_addon_amount

_D0 = Decimal("0")


async def collect_leg_flag_charges(
    db: AsyncSession, team_id: int, leg, *, base_amount: Decimal,
    channel: str = "payroll",
) -> list[dict]:
    """leg 의 add-on → charge dict 목록 (정산/청구 공용).

    dict = {code, addon_id, snapshot_unit_amount, quantity, amount, note}
    저장 amount(>0) 우선. 미설정이면 addon 마스터 단가로 해석(PERCENT 는 base 사용).

    channel="payroll" → is_payable_to_driver 인 add-on 만(기사 정산).
    channel="invoice" → is_billable_to_customer 인 add-on 만(고객 청구).
    플래그는 부착 시점 스냅샷(leg_addon 행)이라 마스터 변경이 과거 기록에 영향 없음.
    """
    layer = LegLayerRepository(db, team_id)
    out: list[dict] = []
    for a in await layer.list_addons(leg.id):
        if channel == "invoice":
            if not a.is_billable_to_customer:
                continue
        elif not a.is_payable_to_driver:
            continue
        code = a.code  # leg_addon.code 는 addon.code 스냅샷(String)
        stored = a.amount if (a.amount is not None and a.amount != _D0) else (a.amount_override or _D0)
        if stored != _D0:
            amount, unit, qty = stored, a.unit_amount, (a.quantity or Decimal("1"))
        else:
            filled = await resolve_addon_amount(
                db, team_id, code,
                driver_id=leg.driver_id, rate_miles=leg.rate_miles, base_amount=base_amount,
            )
            if filled is None:
                continue
            amount, unit, qty = filled
        if amount == _D0:
            continue
        out.append({
            "code": code, "addon_id": a.addon_id,
            "snapshot_unit_amount": unit, "quantity": qty, "amount": amount,
            "note": f"leg #{leg.id} {code}",
        })
    return out
