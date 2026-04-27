# src/settlement/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import SETTLEMENT_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from settlement.service import SettlementService
from settlement.schemas.request import (
    SettlementCalculateRequest, SettlementAdjustRequest,
    SettlementApproveRequest, SettlementUnapproveRequest,
    SettlementCreateRequest, SettlementUpdateRequest, PaginateSettlementRequest,
    SettlementBulkCreateRequest, SettlementBulkUpdateRequest, SettlementBulkDeleteRequest,
)
from settlement.schemas.response import (
    SettlementResponseSchema, SettlementDeleteResponseSchema,
    SettlementBulkCreateResponseSchema, SettlementBulkUpdateResponseSchema, SettlementBulkDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/settlements", tags=["settlements"])


# ═══════════════════════════════════════════════════════════════
# 단건 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("", response_model=SettlementResponseSchema)
async def create_settlement(
    body: SettlementCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 생성
    - 쓰기 권한 필요
    """
    return await SettlementService(db, team_id).create(
        body,
        actor_user_id=int(me.id),
    )


@router.get("", response_model=CursorPaginationResult[SettlementResponseSchema])
async def list_settlements(
    request: PaginateSettlementRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 목록(커서 페이징)
    - 기본 활성만; include_inactive=True 로 비활성 포함
    - 정렬/필터는 DTO의 order__/where__ 파라미터 사용
    """
    return await SettlementService(db, team_id).list_paginated(request)


# ═══════════════════════════════════════════════════════════════
# Delta Sync
# /{settlement_id}보다 먼저 정의해야 "sync"가 settlement_id로 파싱되지 않음
# ═══════════════════════════════════════════════════════════════

@router.get("/sync", response_model=SyncResponse[SettlementResponseSchema])
async def sync_settlements(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 Delta Sync

    - since 이후 변경된 활성 아이템 + soft-delete된 아이템 ID 반환
    """
    return await SettlementService(db, team_id).sync_delta(since)


@router.get("/{settlement_id}", response_model=SettlementResponseSchema)
async def get_settlement(
    settlement_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 단건 조회(활성만)
    """
    return await SettlementService(db, team_id).get(settlement_id)


@router.put("/{settlement_id}", response_model=SettlementResponseSchema)
async def update_settlement(
    settlement_id: int,
    body: SettlementUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 수정(활성만)
    - 쓰기 권한 필요
    """
    return await SettlementService(db, team_id).update(
        settlement_id,
        body,
        actor_user_id=int(me.id),
    )


@router.delete("/{settlement_id}", response_model=SettlementDeleteResponseSchema)
async def delete_settlement(
    settlement_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 삭제
    - 하드 삭제 우선, FK 제약 시 소프트 비활성화
    """
    return await SettlementService(db, team_id).delete(
        settlement_id,
        actor_user_id=int(me.id),
    )


# ═══════════════════════════════════════════════════════════════
# 벌크 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("/bulk/create", response_model=SettlementBulkCreateResponseSchema)
async def create_settlements_bulk(
    body: SettlementBulkCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 생성 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 부분 성공 허용
    """
    return await SettlementService(db, team_id).create_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/update", response_model=SettlementBulkUpdateResponseSchema)
async def update_settlements_bulk(
    body: SettlementBulkUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 수정 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 존재하지 않는 ID는 실패 처리
    """
    return await SettlementService(db, team_id).update_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/delete", response_model=SettlementBulkDeleteResponseSchema)
async def delete_settlements_bulk(
    body: SettlementBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 삭제 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 하드 삭제 우선, FK 제약 시 소프트 삭제
    """
    return await SettlementService(db, team_id).delete_bulk(
        body,
        actor_user_id=int(me.id),
    )

# ═══════════════════════════════════════════════════════════════
# 라이프사이클 — calculate / adjust / approve / unapprove
# ═══════════════════════════════════════════════════════════════

@router.post("/{settlement_id}/calculate", response_model=SettlementResponseSchema)
async def calculate_settlement(
    settlement_id: int,
    body: "SettlementCalculateRequest",
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard("SETTLEMENT_CALCULATE")),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await SettlementService(db, team_id).calculate(
        settlement_id, body, actor_user_id=int(me.id),
    )


@router.post("/{settlement_id}/adjust", response_model=SettlementResponseSchema)
async def adjust_settlement(
    settlement_id: int,
    body: "SettlementAdjustRequest",
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard("SETTLEMENT_ADJUST")),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await SettlementService(db, team_id).adjust(
        settlement_id, body, actor_user_id=int(me.id),
    )


@router.post("/{settlement_id}/approve", response_model=SettlementResponseSchema)
async def approve_settlement(
    settlement_id: int,
    body: "SettlementApproveRequest",
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard("SETTLEMENT_APPROVE")),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await SettlementService(db, team_id).approve(
        settlement_id, body, actor_user_id=int(me.id),
    )


@router.post("/{settlement_id}/unapprove", response_model=SettlementResponseSchema)
async def unapprove_settlement(
    settlement_id: int,
    body: "SettlementUnapproveRequest",
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard("SETTLEMENT_UNAPPROVE")),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await SettlementService(db, team_id).unapprove(
        settlement_id, body, actor_user_id=int(me.id),
    )
