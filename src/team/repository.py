from __future__ import annotations
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from team.model import TeamModel, UserTeamModel


class TeamRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_team_by_id(self, team_id: int) -> Optional[TeamModel]:
        stmt = select(TeamModel).where(TeamModel.id == team_id, TeamModel.is_active.is_(True))
        return await self.db.scalar(stmt)

    async def create_team(self, team: TeamModel) -> TeamModel:
        self.db.add(team)
        await self.db.flush()
        await self.db.refresh(team)
        return team

    async def add_member(self, user_id: int, team_id: int, permission_group_id: int = None) -> UserTeamModel:
        ut = UserTeamModel(user_id=user_id, team_id=team_id, permission_group_id=permission_group_id)
        self.db.add(ut)
        await self.db.flush()
        return ut

    async def list_members(self, team_id: int) -> List[UserTeamModel]:
        """Active memberships only. Joined with UserModel so the service can
        build TeamMemberResponseSchema without a second round-trip."""
        stmt = (
            select(UserTeamModel)
            .where(
                UserTeamModel.team_id == team_id,
                UserTeamModel.is_active.is_(True),
            )
            .options(selectinload(UserTeamModel.user))
            .order_by(UserTeamModel.id.asc())
        )
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def get_membership(
        self,
        *,
        team_id: int,
        user_id: int,
        include_inactive: bool = False,
    ) -> Optional[UserTeamModel]:
        """Return the membership row linking user ↔ team, if any. When
        `include_inactive=True` a soft-removed membership is also returned
        so the caller can reactivate it instead of inserting a duplicate."""
        stmt = select(UserTeamModel).where(
            UserTeamModel.team_id == team_id,
            UserTeamModel.user_id == user_id,
        )
        if not include_inactive:
            stmt = stmt.where(UserTeamModel.is_active.is_(True))
        return await self.db.scalar(stmt)

    async def reactivate_membership(
        self,
        membership: UserTeamModel,
        *,
        permission_group_id: Optional[int] = None,
    ) -> UserTeamModel:
        membership.is_active = True
        if permission_group_id is not None:
            membership.permission_group_id = permission_group_id
        await self.db.flush()
        return membership

    async def deactivate_membership(self, membership: UserTeamModel) -> None:
        # Soft delete — preserves history and avoids cascading FK surprises.
        # Reactivation is handled by `reactivate_membership` above.
        membership.is_active = False
        await self.db.flush()
