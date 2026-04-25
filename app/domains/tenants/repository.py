"""Tenant Repository — Tenant 자체는 tenant_id 가 없으므로 BaseRepository 의 자동 필터 사용 안 함."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.tenants.models import Tenant


class TenantRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, tenant_id: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.id == tenant_id, Tenant.is_deleted.is_(False))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.slug == slug, Tenant.is_deleted.is_(False))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> list[Tenant]:
        stmt = select(Tenant).where(Tenant.is_deleted.is_(False)).order_by(Tenant.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def add(self, tenant: Tenant) -> Tenant:
        self.db.add(tenant)
        await self.db.flush()
        return tenant

    async def soft_delete(self, tenant: Tenant) -> None:
        tenant.is_deleted = True
        await self.db.flush()
