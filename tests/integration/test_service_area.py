# tests/integration/test_service_area.py
"""영업권역(Service Area) — 선언 CRUD + 중복 409/되살림 + zip 검색 스코프 필터."""
from __future__ import annotations

import pytest
import pydantic

from tests.integration.factories import make_team


def _zip(db, **kw):
    from zip_code.model import ZipCodeModel
    row = ZipCodeModel(**kw)
    db.add(row)
    return row


@pytest.mark.asyncio
async def test_service_area_crud_and_revive(db_session):
    from common.exceptions.base import AppException
    from service_area.service import ServiceAreaService
    from service_area.schemas.request import ServiceAreaCreateRequest, PaginateServiceAreaRequest
    from service_area.const.status import ServiceAreaKind

    team = await make_team(db_session)
    svc = ServiceAreaService(db_session, team.id)

    # STATE — value 생략 시 state 로 보정
    a1 = await svc.create(ServiceAreaCreateRequest(kind=ServiceAreaKind.STATE, state="ca"))
    assert a1.state == "CA" and a1.value == "CA"
    # ZIP3
    a2 = await svc.create(ServiceAreaCreateRequest(kind=ServiceAreaKind.ZIP3, state="CA", value="902"))
    assert a2.value == "902"
    # ZIP3 형식 검증
    with pytest.raises(pydantic.ValidationError):
        ServiceAreaCreateRequest(kind=ServiceAreaKind.ZIP3, state="CA", value="90a")
    # CITY 는 value 필수
    with pytest.raises(pydantic.ValidationError):
        ServiceAreaCreateRequest(kind=ServiceAreaKind.CITY, state="CA")

    # 중복 → 409
    with pytest.raises(AppException) as ei:
        await svc.create(ServiceAreaCreateRequest(kind=ServiceAreaKind.ZIP3, state="CA", value="902"))
    assert ei.value.code == "SERVICE_AREA_DUPLICATE"

    # 목록
    page = await svc.list_paginated(PaginateServiceAreaRequest())
    assert len(page.data) == 2

    # 삭제(소프트) → 재추가 시 같은 행 되살림 (uq 점유 충돌 없음)
    out = await svc.delete(a2.id)
    assert out.deleted
    a2b = await svc.create(ServiceAreaCreateRequest(kind=ServiceAreaKind.ZIP3, state="CA", value="902"))
    assert a2b.id == a2.id and a2b.is_active is True


@pytest.mark.asyncio
async def test_zip_search_scope_filter(db_session):
    from zip_code.repository import ZipCodeRepository
    from service_area.repository import ServiceAreaRepository
    from service_area.scope import zip_scope_conditions
    from service_area.model import ServiceAreaModel
    from service_area.const.status import ServiceAreaKind

    team = await make_team(db_session)
    # zip 마스터: 권역 내(902xx, Fontana/SB카운티) + 권역 밖(TX)
    _zip(db_session, zip="90210", city="Beverly Hills", state="CA", county="Los Angeles")
    _zip(db_session, zip="92335", city="Fontana", state="CA", county="San Bernardino")
    _zip(db_session, zip="75001", city="Addison", state="TX", county="Dallas")
    await db_session.flush()

    # 선언: ZIP3=902 + CITY=Fontana
    db_session.add_all([
        ServiceAreaModel(team_id=team.id, kind=ServiceAreaKind.ZIP3, state="CA", value="902"),
        ServiceAreaModel(team_id=team.id, kind=ServiceAreaKind.CITY, state="CA", value="fontana"),
    ])
    await db_session.flush()

    selections = await ServiceAreaRepository(db_session, team.id).list_active()
    conds = zip_scope_conditions(selections)
    repo = ZipCodeRepository(db_session)

    # 스코프 적용 — TX 제외, 902xx + Fontana 만
    rows = await repo.search(None, None, 50, scope_conds=conds)
    zips = {r.zip for r in rows}
    assert zips == {"90210", "92335"}

    # 스코프 미적용 — 전체
    rows_all = await repo.search(None, None, 50)
    assert {r.zip for r in rows_all} == {"90210", "92335", "75001"}

    # 도시 자동완성도 동일
    cities = await repo.search_cities(None, None, 50, scope_conds=conds)
    assert ("Addison", "TX") not in cities and ("Fontana", "CA") in cities

    # 선언 0건 팀 → 빈 조건 = 무필터
    team2 = await make_team(db_session)
    selections2 = await ServiceAreaRepository(db_session, team2.id).list_active()
    assert zip_scope_conditions(selections2) == []
