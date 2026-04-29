# src/container_stop/model.py
"""v3: Container 의 정차점(Stop) 시퀀스.

기존 `leg_stop` 은 leg 내부의 정차 액션(픽업/드롭/대기 등) 표현용이라
*Container 시퀀스*를 표현하기에 부적합하다. v3 부터 별도 도메인으로 분리.

- Container 1개 = ContainerStop N 개 (sequence_no 순).
- 각 stop 은 Location 마스터 참조 + role(ORIGIN/DELIVERY/TRANSIT/TERMINUS).
- Leg 는 from_stop_id / to_stop_id 로 인접 두 stop 사이 이동을 표현.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Integer, Text, ForeignKey, DateTime,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from leg.const.status import StopRole


class ContainerStopModel(Base, TeamScopedMixin):
    """Container 의 정차점 시퀀스 (v3)."""
    __tablename__ = "container_stop"

    container_id: Mapped[int] = mapped_column(
        ForeignKey("container.id", ondelete="CASCADE"), nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[StopRole] = mapped_column(
        SAEnum(StopRole, name="stop_role"), nullable=False,
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )

    # ── 일정 ─────────────────────────────────────────────
    planned_arrival:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_departure:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_arrival:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_departure:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_container_stop_team_id_id"),
        UniqueConstraint("container_id", "sequence_no", name="uq_container_stop_container_seq"),
        Index("ix_container_stop_team_container",  "team_id", "container_id", "sequence_no"),
        Index("ix_container_stop_team_role",       "team_id", "role"),
        Index("ix_container_stop_team_location",   "team_id", "location_id"),
        Index("ix_container_stop_team_active_id",  "team_id", "is_active", "id"),
    )
