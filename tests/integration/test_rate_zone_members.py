# tests/integration/test_rate_zone_members.py
"""존 멤버 — 종류(kind) 분리 강제 + zip XOR (city,state) + 스코프별 원자당 존 1개 + CSV."""
from __future__ import annotations

import pytest
import pydantic

from tests.integration.factories import make_team


def _zip_master(db, zip_, city, state="CA"):
    from zip_code.model import ZipCodeModel
    row = ZipCodeModel(zip=zip_, city=city, state=state)
    db.add(row)
    return row


@pytest.mark.asyncio
async def test_zone_kind_separation_enforced(db_session):
    """ZIP존=zip 멤버만 / 도시존=도시 멤버만 — 혼합은 양방향 모두 422."""
    from common.exceptions.base import AppException
    from rate_zone.service import RateZoneService
    from rate_zone.const.status import ZoneKind
    from rate_zone.schemas.request import (
        RateZoneCreateRequest, RateZoneMemberItem, RateZoneMembersReplaceRequest,
    )

    team = await make_team(db_session)
    svc = RateZoneService(db_session, team.id)

    # ZIP존에 도시 멤버 → 422
    with pytest.raises(AppException) as e1:
        await svc.create(RateZoneCreateRequest(
            name="Bad ZIP Zone", kind=ZoneKind.ZIP,
            members=[RateZoneMemberItem(city="San Pedro", state="CA")]))
    assert e1.value.code == "ZONE_KIND_MISMATCH"

    # 도시존에 zip 멤버 → 422
    with pytest.raises(AppException) as e2:
        await svc.create(RateZoneCreateRequest(
            name="Bad City Zone", kind=ZoneKind.CITY,
            members=[RateZoneMemberItem(zip_code="90731")]))
    assert e2.value.code == "ZONE_KIND_MISMATCH"

    # 정상 생성 — ZIP존(zip), 도시존(도시)
    zz = await svc.create(RateZoneCreateRequest(
        name="Harbor ZIPs", kind=ZoneKind.ZIP,
        members=[RateZoneMemberItem(zip_code="90731")]))
    cz = await svc.create(RateZoneCreateRequest(
        name="Harbor Cities", kind=ZoneKind.CITY,
        members=[RateZoneMemberItem(city="San Pedro", state="CA")]))
    assert zz.kind == ZoneKind.ZIP and cz.kind == ZoneKind.CITY

    # replace 로 혼합 시도 → 422
    with pytest.raises(AppException) as e3:
        await svc.replace_members(cz.id, RateZoneMembersReplaceRequest(
            members=[RateZoneMemberItem(zip_code="90744")]))
    assert e3.value.code == "ZONE_KIND_MISMATCH"

    # '도시로 추가'(zip 확장)는 ZIP존 전용 — 도시존이면 422
    _zip_master(db_session, "90731", "San Pedro")
    await db_session.flush()
    with pytest.raises(AppException) as e4:
        await svc.add_members_by_city(cz.id, "San Pedro", "CA")
    assert e4.value.code == "ZONE_KIND_MISMATCH"
    # ZIP존에서는 정상 동작 (도시의 zip 전부 확장)
    out = await svc.add_members_by_city(zz.id, "San Pedro", "CA")
    assert all(m.zip_code for m in out.members)

    # kind 변경은 멤버가 있으면 409, 비우면 허용
    from rate_zone.schemas.request import RateZoneUpdateRequest
    with pytest.raises(AppException) as e5:
        await svc.update(zz.id, RateZoneUpdateRequest(kind=ZoneKind.CITY))
    assert e5.value.code == "ZONE_KIND_LOCKED"
    await svc.replace_members(zz.id, RateZoneMembersReplaceRequest(members=[]))
    changed = await svc.update(zz.id, RateZoneUpdateRequest(kind=ZoneKind.CITY))
    assert changed.kind == ZoneKind.CITY


@pytest.mark.asyncio
async def test_member_xor_validation(db_session):
    """멤버 = zip XOR (city,state) — 스키마 검증."""
    from rate_zone.schemas.request import RateZoneMemberItem

    with pytest.raises(pydantic.ValidationError):
        RateZoneMemberItem(zip_code="90731", city="San Pedro", state="CA")
    with pytest.raises(pydantic.ValidationError):
        RateZoneMemberItem()
    with pytest.raises(pydantic.ValidationError):
        RateZoneMemberItem(city="San Pedro")  # state 누락


@pytest.mark.asyncio
async def test_resolver_filters_by_zone_kind(db_session):
    """해석 kind 필터 — zip 은 도시존에 안 잡히고, 도시는 ZIP존에 안 잡힌다."""
    from rate_zone.model import RateZoneModel, RateZoneMemberModel
    from rate_zone.repository import RateZoneRepository
    from rate_zone.const.status import ZoneKind

    team = await make_team(db_session)
    # 비정상 데이터를 일부러 직접 삽입(서비스 우회) — 해석 필터가 막아주는지 확인
    z_zip = RateZoneModel(team_id=team.id, name="Z-ZIP", kind=ZoneKind.ZIP)
    z_city = RateZoneModel(team_id=team.id, name="Z-CITY", kind=ZoneKind.CITY)
    db_session.add_all([z_zip, z_city])
    await db_session.flush()
    db_session.add_all([
        RateZoneMemberModel(team_id=team.id, zone_id=z_zip.id, zip_code="90731"),
        # 도시존에 zip 멤버가 (우회로) 들어가 있어도:
        RateZoneMemberModel(team_id=team.id, zone_id=z_city.id, zip_code="92335"),
        RateZoneMemberModel(team_id=team.id, zone_id=z_city.id, city="San Pedro", state="CA"),
        # ZIP존에 city 멤버가 들어가 있어도:
        RateZoneMemberModel(team_id=team.id, zone_id=z_zip.id, city="Fontana", state="CA"),
    ])
    await db_session.flush()

    repo = RateZoneRepository(db_session, team.id)
    # zip 해석은 ZIP존만 — 도시존의 zip 멤버(92335)는 무시
    assert await repo.resolve_zone_id_for_zip("90731") == z_zip.id
    assert await repo.resolve_zone_id_for_zip("92335") is None
    # 도시 해석은 도시존만 — ZIP존의 city 멤버(Fontana)는 무시
    assert await repo.resolve_zone_id_for_city("San Pedro", "CA") == z_city.id
    assert await repo.resolve_zone_id_for_city("Fontana", "CA") is None


@pytest.mark.asyncio
async def test_atom_per_zone_per_scope_conflict(db_session):
    """같은 스코프의 다른 존에 속한 원자 → 409. 글로벌+스코프 공존은 허용."""
    from common.exceptions.base import AppException
    from rate_group.model import RateGroupModel
    from rate_group.const.status import RateMethod
    from rate_zone.service import RateZoneService
    from rate_zone.const.status import ZoneKind
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

    # city 원자도 동일 제약 (도시존끼리)
    await svc.create(RateZoneCreateRequest(
        name="Harbor", kind=ZoneKind.CITY,
        members=[RateZoneMemberItem(city="San Pedro", state="CA")]))
    with pytest.raises(AppException) as ei3:
        await svc.create(RateZoneCreateRequest(
            name="Harbor2", kind=ZoneKind.CITY,
            members=[RateZoneMemberItem(city="san pedro", state="CA")]))
    assert ei3.value.code == "ZONE_MEMBER_CONFLICT"


@pytest.mark.asyncio
async def test_zone_member_csv_respects_kind(db_session):
    """멤버 CSV — 존 종류에 맞는 행만 허용, 어긋나면 422."""
    from common.exceptions.base import AppException
    from rate_zone.service import RateZoneService
    from rate_zone.const.status import ZoneKind
    from rate_zone.schemas.request import RateZoneCreateRequest, RateZoneMemberItem
    from rate_import.service import RateImportService

    team = await make_team(db_session)
    svc = RateZoneService(db_session, team.id)
    imp = RateImportService(db_session, team.id)

    # ZIP존 — zip 행 임포트 OK, 도시 행 포함 시 422
    zz = await svc.create(RateZoneCreateRequest(
        name="Zips", kind=ZoneKind.ZIP,
        members=[RateZoneMemberItem(zip_code="90731")]))
    report = await imp.import_zone_members(zz.id, "zip_code,city,state\n90744,,\n", dry_run=False, actor_user_id=None)
    assert report.ok and report.applied == 1
    with pytest.raises(AppException) as e1:
        await imp.import_zone_members(zz.id, "zip_code,city,state\n,Fontana,CA\n", dry_run=False, actor_user_id=None)
    assert e1.value.code == "ZONE_KIND_MISMATCH"

    # 도시존 — 도시 행 임포트 OK + export 에 도시 표기
    cz = await svc.create(RateZoneCreateRequest(name="Cities", kind=ZoneKind.CITY))
    report2 = await imp.import_zone_members(cz.id, "zip_code,city,state\n,Fontana,CA\n,Ontario,CA\n", dry_run=False, actor_user_id=None)
    assert report2.ok and report2.applied == 2
    out = await imp.export_zone_members(cz.id)
    assert "Fontana,CA" in out and "Ontario,CA" in out

    # 불량 행 — zip+city 동시 / city 인데 state 없음 → 행 단위 에러 리포트
    bad = "zip_code,city,state\n90731,Fontana,CA\n,Ontario,\n"
    report3 = await imp.import_zone_members(cz.id, bad, dry_run=True, actor_user_id=None)
    assert report3.ok is False and len(report3.errors) == 2


@pytest.mark.asyncio
async def test_atom_conflict_enforced_on_csv_import_and_scope_change(db_session):
    """CSV import / 헤더 스코프 변경도 '같은 스코프 원자당 존 1개'(409) 를 우회 못 한다."""
    from common.exceptions.base import AppException
    from rate_group.model import RateGroupModel
    from rate_group.const.status import RateMethod
    from rate_zone.service import RateZoneService
    from rate_zone.schemas.request import (
        RateZoneCreateRequest, RateZoneMemberItem, RateZoneUpdateRequest,
    )
    from rate_import.service import RateImportService

    team = await make_team(db_session)
    svc = RateZoneService(db_session, team.id)
    imp = RateImportService(db_session, team.id)
    group = RateGroupModel(team_id=team.id, name="RF", method=RateMethod.ZIP)
    db_session.add(group)
    await db_session.flush()

    await svc.create(RateZoneCreateRequest(
        name="Port", members=[RateZoneMemberItem(zip_code="90731")]))
    other = await svc.create(RateZoneCreateRequest(
        name="IE", members=[RateZoneMemberItem(zip_code="92335")]))

    # CSV 로 같은 글로벌 스코프의 다른 존에 90731 을 넣으면 409 (단건 추가 경로와 동일)
    with pytest.raises(AppException) as e1:
        await imp.import_zone_members(other.id, "zip_code,city,state\n90731,,\n",
                                      dry_run=True, actor_user_id=None)
    assert e1.value.code == "ZONE_MEMBER_CONFLICT"

    # 그룹 스코프 존(같은 zip 허용)을 글로벌로 이동하면 글로벌의 Port 와 충돌 → 409
    scoped = await svc.create(RateZoneCreateRequest(
        name="Port Cold", rate_group_id=group.id,
        members=[RateZoneMemberItem(zip_code="90731")]))
    with pytest.raises(AppException) as e2:
        await svc.update(scoped.id, RateZoneUpdateRequest(rate_group_id=None))
    assert e2.value.code == "ZONE_MEMBER_CONFLICT"

    # 충돌 없는 스코프 이동은 정상 수행 (IE 존 → 그룹 스코프)
    moved = await svc.update(other.id, RateZoneUpdateRequest(rate_group_id=group.id))
    assert moved.rate_group_id == group.id
