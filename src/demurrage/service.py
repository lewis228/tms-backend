# src/demurrage/service.py
"""Demurrage / Detention 자동 카운터.

규칙 (v3):
  - container.demurrage_lfd 가 오늘보다 과거이면, 활성 leg 가 있는 한 매일 1건 LegCharge 자동 적용.
  - ChargeCode "DEMURRAGE_PER_DAY" 가 마스터에 등록되어 있어야 함.
  - 같은 leg + 같은 날짜에 중복 적용 안 되도록 description 에 "DEMURRAGE day=YYYY-MM-DD" 박음.

수동 호출:
  POST /api/v1/demurrage/run-daily  (운영자 또는 cron)
  → 모든 team 의 모든 컨테이너를 한 번 스캔해서 적용.

향후 cron job 으로 자동화 (apscheduler 또는 외부 cron + endpoint 호출).
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from charge_code.const.status import ChargeSource, PartyKind
from charge_code.model import ChargeCodeModel
from container.model import ContainerModel
from leg.model import LegModel
from leg.const.status import LegStatus
from leg_charge.model import LegChargeModel


DEMURRAGE_CODE = "DEMURRAGE_PER_DAY"
DETENTION_CODE = "DETENTION_PER_DAY"


async def apply_daily_charges(db: AsyncSession, team_id: int) -> dict:
    """team 단위로 demurrage/detention 자동 적용.

    Returns:
        {"demurrage_added": N, "detention_added": M, "skipped": K}
    """
    today = date.today()

    # 1) ChargeCode lookup (없으면 skip)
    codes = (await db.execute(
        select(ChargeCodeModel).where(
            ChargeCodeModel.team_id == team_id,
            ChargeCodeModel.code.in_([DEMURRAGE_CODE, DETENTION_CODE]),
            ChargeCodeModel.is_active.is_(True),
        )
    )).scalars().all()
    code_by_key = {c.code: c for c in codes}

    demurrage_added = 0
    detention_added = 0
    skipped = 0

    # 2) 활성 컨테이너 조회 (LFD 지난 것만)
    containers = (await db.execute(
        select(ContainerModel).where(
            ContainerModel.team_id == team_id,
            ContainerModel.is_active.is_(True),
        )
    )).scalars().all()

    for c in containers:
        # 활성 leg 가 있어야 적용 (이미 종료된 컨테이너 무시)
        active_legs = (await db.execute(
            select(LegModel).where(
                LegModel.team_id == team_id,
                LegModel.container_id == c.id,
                LegModel.is_active.is_(True),
                LegModel.status.in_([LegStatus.PENDING, LegStatus.IN_TRANSIT]),
            ).limit(1)
        )).scalars().first()
        if active_legs is None:
            continue

        # Demurrage
        cc = code_by_key.get(DEMURRAGE_CODE)
        if c.demurrage_lfd and c.demurrage_lfd < today and cc is not None:
            tag = f"DEMURRAGE day={today.isoformat()}"
            already = (await db.execute(
                select(LegChargeModel.id).where(
                    LegChargeModel.team_id == team_id,
                    LegChargeModel.leg_id == active_legs.id,
                    LegChargeModel.charge_code_id == cc.id,
                    LegChargeModel.description == tag,
                ).limit(1)
            )).first()
            if already is None:
                qty = Decimal("1")
                unit = cc.default_amount or Decimal("0")
                db.add(LegChargeModel(
                    team_id=team_id,
                    leg_id=active_legs.id,
                    charge_code_id=cc.id,
                    snapshot_unit_amount=unit,
                    quantity=qty,
                    amount=unit * qty,
                    source=ChargeSource.AUTO,
                    payer_kind=PartyKind.CUSTOMER,
                    description=tag,
                ))
                demurrage_added += 1
            else:
                skipped += 1

        # Detention
        cd = code_by_key.get(DETENTION_CODE)
        if c.detention_lfd and c.detention_lfd < today and cd is not None:
            tag = f"DETENTION day={today.isoformat()}"
            already = (await db.execute(
                select(LegChargeModel.id).where(
                    LegChargeModel.team_id == team_id,
                    LegChargeModel.leg_id == active_legs.id,
                    LegChargeModel.charge_code_id == cd.id,
                    LegChargeModel.description == tag,
                ).limit(1)
            )).first()
            if already is None:
                qty = Decimal("1")
                unit = cd.default_amount or Decimal("0")
                db.add(LegChargeModel(
                    team_id=team_id,
                    leg_id=active_legs.id,
                    charge_code_id=cd.id,
                    snapshot_unit_amount=unit,
                    quantity=qty,
                    amount=unit * qty,
                    source=ChargeSource.AUTO,
                    payer_kind=PartyKind.CUSTOMER,
                    description=tag,
                ))
                detention_added += 1
            else:
                skipped += 1

    if demurrage_added or detention_added:
        await db.flush()
    _ = datetime.now(timezone.utc)
    return {
        "demurrage_added": demurrage_added,
        "detention_added": detention_added,
        "skipped": skipped,
    }
