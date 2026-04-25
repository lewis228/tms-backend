"""Auth 서비스 — 이메일/비밀번호 인증, JWT 발급, refresh."""
from __future__ import annotations

from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.domains.users.models import User
from app.domains.users.repository import UserRepository
from app.domains.users.service import UserService


class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self.user_repo = user_repo

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.user_repo.get_by_email(email)
        if not user or not user.is_active:
            raise UnauthorizedError("Invalid credentials", code="ERR_AUTH_INVALID")
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid credentials", code="ERR_AUTH_INVALID")
        await UserService(self.user_repo).touch_login(user)
        return user

    @staticmethod
    def issue_tokens(user: User) -> tuple[str, str]:
        access = create_access_token(
            user_id=user.id, tenant_id=user.tenant_id, role=user.role.value
        )
        refresh = create_refresh_token(
            user_id=user.id, tenant_id=user.tenant_id, role=user.role.value
        )
        return access, refresh

    async def refresh(self, refresh_token: str) -> tuple[User, str, str]:
        payload = decode_token(refresh_token, expected_type="refresh")
        user = await self.user_repo.get(payload["sub"])
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or inactive", code="ERR_AUTH_INVALID")
        access, new_refresh = self.issue_tokens(user)
        return user, access, new_refresh
