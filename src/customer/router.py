# src/customer/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import CUSTOMER_WRITE
from rbac.dependencies.guards import permission_guard
from tenant.dependencies.get_tenant_scope import get_tenant_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from customer.service import CustomerService
from customer.schemas.request import (
    CustomerCreateRequest, CustomerUpdateRequest, PaginateCustomerRequest,
    CustomerBulkCreateRequest, CustomerBulkUpdateRequest, CustomerBulkDeleteRequest,
)
from customer.schemas.response import (
    CustomerResponseSchema, CustomerDeleteResponseSchema,
    CustomerBulkCreateResponseSchema, CustomerBulkUpdateResponseSchema, CustomerBulkDeleteResponseSchema,
)

router = APIRouter(prefix="/customers", tags=["customers"])


# ═══════════════════════════════════════════════════════════════
# 단건 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("", response_model=CustomerResponseSchema)
async def create_customer(
    body: CustomerCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CUSTOMER_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    고객사 생성
    - 쓰기 권한 필요
    """
    return await CustomerService(db, tenant_id).create(
        body,
        actor_user_id=int(me.id),
    )


@router.get("", response_model=CursorPaginationResult[CustomerResponseSchema])
async def list_customers(
    request: PaginateCustomerRequest = Depends(),
    _1: None = Depends(access_token),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    고객사 목록(커서 페이징)
    - 기본 활성만; include_inactive=True 로 비활성 포함
    - 정렬/필터는 DTO의 order__/where__ 파라미터 사용
    """
    return await CustomerService(db, tenant_id).list_paginated(request)


# ═══════════════════════════════════════════════════════════════
# Delta Sync
# /{customer_id}보다 먼저 정의해야 "sync"가 customer_id로 파싱되지 않음
# ═══════════════════════════════════════════════════════════════

@router.get("/sync", response_model=SyncResponse[CustomerResponseSchema])
async def sync_customers(
    since: str,
    _1: None = Depends(access_token),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    고객사 Delta Sync

    - since 이후 변경된 활성 아이템 + soft-delete된 아이템 ID 반환
    """
    return await CustomerService(db, tenant_id).sync_delta(since)


@router.get("/{customer_id}", response_model=CustomerResponseSchema)
async def get_customer(
    customer_id: int,
    _1: None = Depends(access_token),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    고객사 단건 조회(활성만)
    """
    return await CustomerService(db, tenant_id).get(customer_id)


@router.put("/{customer_id}", response_model=CustomerResponseSchema)
async def update_customer(
    customer_id: int,
    body: CustomerUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CUSTOMER_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    고객사 수정(활성만)
    - 쓰기 권한 필요
    """
    return await CustomerService(db, tenant_id).update(
        customer_id,
        body,
        actor_user_id=int(me.id),
    )


@router.delete("/{customer_id}", response_model=CustomerDeleteResponseSchema)
async def delete_customer(
    customer_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CUSTOMER_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    고객사 삭제
    - 하드 삭제 우선, FK 제약 시 소프트 비활성화
    """
    return await CustomerService(db, tenant_id).delete(
        customer_id,
        actor_user_id=int(me.id),
    )


# ═══════════════════════════════════════════════════════════════
# 벌크 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("/bulk/create", response_model=CustomerBulkCreateResponseSchema)
async def create_customers_bulk(
    body: CustomerBulkCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CUSTOMER_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    고객사 벌크 생성 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 부분 성공 허용
    """
    return await CustomerService(db, tenant_id).create_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/update", response_model=CustomerBulkUpdateResponseSchema)
async def update_customers_bulk(
    body: CustomerBulkUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CUSTOMER_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    고객사 벌크 수정 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 존재하지 않는 ID는 실패 처리
    """
    return await CustomerService(db, tenant_id).update_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/delete", response_model=CustomerBulkDeleteResponseSchema)
async def delete_customers_bulk(
    body: CustomerBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CUSTOMER_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    고객사 벌크 삭제 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 하드 삭제 우선, FK 제약 시 소프트 삭제
    """
    return await CustomerService(db, tenant_id).delete_bulk(
        body,
        actor_user_id=int(me.id),
    )