# src/tenant/service.py
from __future__ import annotations
from typing import Optional, Iterable, List
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, func
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, available_timezones

from common.pagination.schemas.pagination_response import CursorPaginationResult
from rbac.cache_service import (
    invalidate_user_tenant_meta, invalidate_tenant_scope,
    bulk_invalidate_user_tenant_meta, TENANT_SCOPE_KEY,
)
from rbac.const.const import (
    DEFAULT_ADMIN_CODES, DEFAULT_MEMBER_CODES, DEFAULT_VIEWER_CODES,
)
from tenant.model import UserTenantModel
from tenant.repository import TenantRepository
from tenant.schemas.request import PaginateTeamMemberRequestSchema, PaginateTeamRequestSchema
from tenant.schemas.request import OnboardingUpdateRequestSchema
from tenant.schemas.request import TeamSettingsUpdateRequestSchema
from tenant.schemas.response import (
    TenantListItemResponseSchema,
    UserTenantResponseSchema,
    TenantResponseSchema,
    TenantDetailResponseSchema,
    TeamRenameResponseSchema,
    TenantDeleteResponseSchema,
    TenantReactivateResponseSchema,
    TeamMemberInviteResponseSchema,
    TeamMemberRemoveResponseSchema,
    TeamMemberPermissionResponseSchema,
    OnboardingUpdateResponseSchema,
    TeamUsageStatsResponseSchema,
    TimezoneItemSchema,
)
from common.exceptions.base import NotFoundException, ConflictException, AppException
from common.const.settings import settings
from file.service import FileService
from file.const.domains import FileDomain

# ─────────────────────────────────────────────────────────
# ▼ 시간대 목록 (모듈 레벨 캐싱 — 서버 기동 시 1회 계산)
# ─────────────────────────────────────────────────────────
_cached_timezones: List[TimezoneItemSchema] | None = None


def get_timezone_list() -> List[TimezoneItemSchema]:
    """
    IANA 시간대 전체 목록을 (GMT±HH:MM) Region/City 포맷으로 반환.
    - Region/City 형식만 포함 (Etc/, 약어 제외)
    - UTC offset 기준 정렬 → 같은 offset 내 알파벳순
    - 서버 기동 후 최초 호출 시 1회 계산, 이후 캐싱
    """
    global _cached_timezones
    if _cached_timezones is not None:
        return _cached_timezones

    now = datetime.now(timezone.utc)
    items: list[tuple[float, str, str]] = []  # (offset_seconds, code, label)

    for tz_name in available_timezones():
        # Region/City 형식만 포함 (슬래시가 있어야 하고, Etc/ 제외)
        if "/" not in tz_name or tz_name.startswith("Etc/"):
            continue

        try:
            tz = ZoneInfo(tz_name)
            offset = now.astimezone(tz).utcoffset()
            if offset is None:
                continue
            total_seconds = offset.total_seconds()
            hours, remainder = divmod(abs(total_seconds), 3600)
            minutes = remainder // 60
            sign = "+" if total_seconds >= 0 else "-"
            label = f"(GMT{sign}{int(hours):02d}:{int(minutes):02d}) {tz_name}"
            items.append((total_seconds, tz_name, label))
        except Exception:
            continue

    # 정렬: offset 오름차순 → 같은 offset 내 알파벳순
    items.sort(key=lambda x: (x[0], x[1]))

    _cached_timezones = [
        TimezoneItemSchema(code=code, label=label)
        for _, code, label in items
    ]
    return _cached_timezones


class TenantService:
    """
    정책 요약:
    - 조회: 활성 팀만 반환 (repo에서 is_active=True 강제)
    - 삭제: 항상 소프트 삭제
      * is_active=False
      * deactivated_at=now(UTC) (최초만)
      * purge_at=now+{PURGE_GRACE_DAYS}
    - 되살리기: is_active=True, purge_at=None

    트랜잭션:
    - 요청 스코프 세션(get_db()) 전제, 여기서 commit() 직접 호출하지 않음.
    """

    # 서비스 초기화: Repository/Redis/FileService 핸들 준비
    def __init__(self, db: AsyncSession, redis: Redis | None = None):
        self.db = db
        self.repo = TenantRepository(db)
        self.redis = redis
        self.file_svc = FileService(db)

    # ─────────────────────────────────────────
    # ▼ 커서 페이지네이션
    # ─────────────────────────────────────────

    # 내가 속한 팀 목록(활성) 커서 페이지네이션 반환(DTO 직변환 + 파일 URL 주입)
    async def list_my_tenants_paginated(
        self,
        user_id: int,
        request: PaginateTeamRequestSchema,
    ) -> CursorPaginationResult[TenantListItemResponseSchema]:
        result = await self.repo.list_my_tenants_paginated(user_id, request)
        items = []
        for t in result.data:
            item = TenantListItemResponseSchema.model_validate(t)
            if item.files:
                self.file_svc.inject_file_urls(item.files)
            items.append(item)
        result.data = items
        return result

    # 특정 팀의 멤버(UserTeam) 목록을 커서 페이지네이션으로 반환(팀 멤버만 접근 가능)
    async def list_tenant_members_paginated(
        self,
        *,
        tenant_id: int,
        request: PaginateTeamMemberRequestSchema,
        actor_user_id: int,
    ) -> CursorPaginationResult[UserTenantResponseSchema]:
        """
        팀 멤버 커서 페이지네이션
        - 접근 제어: 요청자가 해당 팀 멤버여야 함
        - 레포는 ORM 그대로 반환 → 여기서 직변환만 수행
        """
        tenant = await self.repo.get_tenant_including_inactive(tenant_id)
        if not tenant:
            raise NotFoundException("팀")

        if not await self.repo.is_member(tenant_id, actor_user_id):
            raise NotFoundException("팀")

        result = await self.repo.list_members_paginated(tenant_id=tenant_id, request=request)
        result.data = [UserTenantResponseSchema.model_validate(ut) for ut in result.data]

        # 멤버 프로필 이미지 URL 주입
        for item in result.data:
            if item.user and item.user.files:
                self.file_svc.inject_file_urls(item.user.files)

        return result

    # 팀 멤버 Delta Sync (hard-delete → all_ids)
    async def sync_members_delta(
        self,
        *,
        tenant_id: int,
        since_str: str,
        actor_user_id: int,
    ):
        """
        팀 멤버 Delta Sync
        - 접근 제어: 요청자가 해당 팀 멤버여야 함
        - since 이후 변경된 멤버 + 전체 활성 멤버 ID 반환
        """
        if not await self.repo.is_member(tenant_id, actor_user_id):
            raise NotFoundException("팀")

        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_members_delta(tenant_id, since)

        result.items = [UserTenantResponseSchema.model_validate(ut) for ut in result.items]
        for item in result.items:
            if item.user and item.user.files:
                self.file_svc.inject_file_urls(item.user.files)

        return result

    # tenant_id로 활성 팀 상세 조회(DTO 직변환 + 파일 URL 주입)
    async def get_tenant(self, tenant_id: int) -> TenantResponseSchema:
        tenant = await self.repo.get_tenant(tenant_id)
        if not tenant:
            raise NotFoundException("팀")
        response = TenantDetailResponseSchema.model_validate(tenant)
        self.file_svc.inject_file_urls(response.files)
        return response

    # ─────────────────────────────────────────
    # 생성/변경/삭제
    # ─────────────────────────────────────────

    # 팀 생성: 기본 권한 그룹 생성/권한 매핑/생성자 멤버 추가/기본 위치 생성까지 처리 후 DTO 반환
    async def create_tenant(self, *, name: str, creator_user_id: int) -> TenantResponseSchema:
        tenant = await self.repo.create_tenant(name=name)

        # 기본 권한 그룹 3종
        g_admin  = await self.repo.create_group(tenant_id=tenant.id, name="관리자", is_admin=True,  is_system=True, system_key="ADMIN")
        g_member = await self.repo.create_group(tenant_id=tenant.id, name="멤버",   is_admin=False, is_system=True, system_key="MEMBER")
        g_viewer = await self.repo.create_group(tenant_id=tenant.id, name="뷰어",   is_admin=False, is_system=True, system_key="VIEWER")

        # 권한 매핑
        perm_id_map = await self.repo.get_permission_id_map()

        def to_ids(codes: Iterable[str]) -> List[int]:
            return [perm_id_map[c] for c in codes if c in perm_id_map]

        await self.repo.add_permissions_to_group(tenant_id=tenant.id, group_id=g_admin.id,  permission_ids=to_ids(DEFAULT_ADMIN_CODES))
        await self.repo.add_permissions_to_group(tenant_id=tenant.id, group_id=g_member.id, permission_ids=to_ids(DEFAULT_MEMBER_CODES))
        await self.repo.add_permissions_to_group(tenant_id=tenant.id, group_id=g_viewer.id, permission_ids=to_ids(DEFAULT_VIEWER_CODES))

        # 생성자를 관리자 그룹으로 등록
        await self.repo.add_member(tenant_id=tenant.id, user_id=creator_user_id, permission_group_id=g_admin.id)

        # ste 의 location/attribute 기본 시드는 TMS 와 무관 (별도 도메인). 폐기.

        # 새 tenant 이므로 files 관계를 빈 리스트로 초기화 (lazy='raise' 우회)
        from sqlalchemy.orm.attributes import set_committed_value
        set_committed_value(tenant, "files", [])

        # ORM → DTO 직변환
        return TenantDetailResponseSchema.model_validate(tenant)

    # 팀 이름 변경
    async def rename_tenant(self, *, tenant_id: int, name: str, actor_user_id: int) -> TeamRenameResponseSchema:
        tenant = await self.repo.get_tenant(tenant_id)
        if not tenant:
            raise NotFoundException("팀")
        await self.repo.rename_tenant(tenant_id, name=name)
        tenant.updated_by_user_id = actor_user_id
        return TeamRenameResponseSchema(
            id=tenant_id,
            renamed=True,
            name=name,
        )

    # 팀 삭제(소프트): 비활성화 및 purge_at 예약
    async def delete_tenant(self, *, tenant_id: int, actor_user_id: int) -> TenantDeleteResponseSchema:
        """
        팀 삭제 정책(소프트 전용):
        - is_active=False
        - deactivated_at: 최초만 기록
        - purge_at: now+grace로 최소 보장
        """
        tenant = await self.repo.get_tenant_including_inactive(tenant_id)
        if not tenant:
            raise NotFoundException("팀")

        now = datetime.now(timezone.utc)

        tenant.is_active = False
        tenant.updated_by_user_id = actor_user_id
        if not tenant.deactivated_at:
            tenant.deactivated_at = now
            tenant.deactivated_by = actor_user_id

        scheduled = now + timedelta(days=settings.PURGE_GRACE_DAYS)
        if not tenant.purge_at or tenant.purge_at < scheduled:
            tenant.purge_at = scheduled

        # 팀 멤버 캐시 벌크 무효화 (즉시 접근 차단)
        if self.redis:
            user_ids = await self.repo.get_active_member_user_ids(tenant_id)
            if user_ids:
                pairs = [(uid, tenant_id) for uid in user_ids]
                await bulk_invalidate_user_tenant_meta(self.redis, pairs)
                scope_keys = [TENANT_SCOPE_KEY.format(uid=uid, tid=tenant_id) for uid in user_ids]
                await self.redis.unlink(*scope_keys)

        return TenantDeleteResponseSchema(
            id=tenant_id,
            deleted=True,
            purge_at=tenant.purge_at,
        )

    # 비활성화된 팀을 재활성화
    async def reactivate_tenant(self, *, tenant_id: int) -> TenantReactivateResponseSchema:
        tenant = await self.repo.get_tenant_including_inactive(tenant_id)
        if not tenant:
            raise NotFoundException("팀")

        tenant.is_active = True
        tenant.purge_at = None
        return TenantReactivateResponseSchema(
            id=tenant_id,
            reactivated=True,
        )

    # 팀에 멤버 초대(중복 소속 방지 검사 + 캐시 무효화)
    async def invite_member(
        self,
        *,
        tenant_id: int,
        user_id: int,
        permission_group_id: Optional[int],
    ) -> TeamMemberInviteResponseSchema:
        tenant = await self.repo.get_tenant(tenant_id)
        if not tenant:
            raise NotFoundException("팀")
        if await self.repo.is_member(tenant_id, user_id):
            raise ConflictException("이미 팀 멤버입니다.")

        await self.repo.add_member(tenant_id=tenant_id, user_id=user_id, permission_group_id=permission_group_id)

        if self.redis:
            await invalidate_user_tenant_meta(self.redis, user_id, tenant_id)

        return TeamMemberInviteResponseSchema(
            tenant_id=tenant_id,
            user_id=user_id,
            invited=True,
            permission_group_id=permission_group_id,
        )

    # 팀에서 멤버 제거(존재 확인 + 캐시 무효화)
    async def remove_member(self, *, tenant_id: int, target_user_id: int) -> TeamMemberRemoveResponseSchema:
        tenant = await self.repo.get_tenant(tenant_id)
        if not tenant:
            raise NotFoundException("팀")
        if not await self.repo.is_member(tenant_id, target_user_id):
            raise NotFoundException("해당 사용자는 팀 멤버가 아닙니다.")

        await self.repo.remove_member(tenant_id=tenant_id, user_id=target_user_id)

        if self.redis:
            await invalidate_user_tenant_meta(self.redis, target_user_id, tenant_id)
            await invalidate_tenant_scope(self.redis, target_user_id, tenant_id)

        return TeamMemberRemoveResponseSchema(
            tenant_id=tenant_id,
            user_id=target_user_id,
            removed=True,
        )

    # (본인) 팀 탈퇴
    async def leave_team(self, *, tenant_id: int, actor_user_id: int) -> TeamMemberRemoveResponseSchema:
        # 마지막 관리자는 탈퇴 불가
        if await self.repo.is_admin_member(tenant_id, actor_user_id):
            if await self.repo.count_admin_members(tenant_id) <= 1:
                raise AppException(
                    code="cannot-leave-without-successor-admin",
                    message="마지막 관리자는 팀을 나갈 수 없습니다. 다른 관리자를 추가하시거나, 팀을 삭제해 주세요.",
                    status_code=400,
                )
        return await self.remove_member(tenant_id=tenant_id, target_user_id=actor_user_id)

    # 멤버의 권한 그룹 변경(검증 포함) + 캐시 무효화
    async def assign_permission_group(
        self,
        *,
        tenant_id: int,
        target_user_id: int,
        permission_group_id: Optional[int],
    ) -> TeamMemberPermissionResponseSchema:
        tenant = await self.repo.get_tenant(tenant_id)
        if not tenant:
            raise NotFoundException("팀")

        if not await self.repo.is_member(tenant_id, target_user_id):
            raise NotFoundException("해당 사용자는 팀 멤버가 아닙니다.")

        if permission_group_id is not None:
            from rbac.repository import RbacRepository
            rrepo = RbacRepository(self.db, self.redis)
            g = await rrepo.get_group(group_id=permission_group_id, tenant_id=tenant_id)
            if not g:
                raise NotFoundException("권한 그룹")

        await self.db.execute(
            update(UserTenantModel)
            .where(
                UserTenantModel.tenant_id == tenant_id,
                UserTenantModel.user_id == target_user_id,
            )
            .values(permission_group_id=permission_group_id, updated_at=func.now())
        )

        if self.redis:
            await invalidate_user_tenant_meta(self.redis, target_user_id, tenant_id)

        return TeamMemberPermissionResponseSchema(
            tenant_id=tenant_id,
            user_id=target_user_id,
            updated=True,
            permission_group_id=permission_group_id,
        )

    # ─────────────────────────────────────────
    # ▼ 팀 설정 업데이트
    # ─────────────────────────────────────────
    async def update_team_settings(
        self,
        *,
        tenant_id: int,
        payload: TeamSettingsUpdateRequestSchema,
        actor_user_id: int,
    ) -> TenantDetailResponseSchema:
        """팀 설정 부분 업데이트 (PATCH semantics — 전달된 필드만 업데이트)"""
        tenant = await self.repo.get_tenant(tenant_id)
        if not tenant:
            raise NotFoundException("팀")

        # 파일 관련 필드 추출 (DB 업데이트 대상에서 제외)
        temp_keys = payload.temp_keys
        remove_file_ids = payload.remove_file_ids

        update_data = payload.model_dump(exclude_unset=True, exclude={"temp_keys", "remove_file_ids"})
        update_data["updated_by_user_id"] = actor_user_id
        await self.repo.update_settings(tenant_id, update_data)

        # 파일 커밋 (이미지 추가/삭제)
        if temp_keys or remove_file_ids:
            await self.file_svc.commit(
                tenant_id=tenant_id,
                domain=FileDomain.TENANT,
                object_id=tenant_id,
                subdir="image",
                add_temp_keys=temp_keys or [],
                remove_file_ids=remove_file_ids or [],
                actor_user_id=actor_user_id,
                is_public=False,
            )

        # 세션 캐시 초기화 후 재조회 (계정설정 update_user_profile 패턴과 동일)
        await self.db.refresh(tenant)
        updated_tenant = await self.repo.get_tenant(tenant_id)
        response = TenantDetailResponseSchema.model_validate(updated_tenant)
        self.file_svc.inject_file_urls(response.files)
        return response

    # ─────────────────────────────────────────
    # ▼ 팀 사용량 통계
    # ─────────────────────────────────────────
    async def get_usage_stats(self, tenant_id: int) -> TeamUsageStatsResponseSchema:
        """팀 사용량 통계 조회"""
        tenant = await self.repo.get_tenant(tenant_id)
        if not tenant:
            raise NotFoundException("팀")

        stats = await self.repo.get_usage_stats(tenant_id)
        return TeamUsageStatsResponseSchema(**stats)

    # ─────────────────────────────────────────
    # ▼ 온보딩 상태 업데이트
    # ─────────────────────────────────────────
    async def update_onboarding(
        self,
        *,
        tenant_id: int,
        payload: OnboardingUpdateRequestSchema,
    ) -> OnboardingUpdateResponseSchema:
        """온보딩 상태 부분 업데이트"""
        tenant = await self.repo.get_tenant(tenant_id)
        if not tenant:
            raise NotFoundException("팀")

        # 전달된 필드만 업데이트
        if payload.step1_done is not None:
            tenant.onboarding_step1_done = payload.step1_done
        if payload.step2_done is not None:
            tenant.onboarding_step2_done = payload.step2_done
        if payload.step3_done is not None:
            tenant.onboarding_step3_done = payload.step3_done
        if payload.completed is not None:
            tenant.onboarding_completed = payload.completed

        return OnboardingUpdateResponseSchema(
            id=tenant_id,
            updated=True,
            onboarding_step1_done=tenant.onboarding_step1_done,
            onboarding_step2_done=tenant.onboarding_step2_done,
            onboarding_step3_done=tenant.onboarding_step3_done,
            onboarding_completed=tenant.onboarding_completed,
        )