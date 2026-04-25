"""Customer 서비스."""
from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.domains.customers.models import Customer
from app.domains.customers.repository import CustomerRepository
from app.domains.customers.schema import CustomerCreateRequest, CustomerUpdateRequest


class CustomerService:
    def __init__(self, repo: CustomerRepository, tenant_id: str) -> None:
        self.repo = repo
        self.tenant_id = tenant_id

    async def create(self, payload: CustomerCreateRequest) -> Customer:
        c = Customer(tenant_id=self.tenant_id, **payload.model_dump())
        await self.repo.create(c)
        await self.repo.db.commit()
        await self.repo.db.refresh(c)
        return c

    async def get(self, id_: str) -> Customer:
        c = await self.repo.get_by_id(id_)
        if not c:
            raise NotFoundError("Customer not found")
        return c

    async def list_paged(self, params):
        return await self.repo.list_paged(params)

    async def update(self, id_: str, payload: CustomerUpdateRequest) -> Customer:
        c = await self.get(id_)
        await self.repo.update(c, **payload.model_dump(exclude_unset=True))
        await self.repo.db.commit()
        await self.repo.db.refresh(c)
        return c

    async def delete(self, id_: str) -> None:
        c = await self.get(id_)
        await self.repo.soft_delete(c)
        await self.repo.db.commit()
