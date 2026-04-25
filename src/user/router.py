from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from common.pagination.schemas.pagination_response import CursorPaginationResult
from database.dependencies import get_read_db, get_write_db
from user.schemas.request import PaginateUserRequestSchema, UserProfileUpdateRequest
from user.service import UserService
from user.schemas.response import UserListItemResponseSchema, UserDetailResponseSchema, UserResponseSchema, UserDeleteResponseSchema
from user.dependencies.current_user import get_current_user
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from auth.dependencies.rate_limit import rate_limit

router = APIRouter(prefix="/api/v1/user", tags=["user"])


@router.get("", response_model=CursorPaginationResult[UserListItemResponseSchema])
async def get_users(
    request: PaginateUserRequestSchema = Depends(),
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    db: AsyncSession = Depends(get_read_db),
):
    svc = UserService(db)
    return await svc.list_users_paginated(request)


@router.get("/me", response_model=UserDetailResponseSchema)
async def get_me(
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_read_db),
):
    svc = UserService(db)
    return await svc.get_user_by_id(int(me.id))


@router.patch("/me", response_model=UserDetailResponseSchema)
async def update_me(
    request: UserProfileUpdateRequest,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    svc = UserService(db)
    return await svc.update_user_profile(
        user_id=int(me.id), name=request.name, phone=request.phone,
        event_notification_enabled=request.event_notification_enabled,
        language=request.language, temp_keys=request.temp_keys, remove_file_ids=request.remove_file_ids,
    )


@router.delete("/{user_id}", response_model=UserDeleteResponseSchema)
async def delete_user(
    user_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    db: AsyncSession = Depends(get_write_db),
):
    svc = UserService(db)
    return await svc.delete_user_by_actor(target_user_id=user_id)
