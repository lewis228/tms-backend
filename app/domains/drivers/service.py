"""Driver 서비스.

Driver 생성 = User(role=DRIVER, must_change_password=True) + Driver 행 생성.
임시 비번은 응답에 1회만 노출.
"""
from __future__ import annotations

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_temp_password, hash_password
from app.domains.drivers.models import Driver
from app.domains.drivers.repository import DriverRepository
from app.domains.drivers.schema import DriverCreateRequest, DriverUpdateRequest
from app.domains.users.models import User
from app.domains.users.repository import UserRepository
from app.models.enums import UserRole


class DriverService:
    def __init__(
        self, repo: DriverRepository, user_repo: UserRepository, tenant_id: str
    ) -> None:
        self.repo = repo
        self.user_repo = user_repo
        self.tenant_id = tenant_id

    async def create(self, payload: DriverCreateRequest) -> tuple[Driver, User, str]:
        if await self.user_repo.get_by_email(payload.email):
            raise ConflictError(f"Email '{payload.email}' already exists")
        temp_pw = generate_temp_password()
        user = User(
            tenant_id=self.tenant_id,
            email=payload.email,
            name=payload.name,
            role=UserRole.DRIVER,
            phone=payload.phone,
            password_hash=hash_password(temp_pw),
            is_active=True,
            must_change_password=True,
        )
        await self.user_repo.add(user)
        driver = Driver(
            tenant_id=self.tenant_id,
            user_id=user.id,
            license_number=payload.license_number,
            license_state=payload.license_state,
            truck_number=payload.truck_number,
            note=payload.note,
            is_active=True,
        )
        await self.repo.add(driver)
        await self.repo.db.commit()
        await self.repo.db.refresh(driver)
        await self.repo.db.refresh(user)
        return driver, user, temp_pw

    async def get(self, driver_id: str) -> tuple[Driver, User]:
        driver = await self.repo.get(driver_id)
        if not driver:
            raise NotFoundError("Driver not found")
        user = await self.user_repo.get(driver.user_id)
        if not user:
            raise NotFoundError("Driver user missing")
        return driver, user

    async def list_paged(self, params, *, active_only: bool = False):
        rows, total = await self.repo.list_paged(params, active_only=active_only)
        # 같은 트랜잭션에서 user 정보 한 번에
        users = {}
        if rows:
            from sqlalchemy import select as sa_select

            from app.domains.users.models import User as UserModel

            stmt = sa_select(UserModel).where(UserModel.id.in_([r.user_id for r in rows]))
            for u in (await self.repo.db.execute(stmt)).scalars():
                users[u.id] = u
        return rows, users, total

    async def update(self, driver_id: str, payload: DriverUpdateRequest) -> tuple[Driver, User]:
        driver, user = await self.get(driver_id)
        data = payload.model_dump(exclude_unset=True)
        for k in ("name", "phone"):
            if k in data:
                setattr(user, k, data.pop(k))
        for k, v in data.items():
            setattr(driver, k, v)
        await self.repo.db.flush()
        await self.repo.db.commit()
        await self.repo.db.refresh(driver)
        await self.repo.db.refresh(user)
        return driver, user

    async def delete(self, driver_id: str) -> None:
        driver, user = await self.get(driver_id)
        await self.repo.soft_delete(driver)
        await self.user_repo.soft_delete(user)
        await self.repo.db.commit()
