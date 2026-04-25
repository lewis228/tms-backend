from __future__ import annotations
from typing import Any, List, Optional, Literal
from pydantic import EmailStr, model_validator
from common.schemas.base import ResponseSchema
from common.schemas.nested import FileNestedSchema
from user.const.roles import RolesEnum


class UserTeamRowResponseSchema(ResponseSchema):
    id: int
    team_id: int
    team_name: Optional[str] = None
    permission_group_id: Optional[int] = None

    # `team_name` is not a column on `user_teams` — it lives on `teams.name`
    # via the `UserTeamModel.team` relationship. With `from_attributes=True`,
    # Pydantic reads attributes off the ORM object directly, so `team_name`
    # would silently resolve to `None`. This validator intercepts the ORM
    # instance in `model_validate(...)` and exposes the joined name. Callers
    # must ensure the `team` relationship is eager-loaded (see
    # `UserRepository._with_options_detail` which already does so via
    # `selectinload(UserTeamModel.team).options(load_only(TeamModel.name))`).
    @model_validator(mode="before")
    @classmethod
    def _resolve_team_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        team = getattr(data, "team", None)
        return {
            "id": getattr(data, "id", None),
            "team_id": getattr(data, "team_id", None),
            "team_name": getattr(team, "name", None) if team is not None else None,
            "permission_group_id": getattr(data, "permission_group_id", None),
        }


class UserListItemResponseSchema(ResponseSchema):
    id: int
    email: Optional[EmailStr] = None
    role: RolesEnum
    name: Optional[str] = None
    phone: Optional[str] = None
    auth_provider: str = "email"
    notification_email: Optional[str] = None
    event_notification_enabled: bool = False
    language: Optional[str] = "auto"
    teams: List[UserTeamRowResponseSchema] = []
    files: List[FileNestedSchema] = []


class UserDetailResponseSchema(UserListItemResponseSchema):
    pass


class UserResponseSchema(ResponseSchema):
    id: int
    email: Optional[EmailStr] = None
    role: RolesEnum
    auth_provider: str = "email"


class TokenPayloadResponseSchema(ResponseSchema):
    id: int
    sid: Optional[str] = None
    did: Optional[str] = None
    jti: Optional[str] = None
    type: str
    iat: Optional[int] = None
    exp: int


class UserDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["user"] = "user"
    deleted: bool = True
    soft_deleted: bool = False
    teams_cleaned: int = 0
