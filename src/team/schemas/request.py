from __future__ import annotations
from typing import Optional
from pydantic import EmailStr, Field
from common.schemas.base import RequestSchema


class CreateTeamRequestSchema(RequestSchema):
    name: str = Field(min_length=1, max_length=80)
    email: Optional[EmailStr] = Field(default=None, max_length=255)
    plan: Optional[str] = Field(default="free", max_length=20)


class UpdateTeamRequestSchema(RequestSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    email: Optional[EmailStr] = Field(None, max_length=255)
    plan: Optional[str] = Field(None, max_length=20)
    memo: Optional[str] = Field(None, max_length=3000)
    timezone: Optional[str] = Field(None, max_length=50)


class InviteMemberRequestSchema(RequestSchema):
    """Invite an existing user to a team by email. Email-based lookup keeps
    the UX simple (admins don't need to know user IDs) but the user must
    already have an account — there's no bundled email invitation flow yet."""
    email: EmailStr
    permission_group_id: Optional[int] = Field(default=None)
