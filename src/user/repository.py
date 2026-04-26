# src/user/repository.py
from __future__ import annotations
from typing import List, Optional

from sqlalchemy import select, delete, update, func
from sqlalchemy.orm import selectinload, load_only, with_loader_criteria
from sqlalchemy.ext.asyncio import AsyncSession

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.service import CommonService
from tenant.model import TenantModel, UserTenantModel
from user.model import UserModel
from user.schemas.request import PaginateUserRequestSchema
from auth.const.providers import AuthProviderEnum
from file.model import FileAssetModel


def _norm(email: str) -> str:
    """이메일 정규화(양끝 공백 제거 + 소문자)"""
    return (email or "").strip().lower()


class UserRepository:
    """플랫폼 전역 스코프 사용자 레포지토리.
    
    - 목록/상세 로딩 옵션을 분리해 경량화 여지 확보
    - 일반 조회에는 password 절대 포함하지 않음
    - 로그인 전용(get_user_for_auth)에서만 password 로딩
    -  OAuth 지원: auth_provider, oauth_id 컬럼 추가
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.common = CommonService()

    # ═══════════════════════════════════════════════════════════════
    # 로딩 옵션
    # ═══════════════════════════════════════════════════════════════

    def _with_options_detail(self, stmt):
        """상세 조회용 로딩 옵션 (password 미포함, 관계 명시 로드)"""
        return stmt.options(
            load_only(
                UserModel.id,
                UserModel.email,
                UserModel.role,
                UserModel.name,
                UserModel.phone,
                UserModel.auth_provider,               #  OAuth
                UserModel.oauth_id,                    #  OAuth
                UserModel.notification_email,
                UserModel.event_notification_enabled,
                UserModel.language,                    #  i18n
            ),
            # User → Teams(활성만) → Team(최소 컬럼)
            selectinload(UserModel.tenants).options(
                load_only(
                    UserTenantModel.id,
                    UserTenantModel.tenant_id,
                    UserTenantModel.permission_group_id,
                ),
                selectinload(UserTenantModel.tenant).options(
                    load_only(
                        TenantModel.id,
                        TenantModel.name,
                    )
                ),
            ),
            # User → Files(활성만, view-only)
            selectinload(UserModel.files).options(
                load_only(
                    FileAssetModel.id,
                    FileAssetModel.domain,
                    FileAssetModel.object_id,
                    FileAssetModel.subdir,
                    FileAssetModel.filename,
                    FileAssetModel.size,
                    FileAssetModel.mime,
                    FileAssetModel.is_public,
                    FileAssetModel.logical_path,
                )
            ),
            # 하위 리소스 활성 필터
            with_loader_criteria(UserTenantModel, UserTenantModel.is_active.is_(True), include_aliases=True),
            with_loader_criteria(FileAssetModel, FileAssetModel.is_active.is_(True), include_aliases=True),
        )

    def _with_options_list(self, stmt):
        """목록 조회용 로딩 옵션 (초기엔 상세와 동일, 추후 경량화 대상)"""
        return stmt.options(
            load_only(
                UserModel.id,
                UserModel.email,
                UserModel.role,
                UserModel.name,
                UserModel.phone,
                UserModel.auth_provider,               #  OAuth
                UserModel.oauth_id,                    #  OAuth
                UserModel.notification_email,
                UserModel.event_notification_enabled,
                UserModel.language,                    #  i18n
            ),
            selectinload(UserModel.tenants).options(
                load_only(
                    UserTenantModel.id,
                    UserTenantModel.tenant_id,
                    UserTenantModel.permission_group_id,
                ),
                selectinload(UserTenantModel.tenant).options(
                    load_only(
                        TenantModel.id,
                        TenantModel.name,
                    )
                ),
            ),
            selectinload(UserModel.files).options(
                load_only(
                    FileAssetModel.id,
                    FileAssetModel.domain,
                    FileAssetModel.object_id,
                    FileAssetModel.subdir,
                    FileAssetModel.filename,
                    FileAssetModel.size,
                    FileAssetModel.mime,
                    FileAssetModel.is_public,
                    FileAssetModel.logical_path,
                )
            ),
            with_loader_criteria(UserTenantModel, UserTenantModel.is_active.is_(True), include_aliases=True),
            with_loader_criteria(FileAssetModel, FileAssetModel.is_active.is_(True), include_aliases=True),
        )

    # ═══════════════════════════════════════════════════════════════
    # 인증용 조회 (password 포함)
    # ═══════════════════════════════════════════════════════════════

    async def get_user_for_auth(self, email: str) -> Optional[UserModel]:
        """
        이메일+비밀번호 로그인 전용 조회.
        - password 반드시 포함
        - auth_provider='email'인 사용자만 조회 (OAuth 사용자 제외)
        - selectinload 전부 제거(레이지 트리거 방지)
        """
        stmt = (
            select(UserModel)
            .where(
                UserModel.email == _norm(email),
                UserModel.auth_provider == AuthProviderEnum.EMAIL.value,  #  이메일 가입자만
                UserModel.is_active.is_(True),
            )
            .options(
                load_only(
                    UserModel.id,
                    UserModel.email,
                    UserModel.password,  # 로그인 전용
                    UserModel.role,
                    UserModel.name,
                    UserModel.phone,
                    UserModel.auth_provider,
                    UserModel.oauth_id,
                    UserModel.notification_email,
                    UserModel.event_notification_enabled,
                    UserModel.created_at,
                    UserModel.updated_at,
                    UserModel.is_active,
                )
            )
        )
        return await self.db.scalar(stmt)

    async def get_user_by_oauth(self, provider: AuthProviderEnum, oauth_id: str) -> Optional[UserModel]:
        """
        OAuth 로그인용 조회.
        - provider + oauth_id로 사용자 조회
        - password 미포함
        """
        stmt = (
            select(UserModel)
            .where(
                UserModel.auth_provider == provider.value,
                UserModel.oauth_id == oauth_id,
                UserModel.is_active.is_(True),
            )
        )
        stmt = self._with_options_detail(stmt)
        return await self.db.scalar(stmt)

    # ═══════════════════════════════════════════════════════════════
    # 이메일 충돌 검사 (OAuth 지원)
    # ═══════════════════════════════════════════════════════════════

    async def get_active_user_by_email(self, email: str) -> Optional[UserModel]:
        """
        이메일로 활성 사용자 조회 (provider 상관없이).
        - 이메일 충돌 검사용
        - 어떤 provider든 같은 이메일이면 반환
        """
        stmt = (
            select(UserModel)
            .where(
                UserModel.email == _norm(email),
                UserModel.is_active.is_(True),
            )
            .options(
                load_only(
                    UserModel.id,
                    UserModel.email,
                    UserModel.auth_provider,
                )
            )
        )
        return await self.db.scalar(stmt)

    async def check_email_conflict(self, email: str, current_provider: AuthProviderEnum) -> Optional[str]:
        """
        같은 이메일로 다른 provider에서 가입된 게 있는지 확인.
        
        Returns:
            None: 충돌 없음
            str: 에러 메시지 ("이미 XX로 가입된 이메일입니다.")
        """
        if not email:
            return None
        
        existing = await self.get_active_user_by_email(email)
        
        if existing and existing.auth_provider != current_provider.value:
            provider_name = AuthProviderEnum(existing.auth_provider).display_name_ko()
            return f"이미 {provider_name}로 가입된 이메일입니다."
        
        return None

    async def exists_oauth_user(self, provider: AuthProviderEnum, oauth_id: str) -> bool:
        """OAuth 사용자 존재 여부 확인"""
        stmt = select(func.count(UserModel.id)).where(
            UserModel.auth_provider == provider.value,
            UserModel.oauth_id == oauth_id,
            UserModel.is_active.is_(True),
        )
        return (await self.db.execute(stmt)).scalar_one() > 0

    # ═══════════════════════════════════════════════════════════════
    # 기존 메서드들 (변경 없음)
    # ═══════════════════════════════════════════════════════════════

    async def list_paginated(self, request: PaginateUserRequestSchema) -> CursorPaginationResult[UserModel]:
        """목록: 사용자 커서/페이지 페이지네이션 (검색 where__email__i_like 지원)"""
        base = select(UserModel).where(UserModel.is_active.is_(True))
        base = self._with_options_list(base)

        # 보조 i_like (DB별 대소문자 무시)
        if request.where__email__i_like:
            q = f"%{request.where__email__i_like.strip().lower()}%"
            base = base.where(func.lower(UserModel.email).like(q))

        return await self.common.paginate(
            request=request,
            model=UserModel,
            session=self.db,
            base_query=base,
            path="user",
        )

    async def get_user_by_id(self, id: int) -> Optional[UserModel]:
        """상세: PK로 활성 사용자 단건 조회"""
        stmt = select(UserModel).where(UserModel.id == id, UserModel.is_active.is_(True))
        stmt = self._with_options_detail(stmt)
        return await self.db.scalar(stmt)

    async def get_user_by_email(self, email: str) -> Optional[UserModel]:
        """이메일로 활성 사용자 조회 (provider 상관없이, 비밀번호 미포함)"""
        stmt = select(UserModel).where(
            UserModel.email == _norm(email),
            UserModel.is_active.is_(True),
        )
        stmt = self._with_options_detail(stmt)
        return await self.db.scalar(stmt)

    async def has_active_email_conflict(self, email: str, exclude_user_id: Optional[int] = None) -> bool:
        """유틸: 활성 이메일 충돌 여부 (자기 자신 제외 가능)"""
        email = _norm(email)
        stmt = select(func.count(UserModel.id)).where(
            UserModel.email == email,
            UserModel.is_active.is_(True),
        )
        if exclude_user_id:
            stmt = stmt.where(UserModel.id != exclude_user_id)
        return (await self.db.execute(stmt)).scalar_one() > 0

    async def exists_email(self, email: str) -> bool:
        """이메일 존재 여부 확인 (provider 상관없이)"""
        return await self.has_active_email_conflict(email)

    async def create_user(self, new_user: UserModel) -> UserModel:
        """생성: UserModel INSERT 후 refresh"""
        self.db.add(new_user)
        await self.db.flush()
        await self.db.refresh(new_user)
        return new_user

    async def hard_delete_user_by_id(self, id: int) -> None:
        """삭제(하드): 외래키 제약으로 실패할 수 있음(서비스에서 소프트 전환)"""
        await self.db.execute(delete(UserModel).where(UserModel.id == id))

    async def soft_deactivate_user_by_id(self, id: int) -> None:
        """소프트 비활성화: is_active=False로 전환"""
        await self.db.execute(
            update(UserModel)
            .where(UserModel.id == id, UserModel.is_active.is_(True))
            .values(is_active=False)
        )

    async def get_user_tenant_ids(self, user_id: int) -> List[int]:
        """팀 유틸: 사용자가 속한 팀 ID 목록"""
        stmt = select(UserTenantModel.tenant_id).where(UserTenantModel.user_id == user_id)
        rows = (await self.db.execute(stmt)).all()
        return [row[0] for row in rows]

    async def deactivate_memberships_by_user(self, user_id: int) -> None:
        """팀 유틸: 해당 사용자의 모든 활성 멤버십 비활성화"""
        await self.db.execute(
            update(UserTenantModel)
            .where(UserTenantModel.user_id == user_id, UserTenantModel.is_active.is_(True))
            .values(is_active=False)
        )

    async def update_password_by_id(self, user_id: int, password_hash: str) -> None:
        """비밀번호 업데이트"""
        await self.db.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(password=password_hash)
        )