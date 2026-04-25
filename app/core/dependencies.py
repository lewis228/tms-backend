"""FastAPI 의존성.

- DB / DBReadOnly: AsyncSession (write/read)
- CurrentUser: JWT 디코드 → User 객체 + 컨텍스트 검증
- TenantID: 일반 사용자 = JWT.tenant_id, SUPER_ADMIN = X-Tenant-ID 헤더
- require_role(*roles): 역할 게이트
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_db_replica
from app.core.exceptions import ForbiddenError, TenantMismatchError, UnauthorizedError
from app.core.security import decode_token

DB = Annotated[AsyncSession, Depends(get_db)]
DBReadOnly = Annotated[AsyncSession, Depends(get_db_replica)]

_bearer = HTTPBearer(auto_error=False)


_ROLE_RANK = {"DRIVER": 0, "DISPATCHER": 1, "ADMIN": 2, "SUPER_ADMIN": 3}


class CurrentUserPayload:
    __slots__ = ("user_id", "tenant_id", "role")

    def __init__(self, user_id: str, tenant_id: str | None, role: str) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role

    def is_super_admin(self) -> bool:
        return self.role == "SUPER_ADMIN"

    def rank(self) -> int:
        return _ROLE_RANK.get(self.role, -1)


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUserPayload:
    if creds is None:
        raise UnauthorizedError("Missing bearer token")
    payload = decode_token(creds.credentials, expected_type="access")
    user_id = payload.get("sub")
    role = payload.get("role")
    if not user_id or not role:
        raise UnauthorizedError("Invalid token payload")
    return CurrentUserPayload(
        user_id=user_id, tenant_id=payload.get("tenant_id"), role=role
    )


CurrentUser = Annotated[CurrentUserPayload, Depends(get_current_user)]


async def get_tenant_id(
    user: CurrentUser,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> str:
    """일반 사용자: JWT.tenant_id. SUPER_ADMIN: X-Tenant-ID 헤더.

    일반 사용자가 X-Tenant-ID 를 보내고 JWT.tenant_id 와 다르면 거부.
    """
    if user.is_super_admin():
        if not x_tenant_id:
            raise ForbiddenError(
                "X-Tenant-ID header required for SUPER_ADMIN", code="ERR_TENANT_REQUIRED"
            )
        return x_tenant_id
    if not user.tenant_id:
        raise ForbiddenError("User has no tenant", code="ERR_NO_TENANT")
    if x_tenant_id and x_tenant_id != user.tenant_id:
        raise TenantMismatchError()
    return user.tenant_id


TenantID = Annotated[str, Depends(get_tenant_id)]


def require_role(*roles: str):
    """라우터 dependencies=[require_role("ADMIN", "SUPER_ADMIN")] 식으로 사용."""
    allowed = {r.upper() for r in roles}

    async def _checker(user: CurrentUser) -> None:
        if user.role not in allowed:
            raise ForbiddenError(
                f"Role {user.role} not in {sorted(allowed)}", code="ERR_FORBIDDEN_ROLE"
            )

    return Depends(_checker)


def require_min_role(role: str):
    """최소 등급 게이트. require_min_role('DISPATCHER') = DISPATCHER 이상 통과."""
    threshold = _ROLE_RANK.get(role.upper(), 999)

    async def _checker(user: CurrentUser) -> None:
        if user.rank() < threshold:
            raise ForbiddenError(
                f"Requires {role}+", code="ERR_FORBIDDEN_ROLE"
            )

    return Depends(_checker)


def get_request(request: Request) -> Request:
    return request
