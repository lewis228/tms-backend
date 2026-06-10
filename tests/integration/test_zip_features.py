# tests/integration/test_zip_features.py
"""zip 마스터 기능 — '도시로 존 추가' + 레그 dest 자동채움."""
from __future__ import annotations
import pytest

from tests.integration.factories import (
    make_team, make_customer, make_delivery_order, make_location,
)


def _zip(db, **kw):
    from zip_code.model import ZipCodeModel
    row = ZipCodeModel(**kw)
    db.add(row)
    return row


@pytest.mark.asyncio
async def test_add_zone_members_by_city(db_session):
    """도시(city+state) 선택 → 그 도시 zip 전부 멤버 합집합 추가, 재호출 중복 없음."""
    from rate_zone.model import RateZoneModel
    from rate_zone.service import RateZoneService

    team = await make_team(db_session)
    _zip(db_session, zip="92335", city="Fontana", state="CA")
    _zip(db_session, zip="92336", city="Fontana", state="CA")
    _zip(db_session, zip="91761", city="Ontario", state="CA")
    zone = RateZoneModel(team_id=team.id, name="IE", code="IE")
    db_session.add(zone)
    await db_session.flush()

    svc = RateZoneService(db_session, team.id)
    res = await svc.add_members_by_city(zone.id, "Fontana", "CA")
    zips = {m.zip_code for m in res.members}
    assert zips == {"92335", "92336"}            # Fontana 만(Ontario 제외)

    # 다른 도시 추가 → 합집합
    res2 = await svc.add_members_by_city(zone.id, "Ontario", "CA")
    assert {m.zip_code for m in res2.members} == {"92335", "92336", "91761"}

    # 재호출 → 중복 안 늘어남
    res3 = await svc.add_members_by_city(zone.id, "Fontana", "CA")
    assert res3.count == 3


@pytest.mark.asyncio
async def test_leg_dest_autofill_from_location_zip(db_session):
    """도착 위치(zip_id) → leg.dest_zip/city/state 자동채움."""
    from container.model import ContainerModel
    from container.const.status import ContainerSize
    from container_stop.model import ContainerStopModel
    from leg.const.status import PointType, MoveType, ServiceType
    from leg.service import LegService
    from leg.schemas.request import LegCreateRequest
    from delivery_order.const.status import DeliveryStatus
    from location.const.kind import LocationKind

    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)

    zc = _zip(db_session, zip="90745", city="Carson", state="CA")
    await db_session.flush()
    loc = await make_location(db_session, team=team, kind=LocationKind.YARD)
    loc.zip_id = zc.id
    cont = ContainerModel(team_id=team.id, delivery_order_id=do.id, sequence_no=1,
                          container_number="MSCU1112223", size=ContainerSize.SIZE_40HC)
    db_session.add(cont)
    await db_session.flush()
    stop = ContainerStopModel(team_id=team.id, container_id=cont.id, sequence_no=1,
                              point_type=PointType.YARD, location_id=loc.id)
    db_session.add(stop)
    await db_session.flush()

    leg = await LegService(db_session, team.id).create(LegCreateRequest(
        delivery_order_id=do.id, container_id=cont.id, step=DeliveryStatus.DISPATCHED,
        move_type=MoveType.EMPTY, service_type=ServiceType.DROP, to_point_id=stop.id,
    ))
    assert leg.dest_zip == "90745"
    assert leg.dest_city == "Carson"
    assert leg.dest_state == "CA"


@pytest.mark.asyncio
async def test_leg_dest_explicit_override(db_session):
    """dest 명시 입력 시 자동채움이 덮어쓰지 않음(override)."""
    from container.model import ContainerModel
    from container.const.status import ContainerSize
    from container_stop.model import ContainerStopModel
    from leg.const.status import PointType, MoveType, ServiceType
    from leg.service import LegService
    from leg.schemas.request import LegCreateRequest
    from delivery_order.const.status import DeliveryStatus
    from location.const.kind import LocationKind

    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    zc = _zip(db_session, zip="90745", city="Carson", state="CA")
    await db_session.flush()
    loc = await make_location(db_session, team=team, kind=LocationKind.YARD)
    loc.zip_id = zc.id
    cont = ContainerModel(team_id=team.id, delivery_order_id=do.id, sequence_no=1,
                          container_number="MSCU9998887", size=ContainerSize.SIZE_40HC)
    db_session.add(cont)
    await db_session.flush()
    stop = ContainerStopModel(team_id=team.id, container_id=cont.id, sequence_no=1,
                              point_type=PointType.YARD, location_id=loc.id)
    db_session.add(stop)
    await db_session.flush()

    leg = await LegService(db_session, team.id).create(LegCreateRequest(
        delivery_order_id=do.id, container_id=cont.id, step=DeliveryStatus.DISPATCHED,
        move_type=MoveType.EMPTY, service_type=ServiceType.DROP, to_point_id=stop.id,
        dest_zip="99999", dest_city="Override City", dest_state="WA",
    ))
    assert leg.dest_zip == "99999"      # override 유지
    assert leg.dest_city == "Override City"


@pytest.mark.asyncio
async def test_leg_update_to_point_autofills_dest(db_session):
    """update 로 to_point 변경 시 dest 자동 갱신."""
    from container.model import ContainerModel
    from container.const.status import ContainerSize
    from container_stop.model import ContainerStopModel
    from leg.const.status import PointType, MoveType, ServiceType
    from leg.service import LegService
    from leg.schemas.request import LegCreateRequest, LegUpdateRequest
    from delivery_order.const.status import DeliveryStatus
    from location.const.kind import LocationKind

    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    zc = _zip(db_session, zip="90745", city="Carson", state="CA")
    await db_session.flush()
    loc = await make_location(db_session, team=team, kind=LocationKind.YARD)
    loc.zip_id = zc.id
    cont = ContainerModel(team_id=team.id, delivery_order_id=do.id, sequence_no=1,
                          container_number="MSCU7776665", size=ContainerSize.SIZE_40HC)
    db_session.add(cont)
    await db_session.flush()
    stop = ContainerStopModel(team_id=team.id, container_id=cont.id, sequence_no=1,
                              point_type=PointType.YARD, location_id=loc.id)
    db_session.add(stop)
    await db_session.flush()

    svc = LegService(db_session, team.id)
    # to_point 없이 생성 → dest 비어있음
    leg = await svc.create(LegCreateRequest(
        delivery_order_id=do.id, container_id=cont.id, step=DeliveryStatus.DISPATCHED,
        move_type=MoveType.EMPTY, service_type=ServiceType.DROP,
    ))
    assert leg.dest_zip is None
    # update 로 to_point 지정 → 자동채움
    updated = await svc.update(leg.id, LegUpdateRequest(to_point_id=stop.id))
    assert updated.dest_zip == "90745"
    assert updated.dest_city == "Carson"
