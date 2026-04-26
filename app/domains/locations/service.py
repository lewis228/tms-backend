"""Location 서비스."""
from __future__ import annotations

from sqlalchemy import or_

from app.core.exceptions import NotFoundError
from app.domains.locations.models import Location
from app.domains.locations.repository import LocationRepository
from app.domains.locations.schema import LocationCreateRequest, LocationUpdateRequest


class LocationService:
    def __init__(self, repo: LocationRepository, tenant_id: str) -> None:
        self.repo = repo
        self.tenant_id = tenant_id

    async def create(self, payload: LocationCreateRequest) -> Location:
        loc = Location(tenant_id=self.tenant_id, **payload.model_dump())
        await self.repo.create(loc)
        await self.repo.db.commit()
        await self.repo.db.refresh(loc)
        return loc

    async def get(self, id_: str) -> Location:
        loc = await self.repo.get_by_id(id_)
        if not loc:
            raise NotFoundError("Location not found")
        return loc

    async def list_paged(self, params, *, q: str | None = None):
        extra: list = []
        if q:
            like = f"%{q.strip()}%"
            extra.append(or_(Location.name.ilike(like), Location.address.ilike(like)))
        return await self.repo.list_paged(params, extra_where=extra or None)

    async def update(self, id_: str, payload: LocationUpdateRequest) -> Location:
        loc = await self.get(id_)
        await self.repo.update(loc, **payload.model_dump(exclude_unset=True))
        await self.repo.db.commit()
        await self.repo.db.refresh(loc)
        return loc

    async def delete(self, id_: str) -> None:
        loc = await self.get(id_)
        await self.repo.soft_delete(loc)
        await self.repo.db.commit()
