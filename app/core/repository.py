"""BaseRepository — tenant 자동 필터 + soft delete 자동 필터.

- 모든 도메인 Repository 는 이 베이스 상속
- 기본 메서드: get_by_id / list_paged / create / update / soft_delete / count
- 도메인 특수 쿼리는 서브클래스에서 self._base_query() 활용
"""
from __future__ import annotations

from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    model: Type[ModelT]

    def __init__(self, db: AsyncSession, *, tenant_id: str | None = None) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def _base_query(self) -> Select:
        stmt = select(self.model)
        if hasattr(self.model, "is_deleted"):
            stmt = stmt.where(self.model.is_deleted.is_(False))  # type: ignore[attr-defined]
        if self.tenant_id is not None and hasattr(self.model, "tenant_id"):
            stmt = stmt.where(self.model.tenant_id == self.tenant_id)  # type: ignore[attr-defined]
        return stmt

    async def get_by_id(self, id_: str) -> ModelT | None:
        stmt = self._base_query().where(self.model.id == id_)  # type: ignore[attr-defined]
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_paged(
        self,
        params: PageParams,
        *,
        order_by: Any | None = None,
        extra_where: list[Any] | None = None,
    ) -> tuple[Sequence[ModelT], int]:
        stmt = self._base_query()
        if extra_where:
            for w in extra_where:
                stmt = stmt.where(w)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()
        if order_by is None and hasattr(self.model, "created_at"):
            order_by = self.model.created_at.desc()  # type: ignore[attr-defined]
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(params.offset).limit(params.limit)
        rows = (await self.db.execute(stmt)).scalars().all()
        return rows, total

    async def create(self, obj: ModelT) -> ModelT:
        # tenant_id 자동 주입 (없으면)
        if (
            self.tenant_id is not None
            and hasattr(obj, "tenant_id")
            and getattr(obj, "tenant_id", None) is None
        ):
            setattr(obj, "tenant_id", self.tenant_id)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, obj: ModelT, **fields: Any) -> ModelT:
        for k, v in fields.items():
            setattr(obj, k, v)
        await self.db.flush()
        return obj

    async def soft_delete(self, obj: ModelT) -> None:
        if not hasattr(obj, "is_deleted"):
            raise RuntimeError(f"{type(obj).__name__} does not support soft delete")
        setattr(obj, "is_deleted", True)
        await self.db.flush()

    async def count(self, *, extra_where: list[Any] | None = None) -> int:
        stmt = self._base_query()
        if extra_where:
            for w in extra_where:
                stmt = stmt.where(w)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        return (await self.db.execute(count_stmt)).scalar_one()
