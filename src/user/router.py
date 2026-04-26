# src/user/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from common.pagination.schemas.pagination_response import CursorPaginationResult
from database.dependencies import get_read_db, get_write_db
from user.schemas.request import PaginateUserRequestSchema, UserProfileUpdateRequest
from user.service import UserService
from file.schemas.request import UploadUrlRequestSchema
from file.schemas.response import UploadUrlResponseSchema
from file.service import FileService
from user.schemas.response import (
    UserListItemResponseSchema,
    UserDetailResponseSchema,
    UserResponseSchema,
    UserDeleteResponseSchema,
)
from user.dependencies.current_user import get_current_user
from auth.tokens.access_token import access_token

router = APIRouter(prefix="/api/v1/users", tags=["users"])


# ---------- 조회(목록: 커서 페이지네이션) ----------
@router.get("", response_model=CursorPaginationResult[UserListItemResponseSchema])
async def get_users(
    request: PaginateUserRequestSchema = Depends(),
    _1: None = Depends(access_token),
    db: AsyncSession = Depends(get_read_db),
):
    svc = UserService(db)
    return await svc.list_users_paginated(request)


# ---------- 단건 조회(본인) ----------
@router.get("/me", response_model=UserDetailResponseSchema)
async def get_me(
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_read_db),
):
    svc = UserService(db)
    return await svc.get_user_by_id(int(me.id))


# ---------- 프로필 이미지 업로드 URL 발급 (팀 불필요) ----------
@router.post("/me/upload-urls", response_model=UploadUrlResponseSchema)
async def get_user_upload_urls(
    body: UploadUrlRequestSchema,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_read_db),
):
    """
    사용자 프로필 이미지 업로드용 Presigned URL 발급

    팀 선택 전에도 프로필 이미지를 업로드할 수 있도록
    팀 컨텍스트 없이 access_token + 본인 인증만 요구.
    """
    svc = FileService(db)
    token, files = svc.generate_upload_urls(body.filenames)
    return UploadUrlResponseSchema(token=token, files=files)


# ---------- 프로필 업데이트(본인) ----------
@router.patch("/me", response_model=UserDetailResponseSchema)
async def update_me(
    request: UserProfileUpdateRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    """
    본인 프로필 업데이트
    - name: 사용자 이름
    - phone: 전화번호 (나중에 사용)
    - event_notification_enabled: 이벤트 알림 수신 여부
    - temp_keys: 새로 업로드한 프로필 이미지 개별 키
    - remove_file_ids: 삭제할 기존 이미지 ID
    """
    svc = UserService(db)
    return await svc.update_user_profile(
        user_id=int(me.id),
        name=request.name,
        phone=request.phone,
        event_notification_enabled=request.event_notification_enabled,
        language=request.language,
        temp_keys=request.temp_keys,
        remove_file_ids=request.remove_file_ids,
    )


# ---------- 삭제 ----------
@router.delete("/{user_id}", response_model=UserDeleteResponseSchema)
async def delete_user(
    user_id: int,
    _1: None = Depends(access_token),
    db: AsyncSession = Depends(get_write_db),
):
    """
    사용자 삭제
    - 하드 삭제 우선, FK 제약 시 소프트 비활성화
    - 멤버 0명이 된 팀은 정책에 따라 정리
    """
    svc = UserService(db)
    return await svc.delete_user_by_actor(target_user_id=user_id)