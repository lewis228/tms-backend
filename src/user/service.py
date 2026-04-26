# src/user/service.py
from __future__ import annotations
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from common.pagination.schemas.pagination_response import CursorPaginationResult
from tenant.model import UserTenantModel
from user.repository import UserRepository
from user.model import UserModel
from user.schemas.request import PaginateUserRequestSchema
from user.schemas.response import (
    UserListItemResponseSchema,
    UserDetailResponseSchema,
    UserDeleteResponseSchema,
)
from common.exceptions.base import NotFoundException, ConflictException

from tenant.service import TenantService
from tenant.repository import TenantRepository

from file.service import FileService
from file.const.domains import FileDomain


class UserService:
    """
    플랫폼 전역 사용자 서비스 계층.
    
    - 레포지토리 호출 + DTO 직변환(from_attributes=True) 일관 유지
    - 트랜잭션 커밋은 상위(의존성 주입된 세션 스코프)에서 처리
    
     삭제 정책:
    - User는 항상 소프트 삭제 (하드 삭제 없음)
    - 팀 내 수정 내역(created_by, updated_by 등)에서 user 참조 필요
    - 파일도 유지 (복구 시 필요)
    
     파일 처리:
    - User는 플랫폼 전역이므로 tenant_id=None 사용
    - 경로: private/user/{user_id}/profile/...
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)
        self.team_repo = TenantRepository(db)
        self.tenant_svc = TenantService(db)
        self.file_svc = FileService(db)

    # ─────────────────────────────────────────────────────────────
    # 목록: 사용자 커서/페이지 페이지네이션
    # ─────────────────────────────────────────────────────────────
    async def list_users_paginated(self, request: PaginateUserRequestSchema) -> CursorPaginationResult[UserListItemResponseSchema]:
        result = await self.repo.list_paginated(request)
        items = []
        for r in result.data:
            item = UserListItemResponseSchema.model_validate(r)
            #  presigned URL 주입
            self.file_svc.inject_file_urls(item.files)
            items.append(item)
        result.data = items
        return result

    # ─────────────────────────────────────────────────────────────
    # 상세: user_id 기준 단건 조회 (없으면 404)
    # ─────────────────────────────────────────────────────────────
    async def get_user_by_id(self, user_id: int) -> UserDetailResponseSchema:
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise NotFoundException("User")
        
        response = UserDetailResponseSchema.model_validate(user)
        
        #  presigned URL 주입
        self.file_svc.inject_file_urls(response.files)
        
        return response

    # ─────────────────────────────────────────────────────────────
    # 생성: 이메일 중복 검사 후 생성 (email에서 기본 이름 추출)
    # ─────────────────────────────────────────────────────────────
    async def create_user(self, *, email: str, password_hash: str, role) -> UserDetailResponseSchema:
        """
        사용자 생성
        
        - 이메일 중복 검사 (is_active=True인 것만)
        - 이메일에서 @ 앞부분을 기본 이름으로 설정
        
        예: "john.doe@example.com" → name: "john.doe"
        """
        if await self.repo.has_active_email_conflict(email):
            raise ConflictException("Active user with the same email already exists.")
        
        #  email에서 @ 앞부분 추출하여 기본 이름으로 설정
        default_name = email.split("@")[0] if "@" in email else email
        
        user = UserModel(
            email=email, 
            password=password_hash, 
            role=role, 
            name=default_name,  #  기본 이름 설정
            is_active=True
        )
        user = await self.repo.create_user(user)
        
        response = UserDetailResponseSchema.model_validate(user)
        #  presigned URL 주입
        self.file_svc.inject_file_urls(response.files)
        
        return response

    # ─────────────────────────────────────────────────────────────
    # 수정: 이메일 변경 (자기 자신/관리자용)
    # ─────────────────────────────────────────────────────────────
    async def update_user_email(self, *, user_id: int, new_email: str) -> UserDetailResponseSchema:
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise NotFoundException("User")
        if await self.repo.has_active_email_conflict(new_email, exclude_user_id=user_id):
            raise ConflictException("Active user with the same email already exists.")
        user.email = (new_email or "").strip().lower()
        await self.db.flush()
        
        response = UserDetailResponseSchema.model_validate(user)
        #  presigned URL 주입
        self.file_svc.inject_file_urls(response.files)
        
        return response

    # ─────────────────────────────────────────────────────────────
    # 프로필 업데이트: 이름, 전화번호, 알림 설정, 프로필 이미지 (자기 자신용)
    # ─────────────────────────────────────────────────────────────
    async def update_user_profile(
        self,
        *,
        user_id: int,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        event_notification_enabled: Optional[bool] = None,
        language: Optional[str] = None,
        temp_keys: List[str] = None,
        remove_file_ids: List[int] = None,
    ) -> UserDetailResponseSchema:
        """
        사용자 프로필 업데이트

        - name: 사용자 이름
        - phone: 전화번호 (나중에 사용)
        - event_notification_enabled: 이벤트 알림 수신 여부
        - temp_keys: 새로 업로드한 이미지의 개별 키
        - remove_file_ids: 삭제할 기존 이미지 ID
        
         파일 처리:
        - User는 플랫폼 전역이므로 tenant_id=None 사용
        - 경로: private/user/{user_id}/profile/...
        """
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise NotFoundException("User")
        
        # 이름/전화번호/알림 설정 업데이트
        if name is not None:
            user.name = name.strip() if name else None
        if phone is not None:
            user.phone = phone.strip() if phone else None
        if event_notification_enabled is not None:
            user.event_notification_enabled = event_notification_enabled
        if language is not None:
            user.language = language.strip() if language else "auto"

        await self.db.flush()
        
        # ─────────────────────────────────────────────────────────
        #  파일 처리 (추가 + 삭제를 한 번에)
        # Product 패턴과 동일하게 FileService.commit() 사용
        # User는 플랫폼 전역이므로 tenant_id=None 사용
        # ─────────────────────────────────────────────────────────
        if temp_keys or remove_file_ids:
            await self.file_svc.commit(
                tenant_id=None,  #  User는 플랫폼 전역
                domain=FileDomain.USER,
                object_id=user_id,
                subdir="profile",
                add_temp_keys=temp_keys or [],
                remove_file_ids=remove_file_ids or [],
                actor_user_id=user_id,
                is_public=False,
            )
        
        # 새로고침하여 최신 상태 반환
        await self.db.refresh(user)
        user = await self.repo.get_user_by_id(user_id)
        
        response = UserDetailResponseSchema.model_validate(user)
        self.file_svc.inject_file_urls(response.files)
        
        return response

    # ─────────────────────────────────────────────────────────────
    # 삭제: 항상 소프트 삭제 (하드 삭제 없음)
    # ─────────────────────────────────────────────────────────────
    async def delete_user_by_actor(self, *, target_user_id: int) -> UserDeleteResponseSchema:
        """
        사용자 삭제 (항상 소프트 삭제)
        
        ⚠️ 하드 삭제 금지 이유:
        - 팀 내 수정 내역(created_by, updated_by 등)에서 user 참조 필요
        - 복구 가능성 유지
        - 감사 추적(audit trail) 보존
        """
        user = await self.repo.get_user_by_id(target_user_id)
        if not user:
            raise NotFoundException("User")

        # 나중 팀 정리를 위해 소속 팀 선조회
        tenant_ids = await self.repo.get_user_tenant_ids(target_user_id)

        # 파일 소프트삭제 (Product와 동일)
        await self.file_svc.soft_deactivate_by_object(
            tenant_id=None,  # User는 플랫폼 전역
            domain=FileDomain.USER,
            object_id=target_user_id,
            actor_user_id=target_user_id,
        )

        # User 소프트삭제
        await self.repo.soft_deactivate_user_by_id(target_user_id)
        await self.repo.deactivate_memberships_by_user(target_user_id)

        # 멤버 0명 팀 소거 (소프트/예약 정책은 TenantService에 위임)
        teams_cleaned = 0
        for tid in set(tenant_ids):
            if await self._count_active_members(tid) == 0:
                await self.tenant_svc.delete_tenant(tenant_id=tid)
                teams_cleaned += 1

        return UserDeleteResponseSchema(
            id=target_user_id,
            deleted=True,
            soft_deleted=True,
            teams_cleaned=teams_cleaned,
        )

    # ─────────────────────────────────────────────────────────────
    # 내부 유틸: 활성 멤버수 집계 (팀 정리 판단용)
    # ─────────────────────────────────────────────────────────────
    async def _count_active_members(self, tenant_id: int) -> int:
        from sqlalchemy import select
        q = select(func.count(UserTenantModel.user_id)).where(
            UserTenantModel.tenant_id == tenant_id,
            UserTenantModel.is_active.is_(True)
        )
        return (await self.db.execute(q)).scalar_one()