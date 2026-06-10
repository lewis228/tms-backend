# tests/integration/test_invoice.py
"""InvoiceService — 고객 인보이스 cost-plus(원가 프리필 + 수동 마크업) (재설계 2c).

요율 미설정 시 원가는 0(UNRESOLVED)이지만, 프리필 라인 구조 / 마진 / lifecycle 은 검증 가능.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from container.model import ContainerModel
from invoice.const.status import InvoiceStatus, InvoiceLineSource
from invoice.service import InvoiceService
from invoice.schemas.request import (
    InvoiceCreateRequest, InvoiceLineCreateRequest, InvoiceLineUpdateRequest,
)
from invoice.state_machine import InvalidInvoiceTransitionError

from tests.integration.factories import (
    make_customer, make_delivery_order, make_team, make_user,
)
from common.exceptions.base import ConflictException


async def _container(db, team, do, *, seq, number=None):
    c = ContainerModel(team_id=team.id, delivery_order_id=do.id, sequence_no=seq,
                       container_number=number)
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return c


@pytest.mark.asyncio
async def test_create_prefills_lines_from_do(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    await _container(db_session, team, do, seq=1, number="MSCU1111111")
    await _container(db_session, team, do, seq=2, number="MSCU2222222")
    await db_session.commit()

    svc = InvoiceService(db_session, team.id)
    inv = await svc.create(
        InvoiceCreateRequest(customer_id=customer.id, delivery_order_id=do.id),
        actor_user_id=user.id,
    )

    assert inv.status == InvoiceStatus.DRAFT
    assert len(inv.lines) == 2          # 컨테이너당 1라인 프리필
    assert all(l.source == InvoiceLineSource.PREFILL for l in inv.lines)
    assert "MSCU1111111" in inv.lines[0].description
    # 요율 미설정 → 원가 0
    assert inv.cost_total == Decimal("0")
    assert inv.margin == inv.charge_total - inv.cost_total


@pytest.mark.asyncio
async def test_manual_line_updates_charge_and_margin(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    user = await make_user(db_session)
    await db_session.commit()

    svc = InvoiceService(db_session, team.id)
    inv = await svc.create(InvoiceCreateRequest(customer_id=customer.id), actor_user_id=user.id)
    assert inv.charge_total == Decimal("0")

    inv = await svc.add_line(inv.id, InvoiceLineCreateRequest(
        description="Drayage", quantity=Decimal("2"), unit_amount=Decimal("500"),
    ), actor_user_id=user.id)
    assert inv.charge_total == Decimal("1000.00")     # 2 × 500
    assert inv.margin == Decimal("1000.00")           # cost 0

    line_id = inv.lines[0].id
    inv = await svc.add_line(inv.id, InvoiceLineCreateRequest(
        description="Fuel", unit_amount=Decimal("120"),
    ), actor_user_id=user.id)
    assert inv.charge_total == Decimal("1120.00")

    # 수정 → 재계산
    inv = await svc.update_line(inv.id, line_id, InvoiceLineUpdateRequest(
        unit_amount=Decimal("600"),
    ), actor_user_id=user.id)
    assert inv.charge_total == Decimal("1320.00")     # 2×600 + 120

    # 삭제 → 재계산
    inv = await svc.delete_line(inv.id, line_id, actor_user_id=user.id)
    assert inv.charge_total == Decimal("120.00")


@pytest.mark.asyncio
async def test_lifecycle_and_edit_lock(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    user = await make_user(db_session)
    await db_session.commit()

    svc = InvoiceService(db_session, team.id)
    inv = await svc.create(InvoiceCreateRequest(customer_id=customer.id), actor_user_id=user.id)

    inv = await svc.transition(inv.id, InvoiceStatus.ISSUED, actor_user_id=user.id)
    assert inv.status == InvoiceStatus.ISSUED

    # ISSUED 에서는 라인 편집 차단
    with pytest.raises(ConflictException, match="DRAFT"):
        await svc.add_line(inv.id, InvoiceLineCreateRequest(
            description="X", unit_amount=Decimal("1"),
        ), actor_user_id=user.id)

    inv = await svc.transition(inv.id, InvoiceStatus.PAID, actor_user_id=user.id)
    assert inv.status == InvoiceStatus.PAID

    # PAID → ISSUED 불가
    with pytest.raises(InvalidInvoiceTransitionError):
        await svc.transition(inv.id, InvoiceStatus.ISSUED, actor_user_id=user.id)


@pytest.mark.asyncio
async def test_cost_prefill_includes_leg_flags(db_session):
    """컨플루언스: 고객 청구 원가도 leg 단위 Flag(Add-on)를 합산한다."""
    from datetime import datetime, timezone
    from addon.model import AddonModel
    from addon.const.status import AddonCategory, AddonUnit
    from leg_layer.model import LegAddonModel
    from leg.const.status import LegStatus
    from tests.integration.factories import make_driver, make_leg

    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    user = await make_user(db_session)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    container = await _container(db_session, team, do, seq=1, number="MSCU9999999")
    driver = await make_driver(db_session, team=team)
    leg = await make_leg(
        db_session, team=team, do=do, driver_id=driver.id,
        status=LegStatus.COMPLETED, container_id=container.id,
        completed_at=datetime(2026, 5, 9, 10, tzinfo=timezone.utc),
    )
    db_session.add(AddonModel(
        team_id=team.id, code="NGT", name="Night Gate",
        category=AddonCategory.NIGHT_GATE, unit=AddonUnit.FLAT, amount=Decimal("50"),
    ))
    db_session.add(LegAddonModel(team_id=team.id, leg_id=leg.id, code="NGT"))
    await db_session.commit()

    svc = InvoiceService(db_session, team.id)
    inv = await svc.create(
        InvoiceCreateRequest(customer_id=customer.id, delivery_order_id=do.id),
        actor_user_id=user.id,
    )
    # 요율 미설정이라 base=0, flag $50 → 컨테이너 원가 = $50
    assert inv.cost_total == Decimal("50.00")


@pytest.mark.asyncio
async def test_do_addon_billed_on_invoice(db_session):
    """컨플루언스: D/O 단위 Add-on(Demurrage 등) → 고객 청구 라인 자동 가산."""
    from delivery_order.model import DeliveryOrderAddonModel

    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    user = await make_user(db_session)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    await _container(db_session, team, do, seq=1, number="MSCU1010101")
    db_session.add(DeliveryOrderAddonModel(
        team_id=team.id, delivery_order_id=do.id, code="DMR", amount=Decimal("300"),
    ))
    await db_session.commit()

    svc = InvoiceService(db_session, team.id)
    inv = await svc.create(
        InvoiceCreateRequest(customer_id=customer.id, delivery_order_id=do.id),
        actor_user_id=user.id,
    )
    dmr = [l for l in inv.lines if "DMR" in (l.description or "")]
    assert len(dmr) == 1
    assert dmr[0].amount == Decimal("300.00")
    assert inv.cost_total == Decimal("300.00")   # 컨테이너 원가 0 + D/O addon 300


@pytest.mark.asyncio
async def test_void_from_draft(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    user = await make_user(db_session)
    await db_session.commit()

    svc = InvoiceService(db_session, team.id)
    inv = await svc.create(InvoiceCreateRequest(customer_id=customer.id), actor_user_id=user.id)
    inv = await svc.transition(inv.id, InvoiceStatus.VOID, actor_user_id=user.id)
    assert inv.status == InvoiceStatus.VOID
