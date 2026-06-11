# src/rate_group/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Text, Boolean,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from rate_group.const.status import RateMethod


class RateGroupModel(Base, TeamScopedMixin):
    """정산/요율 그룹 — 요율 산정 방식(method)별 묶음 마스터 (Team-Scoped).

    method 별로 하나의 그룹을 기본값(is_default)으로 지정할 수 있고,
    템플릿(is_template)으로 표시해 신규 그룹 생성 시 참조용으로 쓸 수 있다.
    커스텀 그룹은 inherits_default=True(기본)면 미등록 구간을 같은 방식의
    디폴트 그룹으로 폴백(해석 사다리 ④)하고, False(빈 그룹)면 폴백 없이 미해석.
    """
    __tablename__ = "rate_group"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    method: Mapped[RateMethod] = mapped_column(
        SAEnum(RateMethod, name="rate_method"),
        nullable=False,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False,
    )
    inherits_default: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False,
    )
    is_template: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_rate_group_team_id_id"),
        Index("ix_rate_group_team_active_id", "team_id", "is_active", "id"),
        Index("ix_rate_group_team_method",     "team_id", "method"),
        Index("ix_rate_group_team_updated_at",  "team_id", "updated_at"),
    )
