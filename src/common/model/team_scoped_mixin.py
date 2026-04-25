# common/model/team_scoped_mixin.py
from __future__ import annotations
from typing import List
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr
from sqlalchemy import Integer, ForeignKey


def get_team_scoped_table_names() -> List[str]:
    """Base.metadata에서 team_id FK → teams.id 를 가진 테이블명 자동 수집.

    런타임에 호출해야 모든 모델이 등록된 상태에서 정확한 결과를 반환한다.
    """
    from common.model.base_model import Base

    names: List[str] = []
    for table in Base.metadata.tables.values():
        if table.name == "teams":
            continue
        for col in table.columns:
            if col.name != "team_id":
                continue
            for fk in col.foreign_keys:
                if fk.target_fullname == "teams.id":
                    names.append(table.name)
                    break
    return names


class TeamScopedMixin:
    """
    - 항상 team_id 컬럼을 제공 (CASCADE/무결성/성능)
    - __with_team_rel__ = False 인 클래스에는 .team 관계를 만들지 않음
    """
    __with_team_rel__: bool = True  # 기본 ON

    @declared_attr
    def team_id(cls) -> Mapped[int]:
        return mapped_column(
            Integer, ForeignKey("teams.id", ondelete="CASCADE"),
            index=True, nullable=False
        )

    @declared_attr
    def team(cls):
        if getattr(cls, "__with_team_rel__", True):
            return relationship("TeamModel", lazy="selectin")
        # 관계를 만들지 않음 (라인 모델에서 충돌 방지)
        return None
