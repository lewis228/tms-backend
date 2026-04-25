"""Vessel 서비스."""
from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.domains.vessels.models import Vessel
from app.domains.vessels.repository import VesselRepository
from app.domains.vessels.schema import VesselCreateRequest, VesselUpdateRequest


class VesselService:
    def __init__(self, repo: VesselRepository, tenant_id: str) -> None:
        self.repo = repo
        self.tenant_id = tenant_id

    async def create(self, payload: VesselCreateRequest) -> Vessel:
        v = Vessel(tenant_id=self.tenant_id, **payload.model_dump())
        await self.repo.create(v)
        await self.repo.db.commit()
        await self.repo.db.refresh(v)
        return v

    async def get(self, id_: str) -> Vessel:
        v = await self.repo.get_by_id(id_)
        if not v:
            raise NotFoundError("Vessel not found")
        return v

    async def list_paged(self, params):
        return await self.repo.list_paged(params)

    async def update(self, id_: str, payload: VesselUpdateRequest) -> Vessel:
        v = await self.get(id_)
        await self.repo.update(v, **payload.model_dump(exclude_unset=True))
        await self.repo.db.commit()
        await self.repo.db.refresh(v)
        return v

    async def delete(self, id_: str) -> None:
        v = await self.get(id_)
        await self.repo.soft_delete(v)
        await self.repo.db.commit()
