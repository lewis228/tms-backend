"""Tenant 서비스 — 생성/조회/갱신/삭제 + slug 충돌 체크."""
from __future__ import annotations

from app.core.exceptions import ConflictError, NotFoundError
from app.domains.tenants.models import Tenant
from app.domains.tenants.repository import TenantRepository
from app.domains.tenants.schema import TenantCreateRequest, TenantUpdateRequest


class TenantService:
    def __init__(self, repo: TenantRepository) -> None:
        self.repo = repo

    async def create(self, payload: TenantCreateRequest) -> Tenant:
        if await self.repo.get_by_slug(payload.slug):
            raise ConflictError(f"Slug '{payload.slug}' already exists")
        tenant = Tenant(
            name=payload.name,
            slug=payload.slug,
            plan_tier=payload.plan_tier,
            timezone=payload.timezone,
            contact_email=payload.contact_email,
            contact_phone=payload.contact_phone,
        )
        await self.repo.add(tenant)
        await self.repo.db.commit()
        await self.repo.db.refresh(tenant)
        return tenant

    async def get(self, tenant_id: str) -> Tenant:
        tenant = await self.repo.get(tenant_id)
        if not tenant:
            raise NotFoundError("Tenant not found")
        return tenant

    async def list_all(self) -> list[Tenant]:
        return await self.repo.list_all()

    async def update(self, tenant_id: str, payload: TenantUpdateRequest) -> Tenant:
        tenant = await self.get(tenant_id)
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(tenant, k, v)
        await self.repo.db.flush()
        await self.repo.db.commit()
        await self.repo.db.refresh(tenant)
        return tenant

    async def delete(self, tenant_id: str) -> None:
        tenant = await self.get(tenant_id)
        await self.repo.soft_delete(tenant)
        await self.repo.db.commit()
