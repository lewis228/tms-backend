from __future__ import annotations
from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from common.repository.team_scoped import TeamScopedRepoMixin
from tag.model import TagModel


class TagRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: Optional[int]):
        super().__init__(team_id)
        self.db = db

    async def get_by_id(self, tag_id: int) -> Optional[TagModel]:
        stmt = select(TagModel).where(
            TagModel.team_id == self._require_team(),
            TagModel.id == tag_id,
            TagModel.is_active.is_(True),
        )
        return await self.db.scalar(stmt)

    async def get_by_name(self, name: str) -> Optional[TagModel]:
        stmt = select(TagModel).where(
            TagModel.team_id == self._require_team(),
            TagModel.name == name,
            TagModel.is_active.is_(True),
        )
        return await self.db.scalar(stmt)

    async def list_by_team(self) -> Sequence[TagModel]:
        """해당 팀의 모든 활성 태그. 색상이 안정되도록 생성 순으로 반환.
        팀당 사용량이 bounded 라 페이징 불필요."""
        stmt = (
            select(TagModel)
            .where(
                TagModel.team_id == self._require_team(),
                TagModel.is_active.is_(True),
            )
            .order_by(TagModel.created_at.asc(), TagModel.id.asc())
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def list_by_ids(self, tag_ids: Sequence[int]) -> Sequence[TagModel]:
        """주어진 id 집합 중 현 팀 소유의 태그만 반환. shipment 에 태그 부착 시
        서비스에서 갯수 비교로 크로스 팀 누락을 감지한다."""
        if len(tag_ids) == 0:
            return []
        stmt = select(TagModel).where(
            TagModel.team_id == self._require_team(),
            TagModel.id.in_(list(tag_ids)),
            TagModel.is_active.is_(True),
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def create(self, tag: TagModel) -> TagModel:
        tag.team_id = self._require_team()
        self.db.add(tag)
        await self.db.flush()
        await self.db.refresh(tag)
        return tag
