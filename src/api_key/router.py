from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from database.dependencies import get_write_db, get_read_db
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from auth.dependencies.rate_limit import rate_limit
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema
from api_key.schemas.request import (
    CreateApiKeyRequestSchema,
    UpdateApiKeyRequestSchema,
)
from api_key.schemas.response import (
    ApiKeyListItemResponseSchema,
    ApiKeyCreatedResponseSchema,
)
from api_key.service import ApiKeyService


# URL path 의 team_id 가 scope 된 team_id 와 일치하는지 검증 — URL 탬퍼링 방어.
def _assert_scope(path_team_id: int, scoped_team_id: int) -> None:
    if path_team_id != scoped_team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NOT_TEAM_MEMBER",
                "message": "URL 의 team_id 와 인증된 team_id 가 일치하지 않습니다.",
            },
        )


router = APIRouter(prefix="/api/v1/team/{team_id}/api-keys", tags=["api-key"])


@router.post("", response_model=ApiKeyCreatedResponseSchema, status_code=201)
async def create_api_key(
    team_id: int,
    body: CreateApiKeyRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    scoped_team_id: int = Depends(get_team_scope),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    """Mint a new API key. The full ``key`` value is returned in this
    response and never again — the client must stash it immediately.
    """
    _assert_scope(team_id, scoped_team_id)
    svc = ApiKeyService(db, scoped_team_id)
    return await svc.create(
        name=body.name,
        description=body.description,
        expires_in_days=body.expires_in_days,
        created_by_user_id=int(me.id),
    )


@router.get("", response_model=List[ApiKeyListItemResponseSchema])
async def list_api_keys(
    team_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    scoped_team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    _assert_scope(team_id, scoped_team_id)
    svc = ApiKeyService(db, scoped_team_id)
    return await svc.list_by_team()


@router.get("/{api_key_id}", response_model=ApiKeyListItemResponseSchema)
async def get_api_key(
    team_id: int,
    api_key_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    scoped_team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    _assert_scope(team_id, scoped_team_id)
    svc = ApiKeyService(db, scoped_team_id)
    return await svc.get(api_key_id)


@router.patch("/{api_key_id}", response_model=ApiKeyListItemResponseSchema)
async def update_api_key(
    team_id: int,
    api_key_id: int,
    body: UpdateApiKeyRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    scoped_team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """Only name/description are mutable. The secret itself cannot be
    rotated in place — revoke and issue a new one instead."""
    _assert_scope(team_id, scoped_team_id)
    svc = ApiKeyService(db, scoped_team_id)
    return await svc.update(
        api_key_id,
        name=body.name,
        description=body.description,
    )


@router.delete("/{api_key_id}", status_code=204)
async def revoke_api_key(
    team_id: int,
    api_key_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    scoped_team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """Soft-delete (revoke). Row 는 유지되며 is_active=False 로 마킹,
    ``updated_at`` 이 회수 시점으로 갱신. 인증 경로는 ``is_active=True`` 만 통과."""
    _assert_scope(team_id, scoped_team_id)
    svc = ApiKeyService(db, scoped_team_id)
    await svc.revoke(api_key_id)
