# tests/integration/test_addon_driver_rate.py
"""기사별 add-on 금액 override (분리 테이블 addon_driver_rate).

마스터(FUEL 20%)는 카탈로그, 기사별 행은 금액만 override.
해석: override 있으면 그 값, 없으면 마스터 기본값 폴백.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from tests.integration.factories import make_team, make_driver


@pytest.mark.asyncio
async def test_driver_rate_override_and_fallback(db_session):
    from addon.model import AddonModel, AddonDriverRateModel
    from addon.const.status import AddonCategory, AddonUnit
    from leg_layer.charge import resolve_addon_amount

    team = await make_team(db_session)
    drv_a = await make_driver(db_session, team=team)
    drv_b = await make_driver(db_session, team=team)

    fuel = AddonModel(team_id=team.id, code="FUEL", name="Fuel Surcharge",
                      category=AddonCategory.FUEL, unit=AddonUnit.PERCENT,
                      percent=Decimal("0.20"))
    db_session.add(fuel)
    await db_session.flush()
    # drv_a 만 18% 개인 요율
    db_session.add(AddonDriverRateModel(team_id=team.id, addon_id=fuel.id,
                                        driver_id=drv_a.id, percent=Decimal("0.18")))
    await db_session.flush()

    base = Decimal("310")
    # drv_a → override 18%
    got_a = await resolve_addon_amount(db_session, team.id, "FUEL",
                                       driver_id=drv_a.id, base_amount=base)
    assert got_a is not None and got_a[0] == Decimal("55.80")  # 310 × 0.18
    # drv_b → 팀 기본 20% 폴백
    got_b = await resolve_addon_amount(db_session, team.id, "FUEL",
                                       driver_id=drv_b.id, base_amount=base)
    assert got_b is not None and got_b[0] == Decimal("62.00")  # 310 × 0.20
    # driver 미지정(D/O 레벨) → 팀 기본
    got_none = await resolve_addon_amount(db_session, team.id, "FUEL", base_amount=base)
    assert got_none is not None and got_none[0] == Decimal("62.00")


@pytest.mark.asyncio
async def test_driver_rate_upsert_delete_service(db_session):
    from addon.model import AddonModel
    from addon.const.status import AddonCategory, AddonUnit
    from addon.service import AddonService
    from addon.schemas.request import AddonDriverRateUpsertRequest

    team = await make_team(db_session)
    drv = await make_driver(db_session, team=team)
    ngt = AddonModel(team_id=team.id, code="NGT", name="Night Gate",
                     category=AddonCategory.NIGHT_GATE, unit=AddonUnit.FLAT,
                     amount=Decimal("75"))
    db_session.add(ngt)
    await db_session.flush()

    svc = AddonService(db_session, team.id)
    # 업서트(생성)
    r1 = await svc.upsert_driver_rate(ngt.id, drv.id,
                                      AddonDriverRateUpsertRequest(amount=Decimal("60")))
    assert r1.amount == Decimal("60.00")
    # 업서트(수정) — 같은 (addon, driver) 행 갱신
    r2 = await svc.upsert_driver_rate(ngt.id, drv.id,
                                      AddonDriverRateUpsertRequest(amount=Decimal("65")))
    assert r2.id == r1.id and r2.amount == Decimal("65.00")
    rates = await svc.list_driver_rates(ngt.id)
    assert len(rates) == 1
    # 삭제 → 팀 기본 복귀
    out = await svc.delete_driver_rate(ngt.id, drv.id)
    assert out.deleted
    assert await svc.list_driver_rates(ngt.id) == []
