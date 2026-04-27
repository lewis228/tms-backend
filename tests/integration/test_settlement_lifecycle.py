# tests/integration/test_settlement_lifecycle.py
"""SettlementService.calculate / adjust / approve / unapprove 라이프사이클."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from settlement.const.status import SettlementStatus
from settlement.model import SettlementAuditLogModel, SettlementModel
from settlement.schemas.request import (
    SettlementAdjustRequest, SettlementApproveRequest,
    SettlementCalculateRequest, SettlementUnapproveRequest,
)
from settlement.service import InvalidSettlementTransition, SettlementService

from tests.integration.factories import (
    make_customer, make_delivery_order, make_driver, make_leg, make_settlement,
    make_team,
)


async def _new_settlement(db, *, status=SettlementStatus.PENDING):
    team = await make_team(db)
    customer = await make_customer(db, team=team)
    do = await make_delivery_order(db, team=team, customer=customer)
    driver = await make_driver(db, team=team)
    leg = await make_leg(db, team=team, do=do, driver_id=driver.id)
    s = await make_settlement(db, team=team, leg=leg, settlement_status=status)
    await db.commit()
    return team, s


@pytest.mark.asyncio
async def test_calculate_sets_system_total_and_status(db_session):
    team, s = await _new_settlement(db_session)
    svc = SettlementService(db_session, team.id)
    payload = SettlementCalculateRequest(system_total=Decimal("100.00"), extra_charges=[])

    result = await svc.calculate(s.id, payload)
    assert result.settlement_status == SettlementStatus.CALCULATED
    assert result.system_total == Decimal("100.00")

    # audit log 1건
    rows = (await db_session.execute(
        select(SettlementAuditLogModel).where(SettlementAuditLogModel.settlement_id == s.id)
    )).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_calculate_blocked_after_approve(db_session):
    team, s = await _new_settlement(db_session, status=SettlementStatus.APPROVED)
    svc = SettlementService(db_session, team.id)
    payload = SettlementCalculateRequest(system_total=Decimal("50.00"), extra_charges=[])
    with pytest.raises(InvalidSettlementTransition, match="PENDING/CALCULATED"):
        await svc.calculate(s.id, payload)


@pytest.mark.asyncio
async def test_adjust_requires_calculated(db_session):
    team, s = await _new_settlement(db_session)
    svc = SettlementService(db_session, team.id)
    payload = SettlementAdjustRequest(note="dispute", has_flag=True)
    with pytest.raises(InvalidSettlementTransition):
        await svc.adjust(s.id, payload)


@pytest.mark.asyncio
async def test_approve_then_unapprove(db_session):
    team, s = await _new_settlement(db_session, status=SettlementStatus.CALCULATED)
    s.system_total = Decimal("200.00")
    await db_session.commit()

    svc = SettlementService(db_session, team.id)

    approved = await svc.approve(s.id, SettlementApproveRequest())
    assert approved.settlement_status == SettlementStatus.APPROVED
    assert approved.final_amount == Decimal("200.00")

    unapproved = await svc.unapprove(
        s.id, SettlementUnapproveRequest(reason="customer dispute"),
    )
    assert unapproved.settlement_status == SettlementStatus.ADJUSTED


@pytest.mark.asyncio
async def test_unapprove_requires_approved(db_session):
    team, s = await _new_settlement(db_session, status=SettlementStatus.CALCULATED)
    svc = SettlementService(db_session, team.id)
    with pytest.raises(InvalidSettlementTransition, match="APPROVED"):
        await svc.unapprove(s.id, SettlementUnapproveRequest(reason="oops"))
