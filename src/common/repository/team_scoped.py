# src/common/repository/team_scoped.py

from __future__ import annotations
from typing import Optional
from sqlalchemy import Select
from sqlalchemy.orm import InstrumentedAttribute

def scope_by_team(q: Select, col: InstrumentedAttribute, team_id: int) -> Select:
    """모델의 team_id 컬럼으로 where 절을 강제."""
    return q.where(col == team_id)


class TeamScopedRepoMixin:
    """레포지토리에서 team_id 스코프를 강제하는 공통 믹스인."""
    def __init__(self, team_id: Optional[int]):
        self.team_id = team_id

    def _require_team(self) -> int:
        if self.team_id is None:
            # 팀 스코프가 꼭 필요한 리포에서 None이면 명확히 실패시켜 버린다.
            raise ValueError("team_id is required for this repository operation")
        return self.team_id

    @staticmethod
    def _scope(q: Select, col: InstrumentedAttribute, team_id: int) -> Select:
        return scope_by_team(q, col, team_id)
