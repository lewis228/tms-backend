# src/common/repository/tenant_scoped.py

from __future__ import annotations
from typing import Optional
from sqlalchemy import Select
from sqlalchemy.orm import InstrumentedAttribute

def scope_by_team(q: Select, col: InstrumentedAttribute, tenant_id: int) -> Select:
    """모델의 tenant_id 컬럼으로 where 절을 강제."""
    return q.where(col == tenant_id)


class TeamScopedRepoMixin:
    """레포지토리에서 tenant_id 스코프를 강제하는 공통 믹스인."""
    def __init__(self, tenant_id: Optional[int]):
        self.tenant_id = tenant_id

    def _require_team(self) -> int:
        if self.tenant_id is None:
            # 팀 스코프가 꼭 필요한 리포에서 None이면 명확히 실패시켜 버린다.
            raise ValueError("tenant_id is required for this repository operation")
        return self.tenant_id

    @staticmethod
    def _scope(q: Select, col: InstrumentedAttribute, tenant_id: int) -> Select:
        return scope_by_team(q, col, tenant_id)
