"""Driver Repository."""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.domains.drivers.models import Driver
from app.domains.users.models import User


class DriverRepository:
    def __init__(self, db: AsyncSession, *, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def _scope(self, stmt):
        return stmt.where(
            Driver.is_deleted.is_(False), Driver.tenant_id == self.tenant_id
        )

    async def get(self, driver_id: str) -> Driver | None:
        stmt = self._scope(select(Driver).where(Driver.id == driver_id))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> Driver | None:
        stmt = self._scope(select(Driver).where(Driver.user_id == user_id))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_paged(
        self,
        params: PageParams,
        *,
        active_only: bool = False,
        q: str | None = None,
    ) -> tuple[list[Driver], int]:
        base = self._scope(select(Driver))
        if active_only:
            base = base.where(Driver.is_active.is_(True))
        if q:
            like = f"%{q.strip()}%"
            base = base.join(User, Driver.user_id == User.id).where(
                or_(
                    User.name.ilike(like),
                    User.email.ilike(like),
                    User.phone.ilike(like),
                    Driver.truck_number.ilike(like),
                )
            )
        total = (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        stmt = base.order_by(Driver.created_at.desc()).offset(params.offset).limit(params.limit)
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, total

    async def add(self, driver: Driver) -> Driver:
        self.db.add(driver)
        await self.db.flush()
        return driver

    async def soft_delete(self, driver: Driver) -> None:
        driver.is_deleted = True
        await self.db.flush()
