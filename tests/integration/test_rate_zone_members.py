# tests/integration/test_rate_zone_members.py
"""존 멤버 — zip XOR (city,state), 스코프별 원자당 존 1개 제약, CSV city 멤버."""
from __future__ import annotations

import pytest
import pydantic

from tests.integration.factories import make_team


@pytest.mark.asyncio
async def test_city_member_roundtrip_and_xor_validation(db_session):
    from rate_zone.service import RateZoneService
    from rate_zone.schemas.request import (
        RateZoneCreateRequest, RateZoneMemberItem, RateZoneMembersReplaceRequest,
    )

    team = await make_team(db_session)
    svc = RateZoneService(db_session, team.id)

    # city 멤버 존 생성 → round-trip
    zone = await svc.create(RateZoneCreateRequest(
        name="Harbor Cities",
        members=[RateZoneMemberItem(city="San Pedro", state="CA"),
                 RateZoneMemberItem(city="Long Beach", state="CA")],
    ))
    assert len(zone.members) == 2
    assert zone.members[0].city == "San Pedro" and zone.members[0].zip_code is None

    # zip 멤버로 교체
    out = await svc.replace_members(zone.id, RateZoneMembersReplaceRequest(
        members=[RateZoneMemberItem(zip_code="90731")]))
    assert out.count == 1 and out.members[0].zip_code == "90731"

    # XOR 검증 — 둘 다/둘 다 없음/city 인데 state 없음 → ValidationError
    with pytest.raises(pydantic.ValidationError):
        RateZoneMemberItem(zip_code="90731", city="San Pedro", state="CA")
    with pytest.raises(pydantic.ValidationError):
        RateZoneMemberItem()
    with pytest.raises(pydantic.ValidationError):
        RateZoneMemberItem(city="San Pedro")


@pytest.mark.asyncio
async def test_atom_per_zone_per_scope_conflict(db_session):
    """같은 스코프의 다른 존에 속한 원자 → 409. 글로벌+스코프 공존은 허용."""
    from common.exceptions.base import AppException
    from rate_group.model import RateGroupModel
    from rate_group.const.status import RateMethod
    from rate_zone.service import RateZoneService
    from rate_zone.schemas.request import RateZoneCreateRequest, RateZoneMemberItem

    team = await make_team(db_session)
    svc = RateZoneService(db_session, team.id)
    group = RateGroupModel(team_id=team.id, name="RF", method=RateMethod.ZIP)
    db_session.add(group)
    await db_session.flush()

    await svc.create(RateZoneCreateRequest(
        name="Port", members=[RateZoneMemberItem(zip_code="90731")]))

    # 글로벌 스코프에서 같은 zip 을 다른 존에 → 409 ZONE_MEMBER_CONFLICT
    with pytest.raises(AppException) as ei:
        await svc.create(RateZoneCreateRequest(
            name="Port2", members=[RateZoneMemberItem(zip_code="90731")]))
    assert ei.value.code == "ZONE_MEMBER_CONFLICT"

    # 그룹 스코프 존에는 같은 zip 허용 (스코프가 다름)
    scoped = await svc.create(RateZoneCreateRequest(
        name="Port Cold", rate_group_id=group.id,
        members=[RateZoneMemberItem(zip_code="90731")]))
    assert scoped.rate_group_id == group.id

    # 같은 그룹 스코프 안에서 또 겹치면 → 409
    with pytest.raises(AppException) as ei2:
        await svc.create(RateZoneCreateRequest(
            name="Port Cold 2", rate_group_id=group.id,
            members=[RateZoneMemberItem(zip_code="90731")]))
    assert ei2.value.code == "ZONE_MEMBER_CONFLICT"

    # city 원자도 동일 제약
    await svc.create(RateZoneCreateRequest(
        name="Harbor", members=[RateZoneMemberItem(city="San Pedro", state="CA")]))
    with pytest.raises(AppException) as ei3:
        await svc.create(RateZoneCreateRequest(
            name="Harbor2", members=[RateZoneMemberItem(city="san pedro", state="CA")]))
    assert ei3.value.code == "ZONE_MEMBER_CONFLICT"


@pytest.mark.asyncio
async def test_zone_member_csv_with_city_rows(db_session):
    """멤버 CSV import/export — city 행 지원 (export 잠재 크래시 회귀 방지)."""
    from rate_zone.service import RateZoneService
    from rate_zone.schemas.request import RateZoneCreateRequest, RateZoneMemberItem
    from rate_import.service import RateImportService

    team = await make_team(db_session)
    zone = await RateZoneService(db_session, team.id).create(RateZoneCreateRequest(
        name="Mixed", members=[RateZoneMemberItem(zip_code="90731")]))

    imp = RateImportService(db_session, team.id)
    csv_text = "zip_code,city,state\n90744,,\n,Fontana,CA\n"
    report = await imp.import_zone_members(zone.id, csv_text, dry_run=False, actor_user_id=None)
    assert report.ok and report.applied == 2

    out = await imp.export_zone_members(zone.id)
    assert "90744" in out and "Fontana,CA" in out

    # 불량 행 — zip 과 city 동시 / city 인데 state 없음
    bad = "zip_code,city,state\n90731,Fontana,CA\n,Ontario,\n"
    report2 = await imp.import_zone_members(zone.id, bad, dry_run=True, actor_user_id=None)
    assert report2.ok is False and len(report2.errors) == 2
