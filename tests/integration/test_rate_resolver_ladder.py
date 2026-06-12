# tests/integration/test_rate_resolver_ladder.py
"""해석 사다리 (컨플루언스 v12) — 양방향(↔) 셀 + 구체성 우선 + 그룹 상속.

① 원자↔원자 > ② 원자↔존 > ③ 존↔존 > ④ 디폴트 그룹 폴백 > ⑤ UNRESOLVED.
존 조회는 그룹 스코프 존 > 글로벌 존. 기사 미배정 시 ZIP 디폴트 그룹 폴백.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tests.integration.factories import make_team, make_driver

WD = date(2026, 6, 10)
JAN = date(2026, 1, 1)


async def _zip_master(db, zip_, city, state="CA"):
    from zip_code.model import ZipCodeModel
    row = ZipCodeModel(zip=zip_, city=city, state=state)
    db.add(row)
    return row


async def _group(db, team, name, method, *, default=False, inherits=True):
    from rate_group.model import RateGroupModel
    g = RateGroupModel(team_id=team.id, name=name, method=method,
                       is_default=default, inherits_default=inherits)
    db.add(g)
    await db.flush()
    return g


async def _zone(db, team, name, zips=(), cities=(), group_id=None):
    from rate_zone.model import RateZoneModel, RateZoneMemberModel
    from rate_zone.const.status import ZoneKind
    kind = ZoneKind.CITY if cities else ZoneKind.ZIP  # 도시 멤버면 도시존
    z = RateZoneModel(team_id=team.id, name=name, rate_group_id=group_id, kind=kind)
    db.add(z)
    await db.flush()
    for zc in zips:
        db.add(RateZoneMemberModel(team_id=team.id, zone_id=z.id, zip_code=zc))
    for c, s in cities:
        db.add(RateZoneMemberModel(team_id=team.id, zone_id=z.id, city=c, state=s))
    await db.flush()
    return z


async def _assign(db, team, driver, group):
    from driver_rate_assignment.model import DriverRateAssignmentModel
    db.add(DriverRateAssignmentModel(team_id=team.id, driver_id=driver.id,
                                     rate_group_id=group.id, effective_from=JAN))
    await db.flush()


def _entry_svc(db, team):
    from rate_group.entry_service import RateGroupEntryService
    return RateGroupEntryService(db, team.id)


async def _cell(db, team, group, *, amount, from_zip=None, to_zip=None,
                from_zone_id=None, to_zone_id=None,
                from_city=None, from_state=None, to_city=None, to_state=None,
                eff=JAN):
    from rate_group.schemas.request import FlatRateEntryRequest
    from rate_sheet.const.status import RateMoveType, RateServiceType
    return await _entry_svc(db, team).set_entry(group.id, FlatRateEntryRequest(
        move_type=RateMoveType.LOAD, service_type=RateServiceType.LIVE,
        from_zip=from_zip, to_zip=to_zip,
        from_zone_id=from_zone_id, to_zone_id=to_zone_id,
        from_city=from_city, from_state=from_state, to_city=to_city, to_state=to_state,
        amount=Decimal(amount), effective_from=eff))


async def _resolve(db, team, driver, *, from_zip=None, dest_zip=None,
                   from_city=None, from_state=None, dest_city=None, dest_state=None):
    from rate_sheet.resolve import RateResolver
    from rate_sheet.const.status import RateMoveType, RateServiceType
    return await RateResolver(db, team.id).resolve(
        driver_id=driver.id if driver is not None else None, work_date=WD,
        move_type=RateMoveType.LOAD, service_type=RateServiceType.LIVE,
        from_zip=from_zip, dest_zip=dest_zip,
        from_city=from_city, from_state=from_state,
        dest_city=dest_city, dest_state=dest_state)


@pytest.mark.asyncio
async def test_ladder_atom_beats_zone_and_bidirectional(db_session):
    """① 원자 예외가 ③ 존 금액을 뚫는다 + 역방향 레그도 같은 셀."""
    from rate_group.const.status import RateMethod

    team = await make_team(db_session)
    drv = await make_driver(db_session, team=team)
    g = await _group(db_session, team, "ZIP Default", RateMethod.ZIP, default=True)
    z_port = await _zone(db_session, team, "Port", zips=["90731", "90802"])
    z_ie = await _zone(db_session, team, "IE", zips=["92335", "91761"])
    await _assign(db_session, team, drv, g)

    await _cell(db_session, team, g, amount="310",
                from_zone_id=z_port.id, to_zone_id=z_ie.id)          # ③
    await _cell(db_session, team, g, amount="350",
                from_zip="90731", to_zip="92335")                     # ① 예외

    # 예외 zip 쌍 → ① 이 ③ 을 뚫음
    r = await _resolve(db_session, team, drv, from_zip="90731", dest_zip="92335")
    assert r.found and r.base_amount == Decimal("350.00") and r.match_step == "ATOM_ATOM"
    # 역방향 레그 → 같은 ① 셀 (양방향)
    r_rev = await _resolve(db_session, team, drv, from_zip="92335", dest_zip="90731")
    assert r_rev.found and r_rev.base_amount == Decimal("350.00") and r_rev.match_step == "ATOM_ATOM"
    # 예외 아닌 쌍 → ③ 존↔존
    r3 = await _resolve(db_session, team, drv, from_zip="90802", dest_zip="91761")
    assert r3.found and r3.base_amount == Decimal("310.00") and r3.match_step == "ZONE_ZONE"
    # ③ 도 역방향 동일
    r3_rev = await _resolve(db_session, team, drv, from_zip="91761", dest_zip="90802")
    assert r3_rev.found and r3_rev.base_amount == Decimal("310.00")


@pytest.mark.asyncio
async def test_ladder_mixed_atom_zone_both_orientations(db_session):
    """② 원자↔존 혼합 셀 — 원자가 출발이든 도착이든 같은 단계로 매칭."""
    from rate_group.const.status import RateMethod

    team = await make_team(db_session)
    drv = await make_driver(db_session, team=team)
    g = await _group(db_session, team, "ZIP Default", RateMethod.ZIP, default=True)
    z_ie = await _zone(db_session, team, "IE", zips=["92335", "91761"])
    await _assign(db_session, team, drv, g)

    await _cell(db_session, team, g, amount="330", from_zip="90744", to_zone_id=z_ie.id)  # ②

    # 원자(90744)가 출발
    r1 = await _resolve(db_session, team, drv, from_zip="90744", dest_zip="92335")
    assert r1.found and r1.base_amount == Decimal("330.00") and r1.match_step == "ATOM_ZONE"
    # 원자(90744)가 도착 (역방향) — 같은 셀
    r2 = await _resolve(db_session, team, drv, from_zip="91761", dest_zip="90744")
    assert r2.found and r2.base_amount == Decimal("330.00") and r2.match_step == "ATOM_ZONE"


@pytest.mark.asyncio
async def test_reversed_input_updates_same_cell(db_session):
    """양방향 정규화 — 역순 입력은 새 셀이 아니라 같은 셀의 새 버전(supersede/close)."""
    from rate_group.const.status import RateMethod
    from rate_sheet.repository import RateSheetRepository
    from rate_sheet.model import RateEntryModel
    from sqlalchemy import select

    team = await make_team(db_session)
    drv = await make_driver(db_session, team=team)
    g = await _group(db_session, team, "ZIP Default", RateMethod.ZIP, default=True)
    await _assign(db_session, team, drv, g)

    await _cell(db_session, team, g, amount="300", from_zip="90731", to_zip="92335")
    # 역순(92335→90731)으로 같은 구간에 새 버전 입력
    await _cell(db_session, team, g, amount="320", from_zip="92335", to_zip="90731",
                eff=date(2026, 6, 1))

    # 열린(현재 유효) 버전은 1개뿐 — 정규형 from=90731
    rows = list((await db_session.execute(
        select(RateEntryModel).where(
            RateEntryModel.team_id == team.id,
            RateEntryModel.is_active.is_(True),
            RateEntryModel.effective_to.is_(None),
        )
    )).scalars().all())
    assert len(rows) == 1
    assert rows[0].from_zip == "90731" and rows[0].to_zip == "92335"
    assert rows[0].amount == Decimal("320")

    r = await _resolve(db_session, team, drv, from_zip="90731", dest_zip="92335")
    assert r.found and r.base_amount == Decimal("320.00")


@pytest.mark.asyncio
async def test_group_scoped_zone_beats_global(db_session):
    """그룹 스코프 존이 글로벌 존보다 우선 (같은 zip 이 양쪽에 속할 때)."""
    from rate_group.const.status import RateMethod

    team = await make_team(db_session)
    drv = await make_driver(db_session, team=team)
    g_def = await _group(db_session, team, "ZIP Default", RateMethod.ZIP, default=True)
    g_rf = await _group(db_session, team, "Reefer", RateMethod.ZIP)
    z_port = await _zone(db_session, team, "Port", zips=["90731"])
    z_ie = await _zone(db_session, team, "IE", zips=["92335"])                       # 글로벌
    z_cold = await _zone(db_session, team, "Cold", zips=["92335"], group_id=g_rf.id)  # 스코프
    await _assign(db_session, team, drv, g_rf)

    await _cell(db_session, team, g_def, amount="310", from_zone_id=z_port.id, to_zone_id=z_ie.id)
    await _cell(db_session, team, g_rf, amount="455", from_zone_id=z_port.id, to_zone_id=z_cold.id)

    # Reefer 기사: 92335 → 스코프 존(Cold) 우선 → $455
    r = await _resolve(db_session, team, drv, from_zip="90731", dest_zip="92335")
    assert r.found and r.base_amount == Decimal("455.00") and r.via_default_group is False

    # 디폴트 그룹 기사(다른 드라이버): 글로벌 IE 존 → $310
    drv2 = await make_driver(db_session, team=team)
    await _assign(db_session, team, drv2, g_def)
    r2 = await _resolve(db_session, team, drv2, from_zip="90731", dest_zip="92335")
    assert r2.found and r2.base_amount == Decimal("310.00")


@pytest.mark.asyncio
async def test_inheritance_fallback_and_empty_group(db_session):
    """④ 상속 커스텀은 미등록 구간을 디폴트로 폴백, 빈 그룹은 ⑤ 미해석."""
    from rate_group.const.status import RateMethod

    team = await make_team(db_session)
    drv_rf = await make_driver(db_session, team=team)
    drv_alone = await make_driver(db_session, team=team)
    g_def = await _group(db_session, team, "ZIP Default", RateMethod.ZIP, default=True)
    g_rf = await _group(db_session, team, "Reefer", RateMethod.ZIP)               # 상속(기본)
    g_empty = await _group(db_session, team, "Standalone", RateMethod.ZIP, inherits=False)
    z_port = await _zone(db_session, team, "Port", zips=["90731"])
    z_ie = await _zone(db_session, team, "IE", zips=["92335"])
    await _assign(db_session, team, drv_rf, g_rf)
    await _assign(db_session, team, drv_alone, g_empty)

    await _cell(db_session, team, g_def, amount="310", from_zone_id=z_port.id, to_zone_id=z_ie.id)

    # 상속: Reefer 에 셀 없음 → 디폴트 그룹에서 해석 (via_default_group)
    r = await _resolve(db_session, team, drv_rf, from_zip="90731", dest_zip="92335")
    assert r.found and r.base_amount == Decimal("310.00")
    assert r.via_default_group is True and r.rate_group_id == g_def.id

    # 빈 그룹: 폴백 차단 → 미해석
    r2 = await _resolve(db_session, team, drv_alone, from_zip="90731", dest_zip="92335")
    assert r2.found is False and "UNRESOLVED" in (r2.message or "")


@pytest.mark.asyncio
async def test_unassigned_driver_falls_back_to_zip_default(db_session):
    """미배정 기사 → ZIP 디폴트 그룹 자동 적용(assignment_fallback). 디폴트도 없으면 실패."""
    from rate_group.const.status import RateMethod

    team = await make_team(db_session)
    drv = await make_driver(db_session, team=team)  # 배정 없음
    g_def = await _group(db_session, team, "ZIP Default", RateMethod.ZIP, default=True)
    z_port = await _zone(db_session, team, "Port", zips=["90731"])
    z_ie = await _zone(db_session, team, "IE", zips=["92335"])
    await _cell(db_session, team, g_def, amount="310", from_zone_id=z_port.id, to_zone_id=z_ie.id)

    r = await _resolve(db_session, team, drv, from_zip="90731", dest_zip="92335")
    assert r.found and r.base_amount == Decimal("310.00") and r.assignment_fallback is True
    # 유효기간 노출 (조회 화면 표시용)
    assert r.effective_from == JAN and r.effective_to is None

    # 기사 미지정(driver_id=None — 디스패처 조회 화면) → 동일하게 ZIP 디폴트
    r_anon = await _resolve(db_session, team, None, from_zip="90731", dest_zip="92335")
    assert r_anon.found and r_anon.base_amount == Decimal("310.00")
    assert r_anon.assignment_fallback is True

    # ZIP 디폴트가 없는 팀 → 실패 메시지 (기사 지정/미지정 모두)
    team2 = await make_team(db_session)
    drv2 = await make_driver(db_session, team=team2)
    r2 = await _resolve(db_session, team2, drv2, from_zip="90731", dest_zip="92335")
    assert r2.found is False and "배정이 없고" in (r2.message or "")
    r3 = await _resolve(db_session, team2, None, from_zip="90731", dest_zip="92335")
    assert r3.found is False and "기사 미지정" in (r3.message or "")


@pytest.mark.asyncio
async def test_city_method_atoms_zones_and_zip_derivation(db_session):
    """CITY 방식: 도시↔도시(①), 도시↔도시존(②), zip→도시 파생."""
    from rate_group.const.status import RateMethod

    team = await make_team(db_session)
    drv = await make_driver(db_session, team=team)
    g = await _group(db_session, team, "City Default", RateMethod.CITY, default=True)
    z_harbor = await _zone(db_session, team, "Harbor Cities",
                           cities=[("San Pedro", "CA"), ("Long Beach", "CA")])
    await _assign(db_session, team, drv, g)
    await _zip_master(db_session, "90731", "San Pedro")
    await _zip_master(db_session, "92335", "Fontana")
    await db_session.flush()

    await _cell(db_session, team, g, amount="320",
                from_city="San Pedro", from_state="CA", to_city="Fontana", to_state="CA")  # ①
    await _cell(db_session, team, g, amount="305",
                from_zone_id=z_harbor.id, to_city="Ontario", to_state="CA")                # ②

    # ① 도시↔도시
    r1 = await _resolve(db_session, team, drv,
                        from_city="San Pedro", from_state="CA",
                        dest_city="Fontana", dest_state="CA")
    assert r1.found and r1.base_amount == Decimal("320.00") and r1.match_step == "ATOM_ATOM"
    # ② 도시존 — Long Beach ∈ Harbor Cities
    r2 = await _resolve(db_session, team, drv,
                        from_city="Long Beach", from_state="CA",
                        dest_city="Ontario", dest_state="CA")
    assert r2.found and r2.base_amount == Decimal("305.00") and r2.match_step == "ATOM_ZONE"
    # zip 만 주면 zip 마스터에서 도시 파생 → ① 매칭
    r3 = await _resolve(db_session, team, drv, from_zip="90731", dest_zip="92335")
    assert r3.found and r3.base_amount == Decimal("320.00") and r3.match_step == "ATOM_ATOM"
