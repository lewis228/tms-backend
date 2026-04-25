from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database.dependencies import get_write_db, get_read_db
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from auth.dependencies.rate_limit import rate_limit
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema
from customer.schemas.request import (
    CreateCustomerRequestSchema,
    UpdateCustomerRequestSchema,
)
from customer.schemas.response import CustomerResponseSchema
from customer.service import CustomerService

router = APIRouter(prefix="/api/v1/customers", tags=["customer"])


@router.get("", response_model=List[CustomerResponseSchema])
async def list_customers(
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    svc = CustomerService(db, team_id)
    return await svc.list_customers()


@router.post("", response_model=CustomerResponseSchema, status_code=201)
async def create_customer(
    body: CreateCustomerRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    svc = CustomerService(db, team_id)
    return await svc.create_customer(body, creator_user_id=me.id)


@router.patch("/{customer_id}", response_model=CustomerResponseSchema)
async def update_customer(
    customer_id: int,
    body: UpdateCustomerRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    svc = CustomerService(db, team_id)
    return await svc.update_customer(customer_id, body, updater_user_id=me.id)


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(
    customer_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    svc = CustomerService(db, team_id)
    await svc.delete_customer(customer_id)
