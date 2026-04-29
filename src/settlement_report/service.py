# src/settlement_report/service.py
"""v3 정산 리포트 — driver 별 LegRate base + LegCharge subtotal 합산.

기간 + driver 선택 → driver_id 별 leg 단위 정산 라인 + 총액 응답.
PDF 생성은 프론트에서 처리 (BE 는 JSON 만).
"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from leg.model import LegModel
from leg.const.status import LegStatus
from leg_rate.model import LegRateModel
from leg_charge.model import LegChargeModel
from charge_code.model import ChargeCodeModel
from driver.model import DriverModel
from user.model import UserModel
from container.model import ContainerModel
from delivery_order.model import DeliveryOrderModel


async def driver_settlement_report(
    db: AsyncSession,
    team_id: int,
    *,
    driver_id: int,
    completed_from: datetime,
    completed_to: datetime,
) -> dict[str, Any]:
    """단일 driver 의 기간 내 leg 정산 합계.

    Returns:
        {
          "driver": {"id", "name"},
          "period": {"from", "to"},
          "legs": [{leg_id, container_no, bl_number, base_amount, charges_total, total, ...}],
          "summary": {"base_total", "charges_total", "grand_total", "leg_count"}
        }
    """
    # Driver 메타
    driver_row = (await db.execute(
        select(DriverModel.id, UserModel.name, UserModel.email)
        .outerjoin(UserModel, UserModel.id == DriverModel.user_id)
        .where(DriverModel.team_id == team_id, DriverModel.id == driver_id)
    )).first()
    driver_name = (
        driver_row.name or driver_row.email
        if driver_row else f"#{driver_id}"
    )

    # 1) LegRate 가 이 driver 에게 귀속된 COMPLETED leg
    legs_q = (
        select(LegModel, LegRateModel, ContainerModel, DeliveryOrderModel)
        .join(LegRateModel, and_(
            LegRateModel.leg_id == LegModel.id,
            LegRateModel.team_id == team_id,
            LegRateModel.is_active.is_(True),
        ))
        .outerjoin(ContainerModel, ContainerModel.id == LegModel.container_id)
        .outerjoin(DeliveryOrderModel, DeliveryOrderModel.id == LegModel.delivery_order_id)
        .where(
            LegModel.team_id == team_id,
            LegModel.is_active.is_(True),
            LegModel.status == LegStatus.COMPLETED,
            LegModel.completed_at >= completed_from,
            LegModel.completed_at <= completed_to,
            LegRateModel.payee_driver_id == driver_id,
        )
        .order_by(LegModel.completed_at.asc())
    )
    leg_rows = (await db.execute(legs_q)).all()

    # 2) 각 leg 의 LegCharge — driver 귀속 라인만
    legs_payload: list[dict[str, Any]] = []
    base_total = Decimal("0")
    charges_total = Decimal("0")

    for leg, rate, container, do in leg_rows:
        # driver 에게 귀속된 charge (payee_driver_id == driver_id) 만 합산
        charge_rows = (await db.execute(
            select(LegChargeModel, ChargeCodeModel.code, ChargeCodeModel.name)
            .outerjoin(ChargeCodeModel, ChargeCodeModel.id == LegChargeModel.charge_code_id)
            .where(
                LegChargeModel.team_id == team_id,
                LegChargeModel.leg_id == leg.id,
                LegChargeModel.is_active.is_(True),
                LegChargeModel.payee_driver_id == driver_id,
            )
        )).all()
        leg_charges_subtotal = Decimal("0")
        charge_lines: list[dict[str, Any]] = []
        for lc, cc_code, cc_name in charge_rows:
            leg_charges_subtotal += lc.amount or Decimal("0")
            charge_lines.append({
                "id": lc.id,
                "code": cc_code,
                "name": cc_name,
                "quantity": str(lc.quantity) if lc.quantity is not None else None,
                "unit_amount": str(lc.snapshot_unit_amount) if lc.snapshot_unit_amount is not None else None,
                "subtotal": str(lc.amount or 0),
                "description": lc.description,
            })

        leg_total = (rate.base_amount or Decimal("0")) + leg_charges_subtotal
        base_total += rate.base_amount or Decimal("0")
        charges_total += leg_charges_subtotal

        legs_payload.append({
            "leg_id": leg.id,
            "completed_at": leg.completed_at.isoformat() if leg.completed_at else None,
            "container_no": container.container_number if container else None,
            "bl_number": do.bl_number if do else None,
            "base_amount": str(rate.base_amount or 0),
            "rate_source": rate.source.value,
            "charges": charge_lines,
            "charges_total": str(leg_charges_subtotal),
            "total": str(leg_total),
        })

    return {
        "driver": {"id": driver_id, "name": driver_name},
        "period": {
            "from": completed_from.isoformat(),
            "to": completed_to.isoformat(),
        },
        "legs": legs_payload,
        "summary": {
            "leg_count": len(legs_payload),
            "base_total": str(base_total),
            "charges_total": str(charges_total),
            "grand_total": str(base_total + charges_total),
        },
    }
