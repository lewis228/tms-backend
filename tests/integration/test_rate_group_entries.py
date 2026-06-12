# tests/integration/test_rate_group_entries.py
"""그룹 단위 플랫 행 API(재설계): set_entry → 시트 자동 라우팅 → list_entries 플랫 반환.

플랫 행 1개 = (group, kind, move, service) 시트의 셀 1개. move/service 별로 다른 시트로 라우팅됨.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from rate_group.model import RateGroupModel
from rate_group.const.status import RateMethod
from rate_group.entry_service import RateGroupEntryService
from rate_group.schemas.request import FlatRateEntryRequest
from rate_zone.model import RateZoneModel
from rate_sheet.const.status import RateMoveType, RateServiceType

from tests.integration.factories import make_team


@pytest.mark.asyncio
async def test_flat_entry_routes_to_sheets_and_lists(db_session):
    team = await make_team(db_session)
    group = RateGroupModel(team_id=team.id, name="Z", method=RateMethod.ZIP)
    z1 = RateZoneModel(team_id=team.id, name="A", code="A")
    z2 = RateZoneModel(team_id=team.id, name="B", code="B")
    db_session.add_all([group, z1, z2])
    await db_session.flush()

    svc = RateGroupEntryService(db_session, team.id)

    # (LOAD, LIVE) z1→z2 = 100
    await svc.set_entry(group.id, FlatRateEntryRequest(
        move_type=RateMoveType.LOAD, service_type=RateServiceType.LIVE,
        from_zone_id=z1.id, to_zone_id=z2.id,
        amount=Decimal("100"), effective_from=date(2026, 1, 1),
    ))
    # (EMPTY, DROP) z1→z2 = 40 → 다른 시트로 라우팅
    await svc.set_entry(group.id, FlatRateEntryRequest(
        move_type=RateMoveType.EMPTY, service_type=RateServiceType.DROP,
        from_zone_id=z1.id, to_zone_id=z2.id,
        amount=Decimal("40"), effective_from=date(2026, 1, 1),
    ))

    resp = await svc.list_entries(group.id)
    assert resp.method == RateMethod.ZIP
    assert len(resp.rows) == 2
    # 두 행은 서로 다른 시트(move/service 분리)
    sheet_ids = {r.rate_sheet_id for r in resp.rows}
    assert len(sheet_ids) == 2
    by_amount = {r.amount: (r.move_type, r.service_type) for r in resp.rows}
    assert by_amount[Decimal("100.00")] == (RateMoveType.LOAD, RateServiceType.LIVE)
    assert by_amount[Decimal("40.00")] == (RateMoveType.EMPTY, RateServiceType.DROP)

    # 같은 셀 재등록(다른 effective_from) → append-only, 현재 유효 셀 수는 그대로 2
    await svc.set_entry(group.id, FlatRateEntryRequest(
        move_type=RateMoveType.LOAD, service_type=RateServiceType.LIVE,
        from_zone_id=z1.id, to_zone_id=z2.id,
        amount=Decimal("120"), effective_from=date(2026, 6, 1),
    ))
    resp2 = await svc.list_entries(group.id)
    assert len(resp2.rows) == 2  # 열린(현재 유효) 셀만
    amounts = {r.amount for r in resp2.rows}
    assert Decimal("120.00") in amounts  # 최신값으로 갱신


@pytest.mark.asyncio
async def test_entry_zone_coords_validated(db_session):
    """셀 좌표 zone_id — 존재(404) / kind 일치(422) / 스코프(422) 검증 (죽은 셀 차단)."""
    from common.exceptions.base import AppException
    from rate_zone.const.status import ZoneKind

    team = await make_team(db_session)
    group = RateGroupModel(team_id=team.id, name="Z", method=RateMethod.ZIP)
    other_group = RateGroupModel(team_id=team.id, name="O", method=RateMethod.ZIP)
    db_session.add_all([group, other_group])
    await db_session.flush()
    z_ok = RateZoneModel(team_id=team.id, name="OK")                              # 글로벌 ZIP존
    z_city = RateZoneModel(team_id=team.id, name="C", kind=ZoneKind.CITY)         # 도시존
    z_scoped = RateZoneModel(team_id=team.id, name="S", rate_group_id=None)
    db_session.add_all([z_ok, z_city, z_scoped])
    await db_session.flush()
    z_scoped.rate_group_id = other_group.id                                       # 다른 그룹 전용
    await db_session.flush()

    svc = RateGroupEntryService(db_session, team.id)

    def _req(**kw):
        return FlatRateEntryRequest(
            move_type=RateMoveType.LOAD, service_type=RateServiceType.LIVE,
            amount=Decimal("100"), effective_from=date(2026, 1, 1), **kw)

    # 존재하지 않는 존 → 404
    with pytest.raises(AppException) as e1:
        await svc.set_entry(group.id, _req(from_zone_id=z_ok.id, to_zone_id=999999))
    assert e1.value.status_code == 404
    # ZIP 그룹 셀에 도시존 → 422 ZONE_KIND_MISMATCH
    with pytest.raises(AppException) as e2:
        await svc.set_entry(group.id, _req(from_zone_id=z_ok.id, to_zone_id=z_city.id))
    assert e2.value.code == "ZONE_KIND_MISMATCH"
    # 다른 그룹 전용 존 → 422 ZONE_SCOPE_MISMATCH
    with pytest.raises(AppException) as e3:
        await svc.set_entry(group.id, _req(from_zone_id=z_ok.id, to_zone_id=z_scoped.id))
    assert e3.value.code == "ZONE_SCOPE_MISMATCH"
    # 글로벌 존 + zip 혼합 좌표는 정상 통과
    out = await svc.set_entry(group.id, _req(from_zone_id=z_ok.id, to_zip="92335"))
    assert out.rate_entry_id
