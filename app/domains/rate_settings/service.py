"""RateSetting 서비스."""
from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.domains.rate_settings.models import RateSetting
from app.domains.rate_settings.repository import RateSettingRepository
from app.domains.rate_settings.schema import (
    RateSettingCreateRequest,
    RateSettingUpdateRequest,
)


class RateSettingService:
    def __init__(self, repo: RateSettingRepository, tenant_id: str) -> None:
        self.repo = repo
        self.tenant_id = tenant_id

    async def create(self, payload: RateSettingCreateRequest) -> RateSetting:
        rs = RateSetting(tenant_id=self.tenant_id, **payload.model_dump())
        await self.repo.create(rs)
        await self.repo.db.commit()
        await self.repo.db.refresh(rs)
        return rs

    async def get(self, id_: str) -> RateSetting:
        rs = await self.repo.get_by_id(id_)
        if not rs:
            raise NotFoundError("Rate setting not found")
        return rs

    async def list_paged(self, params):
        return await self.repo.list_paged(params)

    async def update(self, id_: str, payload: RateSettingUpdateRequest) -> RateSetting:
        rs = await self.get(id_)
        await self.repo.update(rs, **payload.model_dump(exclude_unset=True))
        await self.repo.db.commit()
        await self.repo.db.refresh(rs)
        return rs

    async def delete(self, id_: str) -> None:
        rs = await self.get(id_)
        await self.repo.soft_delete(rs)
        await self.repo.db.commit()
