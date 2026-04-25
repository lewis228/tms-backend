from __future__ import annotations
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from customer.model import CustomerModel
from customer.repository import CustomerRepository
from customer.schemas.request import (
    CreateCustomerRequestSchema,
    UpdateCustomerRequestSchema,
)
from customer.schemas.response import CustomerResponseSchema
from common.exceptions.base import AppException, NotFoundException
from fastapi import status


class CustomerService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = CustomerRepository(db, team_id)

    async def list_customers(self) -> List[CustomerResponseSchema]:
        customers = await self.repo.list_by_team()
        return [CustomerResponseSchema.model_validate(c) for c in customers]

    async def create_customer(
        self,
        body: CreateCustomerRequestSchema,
        *,
        creator_user_id: int,
    ) -> CustomerResponseSchema:
        existing = await self.repo.get_by_name(body.name)
        if existing:
            raise AppException(
                code="CUSTOMER_DUPLICATE",
                message="같은 이름의 고객이 이미 존재합니다.",
                status_code=status.HTTP_409_CONFLICT,
            )
        customer = CustomerModel(
            name=body.name,
            created_by_user_id=creator_user_id,
            updated_by_user_id=creator_user_id,
        )
        customer = await self.repo.create(customer)
        return CustomerResponseSchema.model_validate(customer)

    async def update_customer(
        self,
        customer_id: int,
        body: UpdateCustomerRequestSchema,
        *,
        updater_user_id: int,
    ) -> CustomerResponseSchema:
        customer = await self.repo.get_by_id(customer_id)
        if not customer:
            raise NotFoundException("Customer")

        if body.name is not None and body.name != customer.name:
            collision = await self.repo.get_by_name(body.name)
            if collision and collision.id != customer.id:
                raise AppException(
                    code="CUSTOMER_DUPLICATE",
                    message="같은 이름의 고객이 이미 존재합니다.",
                    status_code=status.HTTP_409_CONFLICT,
                )
            customer.name = body.name
        customer.updated_by_user_id = updater_user_id
        await self.db.flush()
        await self.db.refresh(customer)
        return CustomerResponseSchema.model_validate(customer)

    async def delete_customer(self, customer_id: int) -> None:
        """Soft-delete. shipments.customer_id 는 ON DELETE SET NULL 이 아니라
        RESTRICT — 여기선 soft delete 만 하므로 연결된 shipment 가 있어도
        조회상 '없는 고객' 으로 보인다. 과거 첨부 기록은 감사용으로 FK 유지."""
        customer = await self.repo.get_by_id(customer_id)
        if not customer:
            raise NotFoundException("Customer")
        customer.is_active = False
        await self.db.flush()
