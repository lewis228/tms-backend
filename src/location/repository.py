from __future__ import annotations
from typing import List, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from location.model import LocationModel


class LocationRepository:
    """전역 location 레포. 팀 스코프 무관."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        *,
        search: Optional[str] = None,
        country_code: Optional[str] = None,
        kind: Optional[str] = None,
        supported_only: bool = True,
        limit: int = 50,
    ) -> List[LocationModel]:
        stmt = select(LocationModel).where(LocationModel.is_active.is_(True))
        if supported_only:
            stmt = stmt.where(LocationModel.is_supported.is_(True))
        if country_code:
            stmt = stmt.where(LocationModel.country_code == country_code.upper())
        if kind:
            stmt = stmt.where(LocationModel.kind == kind)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    LocationModel.name.ilike(pattern),
                    LocationModel.unlocode.ilike(pattern),
                    LocationModel.iata.ilike(pattern),
                )
            )
        stmt = stmt.order_by(LocationModel.name.asc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, location_id: int) -> Optional[LocationModel]:
        stmt = select(LocationModel).where(
            LocationModel.id == location_id,
            LocationModel.is_active.is_(True),
        )
        return await self.db.scalar(stmt)

    async def get_by_unlocode(self, unlocode: str) -> Optional[LocationModel]:
        stmt = select(LocationModel).where(
            LocationModel.unlocode == unlocode.upper(),
            LocationModel.is_active.is_(True),
        )
        return await self.db.scalar(stmt)
