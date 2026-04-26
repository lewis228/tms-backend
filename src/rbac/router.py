# src/rbac/router.py
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from auth.tokens.access_token import access_token
from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncWithAllIdsResponse
from rbac.service import RbacService
from tenant.dependencies.get_tenant_scope import get_tenant_scope
from database.dependencies import get_read_db, get_write_db
from cache.dependencies import get_read_redis, get_write_redis
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema
from rbac.schemas.response import (
    PermissionGroupListItemResponseSchema,
    RbacMeResponseSchema,
    PermissionGroupDetailResponseSchema,
    PermissionGroupRenameResponseSchema,
    PermissionGroupDeleteResponseSchema,
)
from rbac.schemas.request import (
    PaginatePermissionGroupRequest,
    PermissionGroupCreateRequestSchema,
    PermissionGroupRenameRequestSchema,
    PermissionGroupSetCodesRequestSchema,
    PermissionGroupPatchCodesRequestSchema,
)
from rbac.dependencies.guards import permission_guard
from rbac.const.const import TENANT_MEMBER_PERMISSION_ASSIGN

router = APIRouter(prefix="/rbac", tags=["rbac"])


# ─────────────────────────────────────────────────────────
# ▼ 단일 엔드포인트: 내 권한 + abilities
# ─────────────────────────────────────────────────────────
@router.get("/me", response_model=RbacMeResponseSchema)
async def get_me(
    _1: None = Depends(access_token),                       # 1) 인증
    tenant_id: Optional[int] = Depends(get_tenant_scope),       # 2) 팀 컨텍스트(없을 수 있음)
    me: UserResponseSchema = Depends(get_current_user),     # 3) 실 사용자 정보
    db: AsyncSession = Depends(get_read_db),                # SELECT → get_read_db
    redis: Redis = Depends(get_read_redis),                 # 캐시 조회 → get_read_redis
):
    """
    현재 로그인 사용자의 RBAC 단일 응답.
    - codes: 사용자가 실제로 가진 권한 코드 목록
    - abilities: 모든 권한 코드에 대해 True/False 판정
    - rbac: permission_group_id, is_admin
    """
    svc = RbacService(db, redis)
    return await svc.get_me(
        user_id=int(me.id),
        tenant_id=tenant_id,
    )

# 현재 팀의 권한 그룹
@router.get("/groups", response_model=CursorPaginationResult[PermissionGroupListItemResponseSchema])
async def list_groups(
    request: PaginatePermissionGroupRequest = Depends(),    # 커서 페이지네이션 DTO
    _1: None = Depends(access_token),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),                # SELECT → get_read_db
    redis: Redis = Depends(get_read_redis),                 # 캐시 조회 → get_read_redis
):
    svc = RbacService(db, redis)
    return await svc.list_groups_paginated(tenant_id=tenant_id, request=request)

# ─────────────────────────────────────────────────────────
# ▼ Delta Sync: 권한 그룹 (hard-delete → all_ids)
# ─────────────────────────────────────────────────────────
@router.get("/groups/sync", response_model=SyncWithAllIdsResponse[PermissionGroupListItemResponseSchema])
async def sync_groups(
    since: str,
    _1: None = Depends(access_token),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),
    redis: Redis = Depends(get_read_redis),
):
    """권한 그룹 Delta Sync (since 이후 변경분 + 전체 활성 ID)"""
    svc = RbacService(db, redis)
    return await svc.sync_delta(tenant_id=tenant_id, since_str=since)

# 현재 팀의 권한 그룹의 상세
@router.get("/groups/{group_id}", response_model=PermissionGroupDetailResponseSchema)
async def get_group_detail(
    group_id: int,
    _1: None = Depends(access_token),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),                # SELECT → get_read_db
    redis: Redis = Depends(get_read_redis),                 # 캐시 조회 → get_read_redis
):
    """그룹 상세 + 코드 세트 조회."""
    svc = RbacService(db, redis)
    return await svc.get_group_detail(tenant_id=tenant_id, group_id=group_id)


@router.post("/groups", response_model=PermissionGroupDetailResponseSchema)
async def create_group(
    payload: PermissionGroupCreateRequestSchema,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TENANT_MEMBER_PERMISSION_ASSIGN)),  # 쓰기 권한 가드
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),               # INSERT → get_write_db
    redis: Redis = Depends(get_write_redis),                # 캐시 무효화 → get_write_redis
):
    """
    그룹 생성.
    - system_key는 None(커스텀 그룹)
    - 초기 코드 세트가 있으면 즉시 반영
    """
    svc = RbacService(db, redis)
    return await svc.create_group(tenant_id=tenant_id, payload=payload)


@router.put("/groups/{group_id}", response_model=PermissionGroupRenameResponseSchema)
async def rename_group(
    group_id: int,
    payload: PermissionGroupRenameRequestSchema,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TENANT_MEMBER_PERMISSION_ASSIGN)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),               # UPDATE → get_write_db
    redis: Redis = Depends(get_write_redis),                # 캐시 무효화 → get_write_redis
):
    """
    그룹 이름 변경.
    - 시스템 그룹은 서비스 레이어에서 차단.
    """
    svc = RbacService(db, redis)
    return await svc.rename_group(tenant_id=tenant_id, group_id=group_id, payload=payload)


@router.delete("/groups/{group_id}", response_model=PermissionGroupDeleteResponseSchema)
async def delete_group(
    group_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TENANT_MEMBER_PERMISSION_ASSIGN)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),               # DELETE → get_write_db
    redis: Redis = Depends(get_write_redis),                # 캐시 무효화 → get_write_redis
):
    """
    그룹 삭제.
    - 시스템 그룹/멤버 존재 그룹은 서비스에서 방어.
    """
    svc = RbacService(db, redis)
    return await svc.delete_group(tenant_id=tenant_id, group_id=group_id)


@router.put("/groups/{group_id}/codes", response_model=PermissionGroupDetailResponseSchema)
async def set_group_codes(
    group_id: int,
    payload: PermissionGroupSetCodesRequestSchema,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TENANT_MEMBER_PERMISSION_ASSIGN)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),               # UPDATE → get_write_db
    redis: Redis = Depends(get_write_redis),                # 캐시 무효화 → get_write_redis
):
    """
    권한 코드 '완전 교체'.
    - 캐시 무효화(invalidate_group_codes) 포함.
    """
    svc = RbacService(db, redis)
    return await svc.set_group_codes(tenant_id=tenant_id, group_id=group_id, payload=payload)


@router.post("/groups/{group_id}/codes", response_model=PermissionGroupDetailResponseSchema)
async def patch_group_codes(
    group_id: int,
    payload: PermissionGroupPatchCodesRequestSchema,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TENANT_MEMBER_PERMISSION_ASSIGN)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),               # UPDATE → get_write_db
    redis: Redis = Depends(get_write_redis),                # 캐시 무효화 → get_write_redis
):
    """
    권한 코드 '증감 패치'(op=add/remove).
    - 캐시 무효화 포함.
    """
    svc = RbacService(db, redis)
    return await svc.patch_group_codes(tenant_id=tenant_id, group_id=group_id, payload=payload)