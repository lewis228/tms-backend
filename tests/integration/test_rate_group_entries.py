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
    group = RateGroupModel(team_id=team.id, name="Z", method=RateMethod.ZONE)
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
    assert resp.method == RateMethod.ZONE
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
