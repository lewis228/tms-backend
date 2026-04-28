# src/street_turn/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import STREET_TURN_WRITE, STREET_TURN_APPROVE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from street_turn.service import StreetTurnService
from street_turn.schemas.request import (
    StreetTurnCreateRequest, StreetTurnUpdateRequest, PaginateStreetTurnRequest,
    StreetTurnBulkCreateRequest, StreetTurnBulkUpdateRequest, StreetTurnBulkDeleteRequest,
    StreetTurnApproveRequest, StreetTurnRejectRequest,
)
from street_turn.schemas.response import (
    StreetTurnResponseSchema, StreetTurnDeleteResponseSchema,
    StreetTurnBulkCreateResponseSchema, StreetTurnBulkUpdateResponseSchema, StreetTurnBulkDeleteResponseSchema,
)
from street_turn.schemas.candidates import StreetTurnCandidatesResponse

router = APIRouter(prefix="/api/v1/street-turns", tags=["street-turns"])


# ═══════════════════════════════════════════════════════════════
# 단건 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("", response_model=StreetTurnResponseSchema)
async def create_street_turn(
    body: StreetTurnCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(STREET_TURN_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 생성
    - 쓰기 권한 필요
    """
    return await StreetTurnService(db, team_id).create(
        body,
        actor_user_id=int(me.id),
    )


@router.get("", response_model=CursorPaginationResult[StreetTurnResponseSchema])
async def list_street_turns(
    request: PaginateStreetTurnRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 목록(커서 페이징)
    - 기본 활성만; include_inactive=True 로 비활성 포함
    - 정렬/필터는 DTO의 order__/where__ 파라미터 사용
    """
    return await StreetTurnService(db, team_id).list_paginated(request)


# ═══════════════════════════════════════════════════════════════
# Delta Sync
# /{street_turn_id}보다 먼저 정의해야 "sync"가 street_turn_id로 파싱되지 않음
# ═══════════════════════════════════════════════════════════════

@router.get("/candidates", response_model=StreetTurnCandidatesResponse)
async def list_street_turn_candidates(
    limit: int = 20,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    Street Turn 후보 추천 (H-11)
    - 매칭 가능한 IMPORT 컨테이너 X EXPORT D/O 페어
    - score 내림차순. estimated_saving 포함.
    """
    return await StreetTurnService(db, team_id).candidates(limit)


@router.get("/sync", response_model=SyncResponse[StreetTurnResponseSchema])
async def sync_street_turns(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 Delta Sync

    - since 이후 변경된 활성 아이템 + soft-delete된 아이템 ID 반환
    """
    return await StreetTurnService(db, team_id).sync_delta(since)


@router.get("/{street_turn_id}", response_model=StreetTurnResponseSchema)
async def get_street_turn(
    street_turn_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 단건 조회(활성만)
    """
    return await StreetTurnService(db, team_id).get(street_turn_id)


@router.put("/{street_turn_id}", response_model=StreetTurnResponseSchema)
async def update_street_turn(
    street_turn_id: int,
    body: StreetTurnUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(STREET_TURN_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 수정(활성만)
    - 쓰기 권한 필요
    """
    return await StreetTurnService(db, team_id).update(
        street_turn_id,
        body,
        actor_user_id=int(me.id),
    )


@router.delete("/{street_turn_id}", response_model=StreetTurnDeleteResponseSchema)
async def delete_street_turn(
    street_turn_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(STREET_TURN_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 삭제
    - 하드 삭제 우선, FK 제약 시 소프트 비활성화
    """
    return await StreetTurnService(db, team_id).delete(
        street_turn_id,
        actor_user_id=int(me.id),
    )


# ═══════════════════════════════════════════════════════════════
# 벌크 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("/bulk/create", response_model=StreetTurnBulkCreateResponseSchema)
async def create_street_turns_bulk(
    body: StreetTurnBulkCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(STREET_TURN_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 생성 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 부분 성공 허용
    """
    return await StreetTurnService(db, team_id).create_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/update", response_model=StreetTurnBulkUpdateResponseSchema)
async def update_street_turns_bulk(
    body: StreetTurnBulkUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(STREET_TURN_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 수정 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 존재하지 않는 ID는 실패 처리
    """
    return await StreetTurnService(db, team_id).update_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/delete", response_model=StreetTurnBulkDeleteResponseSchema)
async def delete_street_turns_bulk(
    body: StreetTurnBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(STREET_TURN_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 삭제 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 하드 삭제 우선, FK 제약 시 소프트 삭제
    """
    return await StreetTurnService(db, team_id).delete_bulk(
        body,
        actor_user_id=int(me.id),
    )


# ═══════════════════════════════════════════════════════════════
# 승인 워크플로우 (REQUESTED → APPROVED / REJECTED / CANCELLED)
# ═══════════════════════════════════════════════════════════════

@router.post("/{street_turn_id}/approve", response_model=StreetTurnResponseSchema)
async def approve_street_turn(
    street_turn_id: int,
    body: StreetTurnApproveRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(STREET_TURN_APPROVE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    Street Turn 승인
    - REQUESTED 상태에서만 가능
    - 승인 시 container_event(STREET_TURNED) 자동 기록
    """
    return await StreetTurnService(db, team_id).approve(
        street_turn_id,
        carrier_approval_no=body.carrier_approval_no,
        actor_user_id=int(me.id),
    )


@router.post("/{street_turn_id}/reject", response_model=StreetTurnResponseSchema)
async def reject_street_turn(
    street_turn_id: int,
    body: StreetTurnRejectRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(STREET_TURN_APPROVE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    Street Turn 거절
    - REQUESTED 상태에서만 가능
    """
    return await StreetTurnService(db, team_id).reject(
        street_turn_id,
        reason=body.reason,
        actor_user_id=int(me.id),
    )


@router.post("/{street_turn_id}/cancel", response_model=StreetTurnResponseSchema)
async def cancel_street_turn(
    street_turn_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(STREET_TURN_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    Street Turn 취소
    - 요청자가 본인 요청을 거두는 경우
    """
    return await StreetTurnService(db, team_id).cancel(
        street_turn_id,
        actor_user_id=int(me.id),
    )