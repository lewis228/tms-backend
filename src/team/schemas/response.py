from __future__ import annotations
from datetime import datetime
from typing import Optional
from common.schemas.base import ResponseSchema


class TeamResponseSchema(ResponseSchema):
    id: int
    name: str
    email: Optional[str] = None
    plan: str = "free"
    memo: Optional[str] = None
    timezone: Optional[str] = None


class TeamListItemResponseSchema(TeamResponseSchema):
    pass


class TeamMemberResponseSchema(ResponseSchema):
    """A user's membership in a team. `id` is the UserTeam row id — distinct
    from `user_id` — so clients can target the specific membership for
    role changes or removal even if a user re-joins the team."""
    id: int
    user_id: int
    email: str
    name: Optional[str] = None
    role: str
    auth_provider: str = "email"
    permission_group_id: Optional[int] = None
    created_at: Optional[datetime] = None


class TeamUsageDailyPoint(ResponseSchema):
    """A single day's API-call count. `date` is an ISO calendar date
    string (YYYY-MM-DD) in UTC to match how keys are stamped in Redis."""
    date: str
    count: int


class TeamUsageResponseSchema(ResponseSchema):
    """Aggregate API usage for a team, derived from Redis counters that
    the rate limiter increments on every authenticated request. Only
    `auth_type == api_key` traffic is counted — JWT (web app) requests
    aren't metered."""
    daily: list[TeamUsageDailyPoint]
    total_count: int
    today_count: int
    plan: str
    daily_limit: int
