from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from team.model import TeamModel
from team.repository import TeamRepository
from team.schemas.response import (
    TeamResponseSchema,
    TeamMemberResponseSchema,
    TeamUsageDailyPoint,
    TeamUsageResponseSchema,
)
from user.repository import UserRepository
from cache.redis_connection import redis_client
from auth.dependencies.rate_limit import PLAN_LIMITS
from common.exceptions.base import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)


class TeamService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TeamRepository(db)
        # User lookups are cross-domain but small — instantiating a local
        # repo here is cheaper than wiring dependency injection for a few
        # call sites.
        self.user_repo = UserRepository(db)

    async def create_team(
        self,
        *,
        name: str,
        creator_user_id: int,
        email: str | None = None,
        plan: str = "free",
    ) -> TeamResponseSchema:
        team = TeamModel(
            name=name,
            email=email,
            plan=plan,
            created_by_user_id=creator_user_id,
        )
        team = await self.repo.create_team(team)
        await self.repo.add_member(user_id=creator_user_id, team_id=team.id)
        return TeamResponseSchema.model_validate(team)

    async def get_team(self, team_id: int) -> TeamResponseSchema:
        team = await self.repo.get_team_by_id(team_id)
        if not team:
            raise NotFoundException("Team")
        return TeamResponseSchema.model_validate(team)

    async def update_team(
        self,
        team_id: int,
        *,
        fields: Dict[str, Any],
        updated_by_user_id: Optional[int] = None,
    ) -> TeamResponseSchema:
        """Partial update — only the keys present in `fields` get written.
        The router should pass the Pydantic payload via
        `model_dump(exclude_unset=True)` so this stays a true PATCH (keys
        the client didn't send are left untouched, while explicit nulls do
        clear nullable columns)."""
        team = await self.repo.get_team_by_id(team_id)
        if not team:
            raise NotFoundException("Team")

        allowed = {"name", "email", "plan", "memo", "timezone"}
        for key, value in fields.items():
            if key in allowed:
                setattr(team, key, value)

        if updated_by_user_id is not None:
            team.updated_by_user_id = updated_by_user_id

        await self.db.flush()
        await self.db.refresh(team)
        return TeamResponseSchema.model_validate(team)

    async def delete_team(self, team_id: int) -> None:
        team = await self.repo.get_team_by_id(team_id)
        if team:
            team.is_active = False
            await self.db.flush()

    # ── Membership management ──────────────────────────────────

    async def list_members(self, team_id: int) -> List[TeamMemberResponseSchema]:
        # Caller should have already verified the requester belongs to the
        # team (router does this). The team-existence check is defensive
        # so a 404 surfaces instead of an empty list for deleted teams.
        team = await self.repo.get_team_by_id(team_id)
        if not team:
            raise NotFoundException("Team")

        memberships = await self.repo.list_members(team_id)
        return [
            TeamMemberResponseSchema(
                id=m.id,
                user_id=m.user_id,
                email=m.user.email,
                name=m.user.name,
                role=m.user.role,
                auth_provider=m.user.auth_provider,
                permission_group_id=m.permission_group_id,
                created_at=m.created_at,
            )
            for m in memberships
        ]

    async def invite_member(
        self,
        *,
        team_id: int,
        email: str,
        permission_group_id: Optional[int] = None,
    ) -> TeamMemberResponseSchema:
        team = await self.repo.get_team_by_id(team_id)
        if not team:
            raise NotFoundException("Team")

        user = await self.user_repo.get_user_by_email(email)
        if not user:
            # Deliberately specific so the UI can prompt the admin to have
            # the user sign up first. Email-invite-with-token flows are out
            # of scope for this phase.
            raise BadRequestException(
                "해당 이메일로 가입된 사용자가 없습니다. 사용자가 먼저 회원가입을 해야 합니다.",
                code="USER_NOT_FOUND",
            )

        # Prefer reactivation over duplicate inserts when the user was
        # previously removed — keeps `user_teams` from accumulating dead
        # rows for churny teams.
        existing = await self.repo.get_membership(
            team_id=team_id, user_id=user.id, include_inactive=True,
        )
        if existing and existing.is_active:
            raise ConflictException(
                "이미 팀의 멤버입니다.",
            )

        if existing is not None:
            membership = await self.repo.reactivate_membership(
                existing, permission_group_id=permission_group_id,
            )
        else:
            membership = await self.repo.add_member(
                user_id=user.id,
                team_id=team_id,
                permission_group_id=permission_group_id,
            )

        return TeamMemberResponseSchema(
            id=membership.id,
            user_id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            auth_provider=user.auth_provider,
            permission_group_id=membership.permission_group_id,
            created_at=membership.created_at,
        )

    async def remove_member(self, *, team_id: int, user_id: int) -> None:
        membership = await self.repo.get_membership(
            team_id=team_id, user_id=user_id,
        )
        if not membership:
            raise NotFoundException("Team member")
        await self.repo.deactivate_membership(membership)

    # ── Usage analytics ──────────────────────────────────────

    async def get_usage(
        self,
        team_id: int,
        *,
        days: int = 30,
    ) -> TeamUsageResponseSchema:
        """Read per-day API-call counters out of Redis for the given team.
        Keys follow the rate limiter's format
        (`rate_limit:{team_id}:{YYYY-MM-DD}`); missing keys mean zero
        calls on that day. Days are returned oldest-first so the Usage
        dashboard can plot them without re-sorting client-side."""
        team = await self.repo.get_team_by_id(team_id)
        if not team:
            raise NotFoundException("Team")

        plan = team.plan or "free"
        daily_limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

        now = datetime.now(timezone.utc)
        dates = [
            (now - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(days)
        ]
        keys = [f"rate_limit:{team_id}:{d}" for d in dates]
        # mget fetches every key in a single round-trip — much cheaper than
        # N sequential GETs when days=30.
        raw_values = await redis_client.mget(*keys) if keys else []

        points: list[TeamUsageDailyPoint] = []
        total = 0
        today_count = 0
        for idx, (date, raw) in enumerate(zip(dates, raw_values)):
            count = int(raw) if raw is not None else 0
            total += count
            if idx == 0:  # today sits at index 0 before we reverse
                today_count = count
            points.append(TeamUsageDailyPoint(date=date, count=count))
        # Oldest → newest so charts render left-to-right naturally.
        points.reverse()

        return TeamUsageResponseSchema(
            daily=points,
            total_count=total,
            today_count=today_count,
            plan=plan,
            daily_limit=daily_limit,
        )
