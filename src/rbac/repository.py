# rbac/repository.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, Tuple, Set, Iterable, List, Dict

from sqlalchemy import select, join, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only
from redis.asyncio import Redis

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.service import CommonService

from rbac.cache_service import (
    get_group_codes,
    get_user_team_meta,
    set_group_codes as cache_set_group_codes,
    set_user_team_meta as cache_set_user_team_meta,
    get_group_excluded_attrs as cache_get_excluded_attrs,
    set_group_excluded_attrs as cache_set_excluded_attrs,
    invalidate_group_excluded_attrs as cache_invalidate_excluded_attrs,
)
from rbac.model import PermissionGroupModel, PermissionGroupPermission, PermissionModel
from rbac.schemas.request import PaginatePermissionGroupRequest
from team.model import UserTeamModel


class RbacRepository:
    """
    RBAC 데이터 접근 계층
    - Redis 캐시 → DB 폴백
    - 팀 스코프(TeamScoped) 일관성 보장:
      * PermissionGroupPermission(매핑 테이블)은 반드시 team_id를 포함해서 생성/삭제/조회
      * 그룹의 team_id는 DB에서 안전하게 조회(get_group_team_id)
    """
    def __init__(self, db: AsyncSession, redis: Redis | None = None):
        self.db = db
        self.redis = redis
        self.common = CommonService()

    # ─────────────────────────────────────────────────────────
    # 내부 유틸: 그룹의 team_id/버전 조회
    # ─────────────────────────────────────────────────────────
    async def get_group_team_id(self, group_id: int) -> Optional[int]:
        return await self.db.scalar(
            select(PermissionGroupModel.team_id).where(PermissionGroupModel.id == group_id)
        )

    async def get_group_version(self, group_id: int) -> Optional[int]:
        return await self.db.scalar(
            select(PermissionGroupModel.version).where(PermissionGroupModel.id == group_id)
        )

    async def bump_group_version(self, group_id: int) -> Optional[int]:
        """
        그룹 버전을 +1 증가시키고 새 버전을 반환.
        - DML update → flush
        """
        current = await self.get_group_version(group_id)
        if current is None:
            return None
        newv = int(current) + 1
        await self.db.execute(
            update(PermissionGroupModel)
            .where(PermissionGroupModel.id == group_id)
            .values(version=newv, updated_at=func.now())
        )
        await self.db.flush()
        return newv

    async def list_active_member_pairs_of_group(self, group_id: int) -> list[tuple[int, int]]:
        """
        해당 그룹에 '활성'으로 속한 멤버들의 (user_id, team_id) 목록
        """
        rows = await self.db.execute(
            select(UserTeamModel.user_id, UserTeamModel.team_id).where(
                UserTeamModel.permission_group_id == group_id,
                UserTeamModel.is_active.is_(True),
            )
        )
        return [(int(u), int(t)) for (u, t) in rows.all()]

    # ─────────────────────────────────────────────────────────
    # 유저 권한 메타 로드(캐시 → DB 폴백)
    # ─────────────────────────────────────────────────────────
    async def get_user_perm_meta(
        self,
        user_id: int,
        *,
        team_id: Optional[int],
    ) -> Tuple[Optional[Set[str]], Optional[int], Optional[int], bool]:
        """
        반환: (codes, group_id, version, is_admin_group)
          - is_admin_group=True 이면 codes=None (모든 권한 허용)
          - version: PermissionGroupModel.version (없으면 None)
        """
        if team_id is None:
            return set(), None, None, False

        group_id: Optional[int] = None
        is_admin_group = False
        version: Optional[int] = None

        # 1) USER_TEAM_META 캐시 조회
        if self.redis:
            meta = await get_user_team_meta(self.redis, user_id, team_id)
            if meta:
                group_id, is_admin_group, version = meta

        # 2) 캐시 미스면 DB에서 로드
        if group_id is None and not is_admin_group:
            user_team = await self.db.scalar(
                select(UserTeamModel).where(
                    UserTeamModel.user_id == user_id,
                    UserTeamModel.team_id == team_id,
                    UserTeamModel.is_active.is_(True),
                )
            )
            if not user_team:
                return set(), None, None, False

            group_id = getattr(user_team, "permission_group_id", None)

            if group_id is not None:
                group = await self.db.scalar(
                    select(PermissionGroupModel).where(
                        PermissionGroupModel.id == group_id,
                        PermissionGroupModel.team_id == team_id,
                        PermissionGroupModel.is_active.is_(True),
                    )
                )
                if group:
                    is_admin_group = bool(getattr(group, "is_admin", False))
                    version = int(getattr(group, "version", None)) if getattr(group, "version", None) is not None else None

            if self.redis:
                await cache_set_user_team_meta(self.redis, user_id, team_id, group_id, is_admin_group, version)

        if is_admin_group:
            return None, group_id, version, True

        if group_id is None:
            return set(), None, version, False

        # 3) 그룹 코드셋 조회(캐시 → DB)
        codes: Optional[Set[str]] = None
        if self.redis:
            codes = await get_group_codes(self.redis, group_id)

        if codes is None:
            g_team_id = await self.get_group_team_id(group_id)
            rows = await self.db.execute(
                select(PermissionModel.code)
                .select_from(
                    join(
                        PermissionGroupPermission,
                        PermissionModel,
                        PermissionGroupPermission.permission_id == PermissionModel.id,
                    )
                )
                .where(
                    PermissionGroupPermission.group_id == group_id,
                    PermissionGroupPermission.team_id == g_team_id,
                    PermissionGroupPermission.is_active.is_(True),
                    PermissionModel.is_active.is_(True),
                )
            )
            codes = {r[0] for r in rows.all() if r and r[0]}

            if self.redis:
                await cache_set_group_codes(self.redis, group_id, codes)

        return codes, group_id, version, False

    # ─────────────────────────────────────────────────────────
    # 그룹/코드 관리 쿼리
    # ─────────────────────────────────────────────────────────
    async def get_group(self, *, group_id: int, team_id: int) -> Optional[PermissionGroupModel]:
        return await self.db.scalar(
            select(PermissionGroupModel).where(
                PermissionGroupModel.id == group_id,
                PermissionGroupModel.team_id == team_id,
                PermissionGroupModel.is_active.is_(True),
            )
        )

    async def get_group_codes_set(self, *, group_id: int) -> Set[str]:
        g_team_id = await self.get_group_team_id(group_id)
        rows = await self.db.execute(
            select(PermissionModel.code)
            .select_from(
                join(
                    PermissionGroupPermission, PermissionModel,
                    PermissionGroupPermission.permission_id == PermissionModel.id
                )
            )
            .where(
                PermissionGroupPermission.group_id == group_id,
                PermissionGroupPermission.team_id == g_team_id,
                PermissionGroupPermission.is_active.is_(True),
                PermissionModel.is_active.is_(True),
            )
        )
        return {r[0] for r in rows.all() if r and r[0]}

    async def create_group(
        self, *, team_id: int, name: str, is_admin: bool = False,
        is_system: bool = False, system_key: Optional[str] = None,
        excluded_attribute_ids: Optional[List[int]] = None,
    ) -> PermissionGroupModel:
        grp = PermissionGroupModel(
            team_id=team_id,
            name=name,
            is_admin=is_admin,
            is_system=is_system,
            system_key=system_key,
            excluded_attribute_ids=excluded_attribute_ids,
            # version: DB default 1 가정
        )
        self.db.add(grp)
        await self.db.flush()
        await self.db.refresh(grp)
        return grp

    async def get_excluded_attribute_ids(self, *, group_id: int) -> Set[int]:
        """캐시 → DB 폴백으로 excluded_attribute_ids 조회"""
        if self.redis:
            cached = await cache_get_excluded_attrs(self.redis, group_id)
            if cached is not None:
                return cached

        row = await self.db.scalar(
            select(PermissionGroupModel.excluded_attribute_ids)
            .where(PermissionGroupModel.id == group_id)
        )
        ids = set(row) if row else set()

        if self.redis:
            await cache_set_excluded_attrs(self.redis, group_id, ids)

        return ids

    async def set_excluded_attribute_ids(self, *, group_id: int, excluded_attribute_ids: List[int]) -> None:
        """제외 속성 ID 목록 갱신 + 캐시 무효화"""
        await self.db.execute(
            update(PermissionGroupModel)
            .where(PermissionGroupModel.id == group_id)
            .values(excluded_attribute_ids=excluded_attribute_ids or [], updated_at=func.now())
        )
        await self.db.flush()

        if self.redis:
            await cache_invalidate_excluded_attrs(self.redis, group_id)

    async def rename_group(self, *, group_id: int, name: str) -> None:
        g = await self.db.scalar(select(PermissionGroupModel).where(PermissionGroupModel.id == group_id))
        if not g:
            return
        g.name = name
        await self.db.flush()

    async def delete_group(self, *, group_id: int) -> None:
        await self.db.execute(delete(PermissionGroupModel).where(PermissionGroupModel.id == group_id))

    async def count_group_members(self, *, group_id: int) -> int:
        q = (
            select(func.count(UserTeamModel.user_id))
            .where(
                UserTeamModel.permission_group_id == group_id,
                UserTeamModel.is_active.is_(True),
            )
        )
        return (await self.db.execute(q)).scalar_one()

    async def get_permission_id_map(self) -> Dict[str, int]:
        rows = await self.db.execute(
            select(PermissionModel.code, PermissionModel.id)
            .where(PermissionModel.is_active.is_(True))
        )
        return {code: pid for code, pid in rows.all()}

    # ─────────────────────────────────────────────────────────
    # 그룹 코드 '완전 교체'
    #   - 호출자는 보통 서비스(RbacService)이며,
    #     서비스에서: bump_version → invalidate caches → invalidate user metas
    # ─────────────────────────────────────────────────────────
    async def set_group_codes(self, *, group_id: int, codes: Iterable[str]) -> Set[str]:
        target = set(codes or [])
        current = await self.get_group_codes_set(group_id=group_id)

        to_add = target - current
        to_del = current - target

        id_map = await self.get_permission_id_map()
        add_ids = [id_map[c] for c in to_add if c in id_map]
        del_ids = [id_map[c] for c in to_del if c in id_map]

        g_team_id = await self.get_group_team_id(group_id)

        if del_ids:
            await self.db.execute(
                delete(PermissionGroupPermission).where(
                    PermissionGroupPermission.group_id == group_id,
                    PermissionGroupPermission.team_id == g_team_id,
                    PermissionGroupPermission.permission_id.in_(del_ids),
                )
            )

        for pid in add_ids:
            self.db.add(PermissionGroupPermission(
                team_id=g_team_id,
                group_id=group_id,
                permission_id=pid,
            ))

        await self.db.flush()
        return target & set(id_map.keys())

    # ─────────────────────────────────────────────────────────
    # 그룹 코드 '증감 패치'
    # ─────────────────────────────────────────────────────────
    async def patch_group_codes(self, *, group_id: int, op: str, codes: Iterable[str]) -> Set[str]:
        id_map = await self.get_permission_id_map()
        valid = [id_map[c] for c in (codes or []) if c in id_map]

        g_team_id = await self.get_group_team_id(group_id)

        if op == "add":
            for pid in set(valid):
                self.db.add(PermissionGroupPermission(
                    team_id=g_team_id,
                    group_id=group_id,
                    permission_id=pid,
                ))
            await self.db.flush()
        elif op == "remove":
            if valid:
                await self.db.execute(
                    delete(PermissionGroupPermission).where(
                        PermissionGroupPermission.group_id == group_id,
                        PermissionGroupPermission.team_id == g_team_id,
                        PermissionGroupPermission.permission_id.in_(valid),
                    )
                )
        else:
            pass

        return await self.get_group_codes_set(group_id=group_id)

    # ─────────────────────────────────────────────────────────
    # ▼ 커서 페이지네이션
    # ─────────────────────────────────────────────────────────
    async def list_groups_paginated(
        self, *, team_id: int, request: PaginatePermissionGroupRequest
    ) -> CursorPaginationResult[PermissionGroupModel]:
        base = (
            select(PermissionGroupModel)
            .where(
                PermissionGroupModel.team_id == team_id,
                PermissionGroupModel.is_active.is_(True),
            )
        )

        return await self.common.paginate(
            request=request,
            model=PermissionGroupModel,
            session=self.db,
            base_query=base,
            path="rbac/groups",
        )

    # ── Delta Sync: 권한 그룹 (hard-delete → all_ids) ──────────────
    async def sync_delta(self, team_id: int, since: datetime):
        """
        since 이후 변경된 활성 그룹 + 전체 활성 그룹 ID (hard-delete 도메인)
        """
        base = (
            select(PermissionGroupModel)
            .where(PermissionGroupModel.team_id == team_id)
        )
        return await self.common.sync_delta(
            model=PermissionGroupModel,
            session=self.db,
            since=since,
            team_id=team_id,
            base_query=base,
            use_soft_delete=False,
        )

    # ─────────────────────────────────────────────────────────
    # 배치 집계
    # ─────────────────────────────────────────────────────────
    async def bulk_group_members_count(self, group_ids: list[int]) -> dict[int, int]:
        if not group_ids:
            return {}
        stmt = (
            select(
                UserTeamModel.permission_group_id,
                func.count(UserTeamModel.user_id)
            )
            .where(
                UserTeamModel.permission_group_id.in_(group_ids),
                UserTeamModel.is_active.is_(True),
            )
            .group_by(UserTeamModel.permission_group_id)
        )
        rows = (await self.db.execute(stmt)).all()
        return {int(gid): int(cnt) for gid, cnt in rows}

    async def bulk_group_code_count(self, group_ids: list[int]) -> dict[int, int]:
        if not group_ids:
            return {}
        stmt = (
            select(
                PermissionGroupPermission.group_id,
                func.count(PermissionGroupPermission.permission_id)
            )
            .select_from(
                join(
                    PermissionGroupPermission,
                    PermissionModel,
                    PermissionGroupPermission.permission_id == PermissionModel.id,
                )
            )
            .where(
                PermissionGroupPermission.group_id.in_(group_ids),
                PermissionGroupPermission.is_active.is_(True),
                PermissionModel.is_active.is_(True),
            )
            .group_by(PermissionGroupPermission.group_id)
        )
        rows = (await self.db.execute(stmt)).all()
        return {int(gid): int(cnt) for gid, cnt in rows}
