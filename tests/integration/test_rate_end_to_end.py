# tests/integration/test_rate_end_to_end.py
"""E2E: leg 생성 → origin/dest 자동채움 → RateResolver 가 zone×zone 으로 정산금액 해석.

leg.service.create 가 from_point/to_point 마스터 zip 으로 origin/dest 를 채우고,
payroll.resolve.resolve_leg_rate 가 그걸로 from_zip→from_zone, dest_zip→to_zone 셀을 찾는다.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tests.integration.factories import (
    make_team, make_customer, make_delivery_order, make_location, make_driver,
)


def _zip(db, **kw):
    from zip_code.model import ZipCodeModel
    row = ZipCodeModel(**kw)
    db.add(row)
    return row


@pytest.mark.asyncio
async def test_leg_create_autofill_then_resolve(db_session):
    from container.model import ContainerModel
    from container.const.status import ContainerSize
    from container_stop.model import ContainerStopModel
    from leg.const.status import PointType, MoveType, ServiceType
    from leg.service import LegService
    from leg.model import LegModel
    from leg.schemas.request import LegCreateRequest
    from delivery_order.const.status import DeliveryStatus
    from location.const.kind import LocationKind
    from rate_group.model import RateGroupModel
    from rate_group.const.status import RateMethod
    from rate_zone.model import RateZoneModel, RateZoneMemberModel
    from rate_sheet.model import RateSheetModel, RateEntryModel
    from rate_sheet.const.status import SheetKind, RateMoveType, RateServiceType
    from driver_rate_assignment.model import DriverRateAssignmentModel
    from payroll.resolve import resolve_leg_rate
    from sqlalchemy import select

    team = await make_team(db_session)
    driver = await make_driver(db_session, team=team)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)

    # zip 마스터 + 위치(출발 항만 / 도착 내륙)
    zc_from = _zip(db_session, zip="90731", city="San Pedro", state="CA")
    zc_to = _zip(db_session, zip="92335", city="Fontana", state="CA")
    await db_session.flush()
    loc_from = await make_location(db_session, team=team, kind=LocationKind.YARD)
    loc_from.zip_id = zc_from.id
    loc_to = await make_location(db_session, team=team, kind=LocationKind.YARD)
    loc_to.zip_id = zc_to.id

    # zone (zip→zone) + 매트릭스
    z_port = RateZoneModel(team_id=team.id, name="Port", code="PORT")
    z_ie = RateZoneModel(team_id=team.id, name="IE", code="IE")
    group = RateGroupModel(team_id=team.id, name="Z", method=RateMethod.ZIP)
    db_session.add_all([z_port, z_ie, group])
    await db_session.flush()
    db_session.add_all([
        RateZoneMemberModel(team_id=team.id, zone_id=z_port.id, zip_code="90731"),
        RateZoneMemberModel(team_id=team.id, zone_id=z_ie.id, zip_code="92335"),
        DriverRateAssignmentModel(team_id=team.id, driver_id=driver.id,
                                  rate_group_id=group.id, effective_from=date(2026, 1, 1)),
    ])
    sheet = RateSheetModel(team_id=team.id, rate_group_id=group.id, kind=SheetKind.ZIP,
                           move_type=RateMoveType.LOAD, service_type=RateServiceType.LIVE)
    db_session.add(sheet)
    await db_session.flush()
    db_session.add(RateEntryModel(team_id=team.id, rate_sheet_id=sheet.id,
                                  from_zone_id=z_port.id, to_zone_id=z_ie.id, amount=Decimal("300"),
                                  effective_from=date(2026, 1, 1)))

    cont = ContainerModel(team_id=team.id, delivery_order_id=do.id, sequence_no=1,
                          container_number="MSCU1234560", size=ContainerSize.SIZE_40HC)
    db_session.add(cont)
    await db_session.flush()
    from_stop = ContainerStopModel(team_id=team.id, container_id=cont.id, sequence_no=1,
                                   point_type=PointType.YARD, location_id=loc_from.id)
    to_stop = ContainerStopModel(team_id=team.id, container_id=cont.id, sequence_no=2,
                                 point_type=PointType.YARD, location_id=loc_to.id)
    db_session.add_all([from_stop, to_stop])
    await db_session.flush()

    # leg 생성 → origin/dest 자동채움
    leg_resp = await LegService(db_session, team.id).create(LegCreateRequest(
        delivery_order_id=do.id, container_id=cont.id, step=DeliveryStatus.DISPATCHED,
        move_type=MoveType.LOADED, service_type=ServiceType.LIVE,
        from_point_id=from_stop.id, to_point_id=to_stop.id, driver_id=driver.id,
    ))
    assert leg_resp.origin_zip == "90731"
    assert leg_resp.dest_zip == "92335"

    # ORM leg → 정산 해석
    leg = (await db_session.execute(
        select(LegModel).where(LegModel.id == leg_resp.id)
    )).scalar_one()
    result = await resolve_leg_rate(db_session, team.id, leg)
    assert result.found
    assert result.base_amount == Decimal("300.00")
    assert result.zone_id == z_ie.id  # 도착존
    assert result.match_step == "ZONE_ZONE"  # 사다리 ③
    assert result.via_default_group is False
    assert result.assignment_fallback is False
