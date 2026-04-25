# src/common/repository/team_scoped.py
"""
팀 테넌시 강제를 위한 Repository 공통 믹스인.

모든 팀-scoped 도메인 레포지토리는 이 믹스인을 상속해 team_id를
생성자에서 받아야 한다. 쿼리 WHERE 절의 최상단 조건으로 team_id
매칭을 강제해 크로스 테넌시 누출을 애플리케이션 레벨에서 차단한다.

사용 예시:

    class ShipmentRepository(TeamScopedRepoMixin):
        def __init__(self, db: AsyncSession, team_id: Optional[int]):
            super().__init__(team_id)
            self.db = db

        async def get(self, shipment_id: int) -> Optional[ShipmentModel]:
            q = select(ShipmentModel).where(
                ShipmentModel.team_id == self._require_team(),  # ← 항상 첫 조건
                ShipmentModel.id == shipment_id,
                ShipmentModel.is_active.is_(True),
            )
            return (await self.db.execute(q)).scalar_one_or_none()

특수 사례 (시스템 배치/Celery 태스크):
    team_id 없이 전 팀을 스캔해야 하는 경우 (예: `check_and_schedule_scrapes`)
    는 ``TeamScopedRepoMixin`` 을 상속하지 않은 별도의 시스템-레포를 사용하거나,
    `_require_team()` 을 호출하지 않는 별도 메서드로 처리한다.
"""

from __future__ import annotations
from typing import Optional
from sqlalchemy import Select
from sqlalchemy.orm import InstrumentedAttribute


def scope_by_team(q: Select, col: InstrumentedAttribute, team_id: int) -> Select:
    """쿼리에 ``col == team_id`` WHERE 절을 추가한다."""
    return q.where(col == team_id)


class TeamScopedRepoMixin:
    """Repository에서 team_id 스코프를 강제하는 공통 믹스인."""

    def __init__(self, team_id: Optional[int]):
        self.team_id = team_id

    def _require_team(self) -> int:
        """팀 scoped 연산에 team_id 가 필수임을 보장한다. ``None`` 이면 즉시 실패."""
        if self.team_id is None:
            raise ValueError("team_id is required for this repository operation")
        return self.team_id

    @staticmethod
    def _scope(q: Select, col: InstrumentedAttribute, team_id: int) -> Select:
        """인스턴스 없이도 사용 가능한 정적 스코프 헬퍼."""
        return scope_by_team(q, col, team_id)
