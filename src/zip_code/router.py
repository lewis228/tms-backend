# src/zip_code/router.py
from __future__ import annotations
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db
from zip_code.repository import ZipCodeRepository
from zip_code.schemas.response import ZipCodeResponseSchema, CitySuggestionSchema

router = APIRouter(prefix="/api/v1/zip-codes", tags=["zip-codes"])


@router.get("", response_model=List[ZipCodeResponseSchema])
async def search_zip_codes(
    q: str | None = None,
    state: str | None = None,
    limit: int = 20,
    _1: None = Depends(access_token),
    db: AsyncSession = Depends(get_read_db),
):
    """zip / city 부분일치 검색 (마스터 폼 zip picker). 전역 reference."""
    rows = await ZipCodeRepository(db).search(q, state, min(limit, 50))
    return [ZipCodeResponseSchema.model_validate(r) for r in rows]


# /cities 는 /{zip_id} 보다 먼저 — 그래야 "cities" 가 int 파싱 안 됨
@router.get("/cities", response_model=List[CitySuggestionSchema])
async def search_cities(
    q: str | None = None,
    state: str | None = None,
    limit: int = 20,
    _1: None = Depends(access_token),
    db: AsyncSession = Depends(get_read_db),
):
    """distinct (city, state) 자동완성 (존 '도시로 추가' 입력 보조)."""
    rows = await ZipCodeRepository(db).search_cities(q, state, min(limit, 50))
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
