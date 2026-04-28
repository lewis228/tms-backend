# src/delivery_order/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import DO_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from delivery_order.service import DeliveryOrderService
from delivery_order.schemas.request import (
    DeliveryOrderTransitionRequest,
    DeliveryOrderCreateRequest, DeliveryOrderUpdateRequest, PaginateDeliveryOrderRequest,
    DeliveryOrderBulkCreateRequest, DeliveryOrderBulkUpdateRequest, DeliveryOrderBulkDeleteRequest,
)
from delivery_order.schemas.response import (
    DeliveryOrderResponseSchema, DeliveryOrderDetailResponseSchema, DeliveryOrderDeleteResponseSchema,
    DeliveryOrderBulkCreateResponseSchema, DeliveryOrderBulkUpdateResponseSchema, DeliveryOrderBulkDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/delivery-orders", tags=["delivery-orders"])


# ═══════════════════════════════════════════════════════════════
# 단건 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("", response_model=DeliveryOrderDetailResponseSchema)
async def create_delivery_order(
    body: DeliveryOrderCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 생성
    - 쓰기 권한 필요
    """
    return await DeliveryOrderService(db, team_id).create(
        body,
        actor_user_id=int(me.id),
    )


@router.get("", response_model=CursorPaginationResult[DeliveryOrderResponseSchema])
async def list_delivery_orders(
    request: PaginateDeliveryOrderRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 목록(커서 페이징)
    - 기본 활성만; include_inactive=True 로 비활성 포함
    - 정렬/필터는 DTO의 order__/where__ 파라미터 사용
    """
    return await DeliveryOrderService(db, team_id).list_paginated(request)


# ═══════════════════════════════════════════════════════════════
# Delta Sync
# /{delivery_order_id}보다 먼저 정의해야 "sync"가 delivery_order_id로 파싱되지 않음
# ═══════════════════════════════════════════════════════════════

@router.get("/sync", response_model=SyncResponse[DeliveryOrderResponseSchema])
async def sync_delivery_orders(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 Delta Sync

    - since 이후 변경된 활성 아이템 + soft-delete된 아이템 ID 반환
    """
    return await DeliveryOrderService(db, team_id).sync_delta(since)


@router.get("/{delivery_order_id}", response_model=DeliveryOrderDetailResponseSchema)
async def get_delivery_order(
    delivery_order_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 단건 조회(활성만)
    """
    return await DeliveryOrderService(db, team_id).get(delivery_order_id)


@router.put("/{delivery_order_id}", response_model=DeliveryOrderResponseSchema)
async def update_delivery_order(
    delivery_order_id: int,
    body: DeliveryOrderUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 수정(활성만)
    - 쓰기 권한 필요
    """
    return await DeliveryOrderService(db, team_id).update(
        delivery_order_id,
        body,
        actor_user_id=int(me.id),
    )


@router.delete("/{delivery_order_id}", response_model=DeliveryOrderDeleteResponseSchema)
async def delete_delivery_order(
    delivery_order_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 삭제
    - 하드 삭제 우선, FK 제약 시 소프트 비활성화
    """
    return await DeliveryOrderService(db, team_id).delete(
        delivery_order_id,
        actor_user_id=int(me.id),
    )


# ═══════════════════════════════════════════════════════════════
# 벌크 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("/bulk/create", response_model=DeliveryOrderBulkCreateResponseSchema)
async def create_delivery_orders_bulk(
    body: DeliveryOrderBulkCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 생성 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 부분 성공 허용
    """
    return await DeliveryOrderService(db, team_id).create_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/update", response_model=DeliveryOrderBulkUpdateResponseSchema)
async def update_delivery_orders_bulk(
    body: DeliveryOrderBulkUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 수정 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 존재하지 않는 ID는 실패 처리
    """
    return await DeliveryOrderService(db, team_id).update_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/delete", response_model=DeliveryOrderBulkDeleteResponseSchema)
async def delete_delivery_orders_bulk(
    body: DeliveryOrderBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 삭제 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 하드 삭제 우선, FK 제약 시 소프트 삭제
    """
    return await DeliveryOrderService(db, team_id).delete_bulk(
        body,
        actor_user_id=int(me.id),
    )

# ═══════════════════════════════════════════════════════════════
# 상태 전이 — DO_TRANSITION 권한
# ═══════════════════════════════════════════════════════════════

@router.post("/{delivery_order_id}/transition", response_model=DeliveryOrderResponseSchema)
async def transition_delivery_order(
    delivery_order_id: int,
    body: "DeliveryOrderTransitionRequest",
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard("DO_TRANSITION")),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """D/O 상태 전이. 게이트 검증은 service 가 수행."""
    return await DeliveryOrderService(db, team_id).transition(
        delivery_order_id, body.target, actor_user_id=int(me.id),
    )
