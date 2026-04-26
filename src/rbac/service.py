# rbac/service.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from common.pagination.schemas.pagination_response import CursorPaginationMeta, CursorPaginationResult
from rbac.model import PermissionGroupModel
from rbac.repository import RbacRepository
from rbac.schemas.response import (
    RbacMeResponseSchema,
    RbacMetaResponseSchema,
    PermissionGroupListItemResponseSchema,
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
from rbac.cache_service import (
    invalidate_group_codes,
    invalidate_group_excluded_attrs,
    bulk_invalidate_user_tenant_meta,
)
from rbac.const.const import ALL_PERMISSION_CODES, IMPLICIT_NON_VIEWER_CODES
from common.exceptions.base import NotFoundException, ConflictException, AppException


# 시스템 그룹 키 세트(보호 대상)
_SYSTEM_KEYS = {"ADMIN", "MEMBER", "VIEWER"}


class RbacService:
    """
    RBAC 비즈니스 레이어
    ---------------------------------------------------------
    - Repository로부터 권한/그룹 메타 로드
    - 시스템 그룹 보호, 캐시 무효화 트리거
    - 팀 스코프 기준 판단
    - ✔ 권한 코드 변경 시: 그룹 버전 ++, 그룹코드 캐시 무효화, 멤버 META 벌크 무효화
    """
    def __init__(self, db: AsyncSession, redis: Redis | None = None):
        self.repo = RbacRepository(db, redis)
        self.redis = redis

    # ─────────────────────────────────────────
    # 단일 응답: 내 권한 + abilities (/rbac/me)
    # ─────────────────────────────────────────
    async def get_me(
        self,
        *,
        user_id: int,
        tenant_id: Optional[int],
    ) -> RbacMeResponseSchema:
        """
        현재 사용자·팀 컨텍스트에 대한 단일 응답.
        - codes       : 사용자가 실제로 가진 권한 코드 목록
        - abilities   : ALL_PERMISSION_CODES 에 대한 True/False 판정 결과
        - rbac        : { permission_group_id, is_admin }
        """
        codes, group_id, version, is_admin_group = await self.repo.get_user_perm_meta(
            user_id,
            tenant_id=tenant_id,
        )

        # abilities 생성
        if is_admin_group or codes is None:
            abilities = {c: True for c in ALL_PERMISSION_CODES}
            code_list: List[str] = []  # admin 그룹은 codes 빈 리스트로 표기 (전권)
        else:
            abilities = {c: (c in codes) for c in ALL_PERMISSION_CODES}
            code_list = list(codes or [])

        # 속성 접근 제외 ID (admin은 제외 없음, 캐시 활용)
        excluded_attribute_ids: List[int] = []
        if group_id is not None and not is_admin_group:
            ids = await self.repo.get_excluded_attribute_ids(group_id=group_id)
            excluded_attribute_ids = list(ids)

        return RbacMeResponseSchema(
            codes=code_list,
            abilities=abilities,
            rbac=RbacMetaResponseSchema(
                permission_group_id=group_id,
                is_admin=bool(is_admin_group),
            ),
            excluded_attribute_ids=excluded_attribute_ids,
        )

    # ─────────────────────────────────────────────────────────
    # ▼ 커서 페이지네이션: 권한 그룹
    # ─────────────────────────────────────────────────────────
    async def list_groups_paginated(
        self, *, tenant_id: int, request: PaginatePermissionGroupRequest
    ) -> CursorPaginationResult[PermissionGroupListItemResponseSchema]:
        page = await self.repo.list_groups_paginated(tenant_id=tenant_id, request=request)
        groups: list[PermissionGroupModel] = page.data

        group_ids = [g.id for g in groups]
        members_map = await self.repo.bulk_group_members_count(group_ids)
        code_map = await self.repo.bulk_group_code_count(group_ids)

        items = [
            PermissionGroupListItemResponseSchema(
                id=g.id,
                name=g.name,
                is_admin=g.is_admin,
                is_system=g.is_system,
                system_key=g.system_key,
                members=int(members_map.get(g.id, 0)),
                code_count=int(code_map.get(g.id, 0)),
            )
            for g in groups
        ]

        return CursorPaginationResult[PermissionGroupListItemResponseSchema](
            meta=CursorPaginationMeta(count=len(items), hasMore=page.meta.hasMore),
            data=items,
        )

    # ─────────────────────────────────────────────────────────
    # ▼ Delta Sync: 권한 그룹 (hard-delete → all_ids)
    # ─────────────────────────────────────────────────────────
    async def sync_delta(self, *, tenant_id: int, since_str: str):
        """
        권한 그룹 Delta Sync
        - since 이후 변경된 그룹 + 전체 활성 그룹 ID 반환
        - items에 members/code_count 집계 포함
        """
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(tenant_id, since)

        # items에 members/code_count 집계 추가
        group_ids = [g.id for g in result.items]
        members_map = await self.repo.bulk_group_members_count(group_ids) if group_ids else {}
        code_map = await self.repo.bulk_group_code_count(group_ids) if group_ids else {}

        result.items = [
            PermissionGroupListItemResponseSchema(
                id=g.id,
                name=g.name,
                is_admin=g.is_admin,
                is_system=g.is_system,
                system_key=g.system_key,
                members=int(members_map.get(g.id, 0)),
                code_count=int(code_map.get(g.id, 0)),
                version=g.version,
            )
            for g in result.items
        ]

        return result

    # ─────────────────────────────────────────
    # 그룹/코드 관리
    # ─────────────────────────────────────────

    async def get_group_detail(self, *, tenant_id: int, group_id: int) -> PermissionGroupDetailResponseSchema:
        g = await self.repo.get_group(group_id=group_id, tenant_id=tenant_id)
        if not g:
            raise NotFoundException("권한 그룹")

        codes = await self.repo.get_group_codes_set(group_id=group_id)
        members_cnt = await self.repo.count_group_members(group_id=group_id)

        return PermissionGroupDetailResponseSchema(
            id=g.id,
            name=g.name,
            is_admin=g.is_admin,
            is_system=g.is_system,
            system_key=g.system_key,
            codes=sorted(list(codes)),
            excluded_attribute_ids=g.excluded_attribute_ids or [],
            members=members_cnt,
            code_count=len(codes),
        )

    async def create_group(self, *, tenant_id: int, payload: PermissionGroupCreateRequestSchema) -> PermissionGroupDetailResponseSchema:
        """
        커스텀 그룹 생성(+선택적 초기 코드 세트).
        - system_key=None으로 생성
        - payload.codes가 있으면 set_group_codes 반영
        """
        grp = await self.repo.create_group(
            tenant_id=tenant_id,
            name=payload.name,
            is_admin=False,
            is_system=False,
            system_key=None,
            excluded_attribute_ids=payload.excluded_attribute_ids,
        )

        applied = set()
        codes = list(set((payload.codes or []) + IMPLICIT_NON_VIEWER_CODES))
        if codes:
            applied = await self.repo.set_group_codes(group_id=grp.id, codes=codes)
            if self.redis:
                await invalidate_group_codes(self.redis, grp.id)

        return PermissionGroupDetailResponseSchema(
            id=grp.id,
            name=grp.name,
            is_admin=grp.is_admin,
            is_system=grp.is_system,
            system_key=grp.system_key,
            codes=sorted(list(applied)),
            excluded_attribute_ids=grp.excluded_attribute_ids or [],
        )

    async def rename_group(
        self,
        *,
        tenant_id: int,
        group_id: int,
        payload: PermissionGroupRenameRequestSchema,
    ) -> PermissionGroupRenameResponseSchema:
        """그룹 이름 변경. 시스템 그룹은 변경 금지."""
        g = await self.repo.get_group(group_id=group_id, tenant_id=tenant_id)
        if not g:
            raise NotFoundException("권한 그룹")
        if g.is_system:
            raise AppException(code="SYSTEM_GROUP", message="시스템 권한 그룹은 이름을 변경할 수 없습니다.", status_code=400)
        await self.repo.rename_group(group_id=group_id, name=payload.name)
        return PermissionGroupRenameResponseSchema(
            id=group_id,
            renamed=True,
            name=payload.name,
        )

    async def delete_group(self, *, tenant_id: int, group_id: int) -> PermissionGroupDeleteResponseSchema:
        """그룹 삭제. 시스템 그룹 / 멤버 존재 그룹은 삭제 금지."""
        g = await self.repo.get_group(group_id=group_id, tenant_id=tenant_id)
        if not g:
            raise NotFoundException("권한 그룹")
        if g.is_system:
            raise AppException(code="SYSTEM_GROUP", message="시스템 권한 그룹은 삭제할 수 없습니다.", status_code=400)
        if await self.repo.count_group_members(group_id=group_id) > 0:
            raise ConflictException("해당 권한 그룹에 할당된 멤버가 있어 삭제할 수 없습니다.")

        await self.repo.delete_group(group_id=group_id)

        if self.redis:
            await invalidate_group_codes(self.redis, group_id)
            await invalidate_group_excluded_attrs(self.redis, group_id)

        return PermissionGroupDeleteResponseSchema(
            id=group_id,
            deleted=True,
        )

    async def set_group_codes(
        self, *, tenant_id: int, group_id: int, payload: PermissionGroupSetCodesRequestSchema
    ) -> PermissionGroupDetailResponseSchema:
        """
        권한 코드 '완전 교체'.
        - 시스템 그룹은 코드 수정 금지
        - ✔ 반영 후: 그룹 버전 ++, 그룹코드 캐시 무효화, 멤버 META 벌크 무효화
        """
        g = await self.repo.get_group(group_id=group_id, tenant_id=tenant_id)
        if not g:
            raise NotFoundException("권한 그룹")
        if g.is_system:
            raise AppException(code="SYSTEM_GROUP", message="시스템 권한 그룹의 권한 코드는 수정할 수 없습니다.", status_code=400)

        codes = list(set(payload.codes + IMPLICIT_NON_VIEWER_CODES))
        await self.repo.set_group_codes(group_id=group_id, codes=codes)

        # excluded_attribute_ids가 명시적으로 전달된 경우에만 갱신 (None=변경 없음)
        if payload.excluded_attribute_ids is not None:
            await self.repo.set_excluded_attribute_ids(
                group_id=group_id,
                excluded_attribute_ids=payload.excluded_attribute_ids,
            )

        # 버전 증가
        await self.repo.bump_group_version(group_id)

        # 캐시 무효화
        if self.redis:
            await invalidate_group_codes(self.redis, group_id)
            await invalidate_group_excluded_attrs(self.redis, group_id)

            #  벌크 무효화 (Pipeline 사용)
            pairs = await self.repo.list_active_member_pairs_of_group(group_id)
            await bulk_invalidate_user_tenant_meta(self.redis, pairs)

        return await self.get_group_detail(tenant_id=tenant_id, group_id=group_id)

    async def patch_group_codes(
        self, *, tenant_id: int, group_id: int, payload: PermissionGroupPatchCodesRequestSchema
    ) -> PermissionGroupDetailResponseSchema:
        """
        권한 코드 '증감 패치' (op=add/remove).
        - 시스템 그룹 수정 금지
        - ✔ 반영 후: 그룹 버전 ++, 그룹코드 캐시 무효화, 멤버 META 벌크 무효화
        """
        g = await self.repo.get_group(group_id=group_id, tenant_id=tenant_id)
        if not g:
            raise NotFoundException("권한 그룹")
        if g.is_system:
            raise AppException(code="SYSTEM_GROUP", message="시스템 권한 그룹의 권한 코드는 수정할 수 없습니다.", status_code=400)

        codes = payload.codes
        if payload.op == "add":
            codes = list(set(codes + IMPLICIT_NON_VIEWER_CODES))
        elif payload.op == "remove":
            codes = [c for c in codes if c not in IMPLICIT_NON_VIEWER_CODES]
        final = await self.repo.patch_group_codes(group_id=group_id, op=payload.op, codes=codes)

        # 버전 증가
        await self.repo.bump_group_version(group_id)

        # 캐시 무효화
        if self.redis:
            await invalidate_group_codes(self.redis, group_id)

            # 벌크 무효화 (Pipeline 사용)
            pairs = await self.repo.list_active_member_pairs_of_group(group_id)
            await bulk_invalidate_user_tenant_meta(self.redis, pairs)

        return PermissionGroupDetailResponseSchema(
            id=g.id,
            name=g.name,
            is_admin=g.is_admin,
            is_system=g.is_system,
            system_key=g.system_key,
            codes=sorted(list(final)),
        )