# tests/integration/test_payroll_period.py
"""PayrollService.build_period + period_summary + bi-weekly 기간 계산 (재설계 2c).

요율 미설정이어도 COMPLETED leg 는 UNRESOLVED(base 0) 라인으로 정산에 들어간다 →
집계/일괄생성 로직만 독립 검증.
"""
from __future__ import annotations

from datetime import datetime, date, timezone
from decimal import Decimal

import pytest

from leg.const.status import LegStatus
from payroll.periods import biweekly_period, next_period, period_index
from payroll.schemas.request import PayrollBuildPeriodRequest, PayrollBuildRequest
from payroll.service import PayrollService

from tests.integration.factories import (
    make_customer, make_delivery_order, make_driver, make_leg, make_team, make_user,
)

_PERIOD_START = date(2026, 5, 4)   # 격주 기간 예시
_PERIOD_END = date(2026, 5, 17)


def test_biweekly_period_math():
    s, e = biweekly_period(date(2024, 1, 20))
    assert (s, e) == (date(2024, 1, 15), date(2024, 1, 28))
    assert next_period(s) == (date(2024, 1, 29), date(2024, 2, 11))
    assert period_index(date(2024, 1, 1)) == 0
    assert period_index(date(2024, 1, 15)) == 1


async def _completed_leg(db, team, do, driver, *, day: int):
    return await make_leg(
        db, team=team, do=do, driver_id=driver.id, status=LegStatus.COMPLETED,
        completed_at=datetime(2026, 5, day, 10, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_build_period_creates_for_drivers_with_legs(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    d1 = await make_driver(db_session, team=team)
    d2 = await make_driver(db_session, team=team)
    await _completed_leg(db_session, team, do, d1, day=6)
    await _completed_leg(db_session, team, do, d1, day=10)
    await _completed_leg(db_session, team, do, d2, day=12)
    await db_session.commit()

    svc = PayrollService(db_session, team.id)
    result = await svc.build_period(
        PayrollBuildPeriodRequest(period_start=_PERIOD_START, period_end=_PERIOD_END),
        actor_user_id=user.id,
    )

    assert result.built_count == 2          # d1, d2 각각 1건
    assert len(result.settlements) == 2
    drivers = {s.driver_id for s in result.settlements}
    assert drivers == {d1.id, d2.id}


@pytest.mark.asyncio
async def test_build_period_skips_driver_without_legs(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    d1 = await make_driver(db_session, team=team)
    d_empty = await make_driver(db_session, team=team)
    await _completed_leg(db_session, team, do, d1, day=8)
    await db_session.commit()

    svc = PayrollService(db_session, team.id)
    result = await svc.build_period(
        PayrollBuildPeriodRequest(
            period_start=_PERIOD_START, period_end=_PERIOD_END,
            driver_ids=[d1.id, d_empty.id],
        ),
        actor_user_id=user.id,
    )

    assert result.built_count == 1
    assert result.skipped_drivers == [d_empty.id]


@pytest.mark.asyncio
async def test_period_summary_aggregates(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    d1 = await make_driver(db_session, team=team)
    await _completed_leg(db_session, team, do, d1, day=9)
    await db_session.commit()

    svc = PayrollService(db_session, team.id)
    await svc.build_period(
        PayrollBuildPeriodRequest(period_start=_PERIOD_START, period_end=_PERIOD_END),
        actor_user_id=user.id,
    )

    summary = await svc.period_summary(_PERIOD_START, _PERIOD_END)
    assert summary.count == 1
    assert summary.driver_count == 1
    assert summary.period_start == _PERIOD_START


@pytest.mark.asyncio
async def test_confirm_blocked_when_lines_unresolved(db_session):
    """요율 미설정 leg → UNRESOLVED 라인 → confirm 차단(핵심 비즈니스 룰)."""
    from common.exceptions.base import ConflictException
    from payroll.const.status import PayrollLineSource, PayrollStatus

    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    driver = await make_driver(db_session, team=team)
    await _completed_leg(db_session, team, do, driver, day=9)  # 요율 설정 없음 → UNRESOLVED
    await db_session.commit()

    svc = PayrollService(db_session, team.id)
    detail = await svc.build(
        PayrollBuildRequest(driver_id=driver.id, period_start=_PERIOD_START, period_end=_PERIOD_END),
        actor_user_id=user.id,
    )
    await db_session.commit()
    # 라인이 UNRESOLVED 인지 확인
    assert any(l.source == PayrollLineSource.UNRESOLVED for l in detail.lines)

    # confirm 은 ConflictException 으로 차단되어야 한다
    with pytest.raises(ConflictException):
        await svc.confirm(detail.id, actor_user_id=user.id)

    # 상태는 여전히 DRAFT
    refetched = await svc.get(detail.id)
    assert refetched.status == PayrollStatus.DRAFT


@pytest.mark.asyncio
async def test_leg_flag_auto_charges_into_payroll(db_session):
    """컨플루언스: leg 단위 Flag(Add-on) → 기사 정산 charge 자동 가산."""
    from addon.model import AddonModel
    from addon.const.status import AddonCategory, AddonUnit
    from leg_layer.model import LegAddonModel

    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    driver = await make_driver(db_session, team=team)
    leg = await _completed_leg(db_session, team, do, driver, day=9)

    # addon 마스터: Night Gate 정액 $50 (팀 전역)
    db_session.add(AddonModel(
        team_id=team.id, code="NGT", name="Night Gate",
        category=AddonCategory.NIGHT_GATE, unit=AddonUnit.FLAT,
        amount=Decimal("50"), auto_apply=True,
    ))
    # leg 에 Night Gate flag 부착
    db_session.add(LegAddonModel(team_id=team.id, leg_id=leg.id, code="NGT"))
    await db_session.commit()

    svc = PayrollService(db_session, team.id)
    detail = await svc.build(
        PayrollBuildRequest(driver_id=driver.id, period_start=_PERIOD_START, period_end=_PERIOD_END),
        actor_user_id=user.id,
    )
    # NGT charge 가 자동 가산되어야 한다
    ngt = [c for c in detail.charges if c.code == "NGT"]
    assert len(ngt) == 1
    assert ngt[0].amount == Decimal("50.00")
    assert detail.addon_total == Decimal("50.00")
    assert detail.grand_total == detail.base_total + Decimal("50.00")


@pytest.mark.asyncio
async def test_repeatable_addons_sum(db_session):
    """컨플루언스 재정의: 같은 add-on(Stop Off) 여러 개 → 각각 정산 합산."""
    from addon.model import AddonModel
    from addon.const.status import AddonCategory, AddonUnit
    from leg_layer.model import LegAddonModel

    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    driver = await make_driver(db_session, team=team)
    leg = await _completed_leg(db_session, team, do, driver, day=9)

    db_session.add(AddonModel(
        team_id=team.id, code="STP", name="Stop Off",
        category=AddonCategory.EXTRA_STOP, unit=AddonUnit.FLAT, amount=Decimal("20"),
    ))
    # Stop Off 3개 부착 (중복 허용)
    for _ in range(3):
        db_session.add(LegAddonModel(team_id=team.id, leg_id=leg.id, code="STP"))
    await db_session.commit()

    svc = PayrollService(db_session, team.id)
    detail = await svc.build(
        PayrollBuildRequest(driver_id=driver.id, period_start=_PERIOD_START, period_end=_PERIOD_END),
        actor_user_id=user.id,
    )
    stp = [c for c in detail.charges if c.code == "STP"]
    assert len(stp) == 3                       # 3개 각각 charge
    assert detail.addon_total == Decimal("60.00")   # 3 × $20


@pytest.mark.asyncio
async def test_non_payable_addon_excluded_from_payroll(db_session):
    """is_payable_to_driver=False add-on 은 기사 정산에서 제외된다(청구 전용)."""
    from leg_layer.model import LegAddonModel

    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    driver = await make_driver(db_session, team=team)
    leg = await _completed_leg(db_session, team, do, driver, day=9)

    # payable add-on $50 (정산 포함) + non-payable add-on $30 (청구 전용, 정산 제외)
    db_session.add(LegAddonModel(
        team_id=team.id, leg_id=leg.id, code="NGT", amount=Decimal("50"),
        is_payable_to_driver=True, is_billable_to_customer=True,
    ))
    db_session.add(LegAddonModel(
        team_id=team.id, leg_id=leg.id, code="PPS", amount=Decimal("30"),
        is_payable_to_driver=False, is_billable_to_customer=True,
    ))
    await db_session.commit()

    svc = PayrollService(db_session, team.id)
    detail = await svc.build(
        PayrollBuildRequest(driver_id=driver.id, period_start=_PERIOD_START, period_end=_PERIOD_END),
        actor_user_id=user.id,
    )
    codes = {c.code for c in detail.charges}
    assert "NGT" in codes
    assert "PPS" not in codes                       # non-payable 제외
    assert detail.addon_total == Decimal("50.00")   # $50 만
