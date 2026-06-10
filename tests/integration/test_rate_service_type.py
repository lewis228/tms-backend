# tests/integration/test_rate_service_type.py
"""재설계(Zone×Zone): 같은 From→To·Move 라도 Service Type 별 요율이 다르다.

같은 (from_zone→to_zone, LOAD, 40ft) 셀이라도 service_type=LIVE 와 DROP 의 금액이 달라야 한다.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from rate_group.model import RateGroupModel
from rate_group.const.status import RateMethod
from driver_rate_assignment.model import DriverRateAssignmentModel
from rate_zone.model import RateZoneModel, RateZoneMemberModel
from rate_sheet.model import RateSheetModel, RateEntryModel
from rate_sheet.const.status import SheetKind, RateMoveType, RateServiceType, RateContainerSize
from rate_sheet.resolve import RateResolver

from tests.integration.factories import make_team, make_driver


@pytest.mark.asyncio
async def test_service_type_differentiates_rate(db_session):
    team = await make_team(db_session)
    driver = await make_driver(db_session, team=team)

    group = RateGroupModel(team_id=team.id, name="LA Zone", method=RateMethod.ZONE)
    from_zone = RateZoneModel(team_id=team.id, name="LA Terminal Zone")
    to_zone = RateZoneModel(team_id=team.id, name="SoCal")
    db_session.add_all([group, from_zone, to_zone])
    await db_session.flush()

    # zip→zone 매핑: 출발 90001 → from_zone, 도착 90210 → to_zone
    db_session.add(RateZoneMemberModel(team_id=team.id, zone_id=from_zone.id, zip_code="90001"))
    db_session.add(RateZoneMemberModel(team_id=team.id, zone_id=to_zone.id, zip_code="90210"))
    db_session.add(DriverRateAssignmentModel(
        team_id=team.id, driver_id=driver.id, rate_group_id=group.id, effective_from=date(2026, 1, 1),
    ))
    # 같은 (LOAD, from→to) 슬롯, service_type 만 다른 두 시트
    sheet_live = RateSheetModel(team_id=team.id, rate_group_id=group.id, kind=SheetKind.ZONE,
                                move_type=RateMoveType.LOAD, service_type=RateServiceType.LIVE)
    sheet_drop = RateSheetModel(team_id=team.id, rate_group_id=group.id, kind=SheetKind.ZONE,
                                move_type=RateMoveType.LOAD, service_type=RateServiceType.DROP)
    db_session.add_all([sheet_live, sheet_drop])
    await db_session.flush()

    db_session.add(RateEntryModel(team_id=team.id, rate_sheet_id=sheet_live.id,
                                  from_zone_id=from_zone.id, to_zone_id=to_zone.id,
                                  container_size=RateContainerSize.SIZE_40, amount=Decimal("1000"),
                                  effective_from=date(2026, 1, 1)))
    db_session.add(RateEntryModel(team_id=team.id, rate_sheet_id=sheet_drop.id,
                                  from_zone_id=from_zone.id, to_zone_id=to_zone.id,
                                  container_size=RateContainerSize.SIZE_40, amount=Decimal("800"),
                                  effective_from=date(2026, 1, 1)))
    await db_session.commit()

    resolver = RateResolver(db_session, team.id)
    common = dict(driver_id=driver.id, work_date=date(2026, 5, 9), move_type=RateMoveType.LOAD,
                  from_zip="90001", dest_zip="90210", container_size=RateContainerSize.SIZE_40)

    live = await resolver.resolve(service_type=RateServiceType.LIVE, **common)
    drop = await resolver.resolve(service_type=RateServiceType.DROP, **common)

    assert live.found and live.base_amount == Decimal("1000.00")
    assert drop.found and drop.base_amount == Decimal("800.00")
