# src/zip_code/repository.py
from __future__ import annotations
from typing import List, Optional

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from zip_code.model import ZipCodeModel


class ZipCodeRepository:
    """전역 zip 마스터 조회 (팀 스코프 없음 — reference data)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, zip_id: int) -> Optional[ZipCodeModel]:
        return (await self.db.execute(
            select(ZipCodeModel).where(ZipCodeModel.id == zip_id)
        )).scalar_one_or_none()

    async def get_by_zip(self, zip_str: str) -> Optional[ZipCodeModel]:
        """zip 문자열 정확 매칭 — 해석 시 city 파생(zip→도시) 용."""
        return (await self.db.execute(
            select(ZipCodeModel).where(ZipCodeModel.zip == zip_str.strip()).limit(1)
        )).scalar_one_or_none()

    async def search(self, q: str | None, state: str | None, limit: int = 20) -> List[ZipCodeModel]:
        """zip 또는 city 부분일치 검색 (마스터폼 picker / 존 도시 autocomplete 공용)."""
        stmt = select(ZipCodeModel)
        if q:
            like = f"{q}%"
            stmt = stmt.where(
                (ZipCodeModel.zip.like(like)) | (ZipCodeModel.city.ilike(like))
            )
        if state:
            stmt = stmt.where(ZipCodeModel.state == state.upper())
        stmt = stmt.order_by(ZipCodeModel.state.asc(), ZipCodeModel.city.asc(), ZipCodeModel.zip.asc()).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def find_zips_by_city(self, city: str, state: str) -> List[str]:
        """(city, state) 정확매칭(대소문자 무시) → 그 도시의 모든 zip 문자열."""
        stmt = (
            select(ZipCodeModel.zip)
            .where(
                func.lower(ZipCodeModel.city) == city.strip().lower(),
                ZipCodeModel.state == state.strip().upper(),
            )
            .order_by(ZipCodeModel.zip.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def search_cities(self, q: str | None, state: str | None, limit: int = 20) -> List[tuple[str, str]]:
        """distinct (city, state) 자동완성용."""
        stmt = select(distinct(ZipCodeModel.city), ZipCodeModel.state)
        if q:
            stmt = stmt.where(ZipCodeModel.city.ilike(f"{q}%"))
        if state:
            stmt = stmt.where(ZipCodeModel.state == state.upper())
        stmt = stmt.order_by(ZipCodeModel.city.asc()).limit(limit)
        return [(c, s) for c, s in (await self.db.execute(stmt)).all()]
