from __future__ import annotations
from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from common.repository.team_scoped import TeamScopedRepoMixin
from customer.model import CustomerModel


class CustomerRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: Optional[int]):
        super().__init__(team_id)
        self.db = db

    async def get_by_id(self, customer_id: int) -> Optional[CustomerModel]:
        stmt = select(CustomerModel).where(
            CustomerModel.team_id == self._require_team(),
            CustomerModel.id == customer_id,
            CustomerModel.is_active.is_(True),
        )
        return await self.db.scalar(stmt)

    async def get_by_name(self, name: str) -> Optional[CustomerModel]:
        stmt = select(CustomerModel).where(
            CustomerModel.team_id == self._require_team(),
            CustomerModel.name == name,
            CustomerModel.is_active.is_(True),
        )
        return await self.db.scalar(stmt)

    async def list_by_team(self) -> Sequence[CustomerModel]:
        """해당 팀의 모든 활성 고객. autocomplete 가 클라 측에서 필터링하므로
        페이징 없이 전체 반환. 팀당 bounded 규모라 문제없음."""
        stmt = (
            select(CustomerModel)
            .where(
                CustomerModel.team_id == self._require_team(),
                CustomerModel.is_active.is_(True),
            )
            .order_by(CustomerModel.name.asc(), CustomerModel.id.asc())
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def create(self, customer: CustomerModel) -> CustomerModel:
        customer.team_id = self._require_team()
        self.db.add(customer)
        await self.db.flush()
        await self.db.refresh(customer)
        return customer
