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
    make_tenant,
)


async def _new_settlement(db, *, status=SettlementStatus.PENDING):
    tenant = await make_tenant(db)
    customer = await make_customer(db, tenant=tenant)
    do = await make_delivery_order(db, tenant=tenant, customer=customer)
    driver = await make_driver(db, tenant=tenant)
    leg = await make_leg(db, tenant=tenant, do=do, driver_id=driver.id)
    s = await make_settlement(db, tenant=tenant, leg=leg, settlement_status=status)
    await db.commit()
    return tenant, s


@pytest.mark.asyncio
async def test_calculate_sets_system_total_and_status(db_session):
    tenant, s = await _new_settlement(db_session)
    svc = SettlementService(db_session, tenant.id)
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
    tenant, s = await _new_settlement(db_session, status=SettlementStatus.APPROVED)
    svc = SettlementService(db_session, tenant.id)
    payload = SettlementCalculateRequest(system_total=Decimal("50.00"), extra_charges=[])
    with pytest.raises(InvalidSettlementTransition, match="PENDING/CALCULATED"):
        await svc.calculate(s.id, payload)


@pytest.mark.asyncio
async def test_adjust_requires_calculated(db_session):
    tenant, s = await _new_settlement(db_session)
    svc = SettlementService(db_session, tenant.id)
    payload = SettlementAdjustRequest(note="dispute", has_flag=True)
    with pytest.raises(InvalidSettlementTransition):
        await svc.adjust(s.id, payload)


@pytest.mark.asyncio
async def test_approve_then_unapprove(db_session):
    tenant, s = await _new_settlement(db_session, status=SettlementStatus.CALCULATED)
    s.system_total = Decimal("200.00")
    await db_session.commit()

    svc = SettlementService(db_session, tenant.id)

    approved = await svc.approve(s.id, SettlementApproveRequest())
    assert approved.settlement_status == SettlementStatus.APPROVED
    assert approved.final_amount == Decimal("200.00")

    unapproved = await svc.unapprove(
        s.id, SettlementUnapproveRequest(reason="customer dispute"),
    )
    assert unapproved.settlement_status == SettlementStatus.ADJUSTED


@pytest.mark.asyncio
async def test_unapprove_requires_approved(db_session):
    tenant, s = await _new_settlement(db_session, status=SettlementStatus.CALCULATED)
    svc = SettlementService(db_session, tenant.id)
    with pytest.raises(InvalidSettlementTransition, match="APPROVED"):
        await svc.unapprove(s.id, SettlementUnapproveRequest(reason="oops"))
