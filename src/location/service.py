from __future__ import annotations
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from location.repository import LocationRepository
from location.schemas.response import LocationResponseSchema


class LocationService:
    """전역 location 조회 서비스. write 는 마이그레이션 seed + 매퍼가 담당."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LocationRepository(db)

    async def search(
        self,
        *,
        search: Optional[str] = None,
        country_code: Optional[str] = None,
        kind: Optional[str] = None,
        supported_only: bool = True,
        limit: int = 50,
    ) -> List[LocationResponseSchema]:
        rows = await self.repo.search(
            search=search,
            country_code=country_code,
            kind=kind,
            supported_only=supported_only,
            limit=limit,
        )
        return [LocationResponseSchema.model_validate(r) for r in rows]
