# src/api_key/router.py
from __future__ import annotations
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import API_KEY_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from api_key.service import ApiKeyService
from api_key.schemas.request import (
    CreateApiKeyRequestSchema,
    UpdateApiKeyRequestSchema,
)
from api_key.schemas.response import (
    ApiKeyListItemResponseSchema,
    ApiKeyCreatedResponseSchema,
    ApiKeyDeleteResponseSchema,
)


router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


# ═══════════════════════════════════════════════════════════════
# 단건 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("", response_model=ApiKeyCreatedResponseSchema, status_code=201)
async def create_api_key(
    body: CreateApiKeyRequestSchema,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(API_KEY_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    새 API 키 발급. 전체 ``key`` 값은 이 응답에서만 노출되고 이후로는 절대
    재조회 불가 — 클라이언트가 즉시 저장해야 한다.
    """
    return await ApiKeyService(db, team_id).create(
        name=body.name,
        description=body.description,
        expires_in_days=body.expires_in_days,
        created_by_user_id=int(me.id),
    )


@router.get("", response_model=List[ApiKeyListItemResponseSchema])
async def list_api_keys(
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """API 키 목록(활성만)."""
    return await ApiKeyService(db, team_id).list_by_team()


@router.get("/{api_key_id}", response_model=ApiKeyListItemResponseSchema)
async def get_api_key(
    api_key_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """API 키 단건 조회(활성만)."""
    return await ApiKeyService(db, team_id).get(api_key_id)


@router.patch("/{api_key_id}", response_model=ApiKeyListItemResponseSchema)
async def update_api_key(
    api_key_id: int,
    body: UpdateApiKeyRequestSchema,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(API_KEY_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """name/description 만 변경 가능. 시크릿 자체는 회수 후 재발급."""
    return await ApiKeyService(db, team_id).update(
        api_key_id,
        name=body.name,
        description=body.description,
        actor_user_id=int(me.id),
    )


@router.delete("/{api_key_id}", response_model=ApiKeyDeleteResponseSchema)
async def revoke_api_key(
    api_key_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(API_KEY_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """소프트 삭제(회수). row 는 유지되며 is_active=False 로 마킹,
    ``updated_at`` 이 회수 시점으로 갱신. 인증 경로는 ``is_active=True`` 만 통과."""
    await ApiKeyService(db, team_id).revoke(api_key_id, actor_user_id=int(me.id))
    return ApiKeyDeleteResponseSchema(id=api_key_id, revoked=True)
