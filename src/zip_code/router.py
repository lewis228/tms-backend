# src/zip_code/router.py
from __future__ import annotations
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db
from team.dependencies.get_team_scope import get_team_scope_optional
from zip_code.repository import ZipCodeRepository
from zip_code.schemas.response import ZipCodeResponseSchema, CitySuggestionSchema

router = APIRouter(prefix="/api/v1/zip-codes", tags=["zip-codes"])


async def _scope_conds(db: AsyncSession, team_id: int) -> list:
    """팀의 영업권역 선언 → zip 검색 OR 조건 (선언 0건이면 빈 리스트 = 무필터)."""
    from service_area.repository import ServiceAreaRepository
    from service_area.scope import zip_scope_conditions
    selections = await ServiceAreaRepository(db, team_id).list_active()
    return zip_scope_conditions(selections)


@router.get("", response_model=List[ZipCodeResponseSchema])
async def search_zip_codes(
    q: str | None = None,
    state: str | None = None,
    limit: int = 20,
    scope: bool = Query(False, description="true 면 팀 영업권역 내로 제한"),
    _1: None = Depends(access_token),
    team_id: int | None = Depends(get_team_scope_optional),
    db: AsyncSession = Depends(get_read_db),
):
    """zip / city 부분일치 검색 (마스터 폼 zip picker). 전역 reference.

    scope=true: 팀의 영업권역(Service Area) 선언 범위로 결과 제한 (선언 없으면 전체).
    팀 컨텍스트는 선택 — X-Team-Id 없으면 scope 무시(기존 전역 계약 유지).
    """
    conds = await _scope_conds(db, team_id) if (scope and team_id is not None) else None
    rows = await ZipCodeRepository(db).search(q, state, min(limit, 50), scope_conds=conds)
    return [ZipCodeResponseSchema.model_validate(r) for r in rows]


# /cities 는 /{zip_id} 보다 먼저 — 그래야 "cities" 가 int 파싱 안 됨
@router.get("/cities", response_model=List[CitySuggestionSchema])
async def search_cities(
    q: str | None = None,
    state: str | None = None,
    limit: int = 20,
    scope: bool = Query(False, description="true 면 팀 영업권역 내로 제한"),
    _1: None = Depends(access_token),
    team_id: int | None = Depends(get_team_scope_optional),
    db: AsyncSession = Depends(get_read_db),
):
    """distinct (city, state) 자동완성 (존 '도시로 추가' 입력 보조)."""
    conds = await _scope_conds(db, team_id) if (scope and team_id is not None) else None
    rows = await ZipCodeRepository(db).search_cities(q, state, min(limit, 50), scope_conds=conds)
    return [CitySuggestionSchema(city=c, state=s) for c, s in rows]


@router.get("/{zip_id}", response_model=ZipCodeResponseSchema)
async def get_zip_code(
    zip_id: int,
    _1: None = Depends(access_token),
    db: AsyncSession = Depends(get_read_db),
):
    """zip 단건(마스터 폼 picker 의 현재값 라벨 해석용)."""
    from common.exceptions.base import NotFoundException
    row = await ZipCodeRepository(db).get(zip_id)
    if not row:
        raise NotFoundException("ZipCode")
    return ZipCodeResponseSchema.model_validate(row)
