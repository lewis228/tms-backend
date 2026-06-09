# src/driver_rate_assignment/model.py
from __future__ import annotations
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Date, Text, ForeignKey,
    Index, UniqueConstraint,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin


class DriverRateAssignmentModel(Base, TeamScopedMixin):
    """드라이버 ↔ 요율그룹 배정 (유효일자 기반, Team-Scoped).

    한 드라이버에 대해 유효기간(effective_from ~ effective_to)별로 적용할
    요율그룹(rate_group)을 매핑한다. effective_to=None 이면 무제한(현재 유효).
    work_date 기준 가장 최근 effective_from 배정이 적용된다.
    """
    __tablename__ = "driver_rate_assignment"

    driver_id: Mapped[int] = mapped_column(
        ForeignKey("driver.id", ondelete="CASCADE"), nullable=False,
    )
    rate_group_id: Mapped[int] = mapped_column(
        ForeignKey("rate_group.id", ondelete="RESTRICT"), nullable=False,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)  # None=무제한
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_driver_rate_assign_team_id_id"),
        Index("ix_driver_rate_assign_lookup", "team_id", "driver_id", "effective_from"),
        Index("ix_driver_rate_assign_team_active_id", "team_id", "is_active", "id"),
        Index("ix_driver_rate_assign_team_group", "team_id", "rate_group_id"),
        Index("ix_driver_rate_assign_team_updated_at", "team_id", "updated_at"),
    )
