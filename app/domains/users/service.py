"""User 서비스 — 역할 계층 검증, 비밀번호 해싱."""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.security import hash_password, verify_password
from app.domains.users.models import User
from app.domains.users.repository import UserRepository
from app.domains.users.schema import (
    PasswordChangeRequest,
    UserCreateRequest,
    UserUpdateRequest,
)
from app.models.enums import UserRole

_ROLE_RANK = {
    UserRole.DRIVER: 0,
    UserRole.DISPATCHER: 1,
    UserRole.ADMIN: 2,
    UserRole.SUPER_ADMIN: 3,
}


class UserService:
    def __init__(
        self,
        repo: UserRepository,
        *,
        actor_role: UserRole | None = None,
        actor_tenant_id: str | None = None,
    ) -> None:
        self.repo = repo
        self.actor_role = actor_role
        self.actor_tenant_id = actor_tenant_id

    def _ensure_can_assign_role(self, target: UserRole) -> None:
        if self.actor_role is None:
            return
        if target == UserRole.SUPER_ADMIN:
            raise ForbiddenError(
                "SUPER_ADMIN cannot be created via API", code="ERR_SUPER_ADMIN_FORBIDDEN"
            )
        actor_rank = _ROLE_RANK.get(self.actor_role, -1)
        target_rank = _ROLE_RANK.get(target, 999)
        if target_rank > actor_rank:
            raise ForbiddenError(
                f"Cannot create user with role {target.value}",
                code="ERR_ROLE_HIERARCHY",
            )

    async def create(self, payload: UserCreateRequest, *, tenant_id: str | None) -> User:
        self._ensure_can_assign_role(payload.role)
        if await self.repo.get_by_email(payload.email):
            raise ConflictError(f"Email '{payload.email}' already exists")
        # SUPER_ADMIN 가 다른 테넌트 사용자 만들 때 X-Tenant-ID 로 결정된 tenant_id 사용
        # 일반 사용자: 자기 tenant_id 만 가능
        target_tenant = payload.tenant_id or tenant_id
        if self.actor_role and self.actor_role != UserRole.SUPER_ADMIN:
            if target_tenant != self.actor_tenant_id:
                raise ForbiddenError("Cannot create user in another tenant")
        user = User(
            tenant_id=target_tenant,
            email=payload.email,
            name=payload.name,
            role=payload.role,
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            is_active=True,
            must_change_password=False,
        )
        await self.repo.add(user)
        await self.repo.db.commit()
        await self.repo.db.refresh(user)
        return user

    async def get(self, user_id: str) -> User:
        u = await self.repo.get(user_id)
        if not u:
            raise NotFoundError("User not found")
        return u

    async def get_or_none(self, user_id: str) -> User | None:
        return await self.repo.get(user_id)

    async def list_paged(self, params):
        return await self.repo.list_paged(params)

    async def update(self, user_id: str, payload: UserUpdateRequest) -> User:
        user = await self.get(user_id)
        if payload.role is not None:
            self._ensure_can_assign_role(payload.role)
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(user, k, v)
        await self.repo.db.flush()
        await self.repo.db.commit()
        await self.repo.db.refresh(user)
        return user

    async def delete(self, user_id: str) -> None:
        user = await self.get(user_id)
        await self.repo.soft_delete(user)
        await self.repo.db.commit()

    async def change_password(
        self, user: User, payload: PasswordChangeRequest, *, force: bool = False
    ) -> User:
        if not force:
            if not payload.current_password or not verify_password(
                payload.current_password, user.password_hash
            ):
                raise ValidationError("Current password mismatch", code="ERR_PASSWORD_MISMATCH")
        user.password_hash = hash_password(payload.new_password)
        user.must_change_password = False
        await self.repo.db.flush()
        await self.repo.db.commit()
        await self.repo.db.refresh(user)
        return user

    async def touch_login(self, user: User) -> None:
        user.last_login_at = datetime.now(timezone.utc)
        await self.repo.db.flush()
        await self.repo.db.commit()
