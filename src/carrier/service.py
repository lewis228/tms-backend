from __future__ import annotations
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from carrier.repository import CarrierRepository
from carrier.schemas.response import CarrierResponseSchema


class CarrierService:
    """전역 carrier 조회 서비스. 현재는 read-only — 선사 CRUD 는 마이그레이션
    시 seed 로 투입되며 필요 시 추후 admin 엔드포인트에서 확장."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CarrierRepository(db)

    async def list_carriers(
        self,
        *,
        supported_only: bool = True,
        scrapable_only: bool = False,
        search: Optional[str] = None,
    ) -> List[CarrierResponseSchema]:
        carriers = await self.repo.list_carriers(
            supported_only=supported_only,
            scrapable_only=scrapable_only,
            search=search,
        )
        return [CarrierResponseSchema.model_validate(c) for c in carriers]
