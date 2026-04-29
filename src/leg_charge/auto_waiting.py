# src/leg_charge/auto_waiting.py
"""leg 완료 시점에 stop 의 arrival/departure 차이로 WAITING 자동 LegCharge.

규칙 (v3):
  - leg.status = COMPLETED 로 전환되는 시점에 호출.
  - leg.from_stop / to_stop 의 arrived_at / departed_at 으로 *대기 시간(분)* 계산.
  - ChargeCode "WAITING_10MIN" 가 마스터에 있으면 quantity = ceil(분 / 10) 로 자동 LegCharge.
  - 같은 leg + 같은 source AUTO + 같은 charge_code 가 이미 있으면 skip (중복 방지).

UNIT TEST: tests/unit/test_v3_policies.py 의 LegCharge 자동 amount 계산 테스트로 산식 검증.
"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from math import ceil

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from charge_code.const.status import ChargeSource, PartyKind
from charge_code.model import ChargeCodeModel
from container_stop.model import ContainerStopModel
from leg.model import LegModel
from leg_charge.model import LegChargeModel


WAITING_CODE = "WAITING_10MIN"
WAITING_BUCKET_MIN = 10


def _diff_min(arrived: datetime | None, departed: datetime | None) -> int:
    if arrived is None or departed is None:
        return 0
    delta = departed - arrived
    return max(0, int(delta.total_seconds() // 60))


async def auto_waiting_on_complete(
    db: AsyncSession,
    team_id: int,
    leg_id: int,
) -> int:
    """leg 의 양 끝 stop 에서 대기 시간 합산 → WAITING_10MIN qty 자동 LegCharge.

    Returns:
        생성된 LegCharge row 수.
    """
    leg = (await db.execute(
        select(LegModel).where(
            LegModel.team_id == team_id,
            LegModel.id == leg_id,
            LegModel.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if leg is None or leg.from_stop_id is None or leg.to_stop_id is None:
        return 0

    cc = (await db.execute(
        select(ChargeCodeModel).where(
            ChargeCodeModel.team_id == team_id,
            ChargeCodeModel.code == WAITING_CODE,
            ChargeCodeModel.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if cc is None:
        return 0

    stops = (await db.execute(
        select(ContainerStopModel).where(
            ContainerStopModel.team_id == team_id,
            ContainerStopModel.id.in_([leg.from_stop_id, leg.to_stop_id]),
            ContainerStopModel.is_active.is_(True),
        )
    )).scalars().all()
    by_id = {s.id: s for s in stops}
    from_stop = by_id.get(leg.from_stop_id)
    to_stop = by_id.get(leg.to_stop_id)
    if from_stop is None or to_stop is None:
        return 0

    total_min = (
        _diff_min(from_stop.actual_arrival, from_stop.actual_departure)
        + _diff_min(to_stop.actual_arrival, to_stop.actual_departure)
    )
    if total_min <= 0:
        return 0

    qty_buckets = ceil(total_min / WAITING_BUCKET_MIN)
    if qty_buckets <= 0:
        return 0

    # 중복 방지 — 동일 leg + 동일 charge_code + AUTO 가 이미 있으면 skip
    existing = (await db.execute(
        select(LegChargeModel.id).where(
            LegChargeModel.team_id == team_id,
            LegChargeModel.leg_id == leg_id,
            LegChargeModel.charge_code_id == cc.id,
            LegChargeModel.source == ChargeSource.AUTO,
            LegChargeModel.is_active.is_(True),
        ).limit(1)
    )).first()
    if existing is not None:
        return 0

    unit = cc.default_amount or Decimal("0")
    qty = Decimal(qty_buckets)
    db.add(LegChargeModel(
        team_id=team_id,
        leg_id=leg_id,
        charge_code_id=cc.id,
        snapshot_unit_amount=unit,
        quantity=qty,
        amount=unit * qty,
        source=ChargeSource.AUTO,
        payee_kind=PartyKind.DRIVER,
        payee_driver_id=leg.driver_id,
        description=f"AUTO WAITING — total {total_min} min ({qty_buckets} × {WAITING_BUCKET_MIN}min buckets)",
    ))
    await db.flush()
    return 1
