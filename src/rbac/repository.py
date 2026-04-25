from __future__ import annotations
from typing import Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from rbac.model import PermissionGroupModel, PermissionGroupPermission, PermissionModel
from rbac.cache_service import RbacCacheService
from team.model import UserTeamModel


class RbacRepository:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.cache = RbacCacheService(redis)

    async def get_user_perm_meta(self, user_id: int, team_id: int = None) -> Tuple[Optional[Set[str]], Optional[int], Optional[int], bool]:
        if team_id is None:
            return None, None, None, False

        cached = await self.cache.get_user_team_meta(user_id, team_id)
        if cached:
            group_id = cached.get("gid")
            version = cached.get("ver", 1)
            is_admin = cached.get("adm", False)
            if is_admin:
                return set(), group_id, version, True
            codes = await self.cache.get_group_codes(group_id, version)
            if codes is not None:
                return codes, group_id, version, False

        stmt = select(UserTeamModel).where(
            UserTeamModel.user_id == user_id,
            UserTeamModel.team_id == team_id,
            UserTeamModel.is_active.is_(True),
        )
        ut = await self.db.scalar(stmt)
        if not ut or not ut.permission_group_id:
            return None, None, None, False

        group_id = ut.permission_group_id
        grp = await self.db.scalar(
            select(PermissionGroupModel).where(PermissionGroupModel.id == group_id)
        )
        if not grp:
            return None, None, None, False

        version = grp.version
        is_admin = grp.is_admin

        meta = {"gid": group_id, "ver": version, "adm": is_admin}
        await self.cache.set_user_team_meta(user_id, team_id, meta)

        if is_admin:
            return set(), group_id, version, True

        code_rows = await self.db.execute(
            select(PermissionModel.code)
            .join(PermissionGroupPermission, PermissionGroupPermission.permission_id == PermissionModel.id)
            .where(PermissionGroupPermission.group_id == group_id, PermissionGroupPermission.team_id == team_id)
        )
        codes = {row[0] for row in code_rows.all()}
        await self.cache.set_group_codes(group_id, version, codes)
        return codes, group_id, version, False

    async def get_excluded_attribute_ids(self, group_id: int) -> Set[int]:
        grp = await self.db.scalar(
            select(PermissionGroupModel).where(PermissionGroupModel.id == group_id)
        )
        if not grp or not grp.excluded_attribute_ids:
            return set()
        return set(grp.excluded_attribute_ids)
