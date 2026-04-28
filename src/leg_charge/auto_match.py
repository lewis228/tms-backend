# src/leg_charge/auto_match.py
"""H-7 자동 정산 엔진.

leg.completed 시 호출되어:
  1. rate_card 매칭 (specific 우선) → BASE_LINEHAUL leg_charge 자동 생성
  2. chassis_event PICKED_UP / RETURNED_TO_POOL 시간차 → CHASSIS_PER_DIEM 자동 산출
  3. leg_stop(WAIT) arrived/departed 차이 → WAIT_PER_MIN 자동 산출
  4. payee/payer 자동 채움 (driver/customer/pool/company 분리)

설계 원칙:
- 같은 leg + 같은 charge_code + source=AUTO 가 이미 있으면 skip (중복 방지)
- Manifest 의 한 줄 = leg 1건 = base + accessorials line 들
"""
from __future__ import annotations
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from charge_code.const.status import ChargeKind, ChargeUnit, ChargeSource, PartyKind
from charge_code.model import ChargeCodeModel
from chassis_event.model import ChassisEventModel
from chassis.model import ChassisModel
from chassis.const.status import ChassisOwnerKind
from container.model import ContainerModel
from delivery_order.model import DeliveryOrderModel
from driver.model import DriverModel
from driver.const.status import EmploymentKind
from leg.model import LegModel
from leg_charge.model import LegChargeModel
from leg_stop.model import LegStopModel
from leg.const.status import StopKind
from rate_card.model import RateCardModel


async def _match_rate_card(
    db: AsyncSession, team_id: int, charge_code_id: int,
    customer_id: Optional[int], terminal_id: Optional[int], size: Optional[str],
) -> Optional[RateCardModel]:
    """우선순위 큰 (specific) rate_card 가 우선. NULL scope 는 wildcard."""
    q = (
        select(RateCardModel)
        .where(
            RateCardModel.team_id == team_id,
            RateCardModel.charge_code_id == charge_code_id,
            RateCardModel.is_active.is_(True),
        )
        .order_by(RateCardModel.priority.desc(), RateCardModel.id.desc())
    )
    rows = list((await db.execute(q)).scalars().all())
    for r in rows:
        if r.scope_customer_id and r.scope_customer_id != customer_id:
            continue
        if r.scope_terminal_id and r.scope_terminal_id != terminal_id:
            continue
        if r.scope_size and r.scope_size.value != size:
            continue
        return r
    return None


async def _get_charge_code(
    db: AsyncSession, team_id: int, code: str,
) -> Optional[ChargeCodeModel]:
    q = select(ChargeCodeModel).where(
        ChargeCodeModel.team_id == team_id,
        ChargeCodeModel.code == code,
        ChargeCodeModel.is_active.is_(True),
    )
    return (await db.execute(q)).scalar_one_or_none()


async def _existing_auto_charge(
    db: AsyncSession, team_id: int, leg_id: int, charge_code_id: int,
) -> Optional[LegChargeModel]:
    q = select(LegChargeModel).where(
        LegChargeModel.team_id == team_id,
        LegChargeModel.leg_id == leg_id,
        LegChargeModel.charge_code_id == charge_code_id,
        LegChargeModel.source.in_([ChargeSource.AUTO, ChargeSource.EVENT]),
        LegChargeModel.is_active.is_(True),
    )
    return (await db.execute(q)).scalar_one_or_none()


async def auto_match_for_leg(
    db: AsyncSession, team_id: int, leg_id: int,
    actor_user_id: Optional[int] = None,
) -> List[LegChargeModel]:
    """leg 1건의 자동 charge 생성 (BASE + accessorial AUTO/EVENT). 기존 AUTO 는 skip."""
    leg = (await db.execute(
        select(LegModel).where(
            LegModel.team_id == team_id,
            LegModel.id == leg_id,
            LegModel.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if not leg:
        return []

    do = (await db.execute(
        select(DeliveryOrderModel).where(
            DeliveryOrderModel.team_id == team_id,
            DeliveryOrderModel.id == leg.delivery_order_id,
        )
    )).scalar_one_or_none()
    customer_id = do.customer_id if do else None
    terminal_id = do.terminal_id if do else None

    container = None
    if leg.container_id:
        container = (await db.execute(
            select(ContainerModel).where(
                ContainerModel.team_id == team_id,
                ContainerModel.id == leg.container_id,
            )
        )).scalar_one_or_none()
    size_value = container.size.value if container and container.size else None

    driver = None
    if leg.driver_id:
        driver = (await db.execute(
            select(DriverModel).where(
                DriverModel.team_id == team_id,
                DriverModel.id == leg.driver_id,
            )
        )).scalar_one_or_none()

    created: List[LegChargeModel] = []

    # ── 1) BASE_LINEHAUL ──
    base_code = await _get_charge_code(db, team_id, "BASE_LINEHAUL")
    if base_code and not await _existing_auto_charge(db, team_id, leg.id, base_code.id):
        rc = await _match_rate_card(
            db, team_id, base_code.id,
            customer_id=customer_id, terminal_id=terminal_id, size=size_value,
        )
        amount = (
            rc.amount if rc and rc.amount is not None
            else base_code.default_amount or Decimal("0")
        )
        # Payee: driver (운임은 기사한테 지급), Payer: customer (D/O 발급자)
        payee_kind: Optional[PartyKind] = None
        payee_driver_id: Optional[int] = None
        if driver:
            if driver.employment_kind == EmploymentKind.CARRIER_DRIVER:
                payee_kind = PartyKind.CARRIER
            else:
                payee_kind = PartyKind.DRIVER
                payee_driver_id = driver.id
        charge = LegChargeModel(
            team_id=team_id, leg_id=leg.id,
            charge_code_id=base_code.id,
            rate_card_id=rc.id if rc else None,
            amount=amount,
            unit=ChargeUnit.FLAT,
            source=ChargeSource.AUTO,
            description=f"AUTO BASE_LINEHAUL (rate_card={rc.id if rc else 'default'})",
            payer_kind=PartyKind.CUSTOMER,
            payer_partner_id=customer_id,
            payee_kind=payee_kind,
            payee_driver_id=payee_driver_id,
            created_by_user_id=actor_user_id,
        )
        db.add(charge)
        await db.flush()
        await db.refresh(charge)
        created.append(charge)

    # ── 2) CHASSIS_PER_DIEM (chassis_event 시간차) ──
    cpd_code = await _get_charge_code(db, team_id, "CHASSIS_PER_DIEM")
    if cpd_code and leg.chassis_id and not await _existing_auto_charge(db, team_id, leg.id, cpd_code.id):
        chassis = (await db.execute(
            select(ChassisModel).where(
                ChassisModel.team_id == team_id,
                ChassisModel.id == leg.chassis_id,
            )
        )).scalar_one_or_none()
        # 풀 챠시일 때만 per-diem 비용 발생
        if chassis and chassis.owner_kind in (
            ChassisOwnerKind.TERMINAL_POOL, ChassisOwnerKind.THIRD_PARTY_POOL,
        ):
            ev_q = (
                select(ChassisEventModel)
                .where(
                    ChassisEventModel.team_id == team_id,
                    ChassisEventModel.chassis_id == chassis.id,
                    ChassisEventModel.is_active.is_(True),
                )
                .order_by(ChassisEventModel.occurred_at.asc())
            )
            events = list((await db.execute(ev_q)).scalars().all())
            picked = next((e for e in events if e.event_kind.value == "PICKED_UP"), None)
            returned = next((e for e in events if e.event_kind.value in ("RETURNED_TO_POOL", "RETURNED_TO_TERMINAL")), None)
            if picked and returned and returned.occurred_at > picked.occurred_at:
                days = max(
                    1,
                    int((returned.occurred_at - picked.occurred_at).total_seconds() / 86400) + 1,
                )
                per_unit = cpd_code.default_amount or Decimal("35.00")
                total = per_unit * Decimal(days)
                charge = LegChargeModel(
                    team_id=team_id, leg_id=leg.id,
                    charge_code_id=cpd_code.id,
                    amount=total,
                    quantity=Decimal(days),
                    unit=ChargeUnit.DAY,
                    source=ChargeSource.EVENT,
                    description=f"AUTO CHASSIS_PER_DIEM ({days}d)",
                    payer_kind=PartyKind.COMPANY,
                    payee_kind=PartyKind.POOL,
                    payee_pool_id=chassis.owner_pool_id,
                    created_by_user_id=actor_user_id,
                )
                db.add(charge)
                await db.flush()
                await db.refresh(charge)
                created.append(charge)

    # ── 3) WAIT_PER_MIN (leg_stop WAIT 의 arrived/departed 차이) ──
    wait_code = await _get_charge_code(db, team_id, "WAIT_PER_MIN")
    if wait_code and not await _existing_auto_charge(db, team_id, leg.id, wait_code.id):
        stops = list((await db.execute(
            select(LegStopModel).where(
                LegStopModel.team_id == team_id,
                LegStopModel.leg_id == leg.id,
                LegStopModel.stop_kind == StopKind.WAIT,
                LegStopModel.is_active.is_(True),
            )
        )).scalars().all())
        total_min = 0
        for s in stops:
            if s.arrived_at and s.departed_at and s.departed_at > s.arrived_at:
                total_min += int((s.departed_at - s.arrived_at).total_seconds() / 60)
        if total_min > 0:
            per_min = wait_code.default_amount or Decimal("1.50")
            total = per_min * Decimal(total_min)
            charge = LegChargeModel(
                team_id=team_id, leg_id=leg.id,
                charge_code_id=wait_code.id,
                amount=total,
                quantity=Decimal(total_min),
                unit=ChargeUnit.MINUTE,
                source=ChargeSource.EVENT,
                description=f"AUTO WAIT_PER_MIN ({total_min}min)",
                payer_kind=PartyKind.CUSTOMER,
                payer_partner_id=customer_id,
                payee_kind=(
                    PartyKind.DRIVER if driver and driver.employment_kind != EmploymentKind.CARRIER_DRIVER
                    else (PartyKind.CARRIER if driver else None)
                ),
                payee_driver_id=(
                    driver.id if driver and driver.employment_kind != EmploymentKind.CARRIER_DRIVER else None
                ),
                created_by_user_id=actor_user_id,
            )
            db.add(charge)
            await db.flush()
            await db.refresh(charge)
            created.append(charge)

    return created
