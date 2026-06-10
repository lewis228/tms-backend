# src/container_stop/model.py
"""Container 의 Point(정차 지점) 시퀀스.

- Container 1개 = Point N 개 (sequence_no 순). Leg 가 from_point→to_point 로 이 포인트들을 잇는다.
- 각 Point 는 **타입(point_type)** + 그 타입 마스터 참조(정확히 하나):
    TERMINAL → terminal_id, YARD → location_id(kind=YARD), CUSTOMER → customer_id.
- 테이블명은 호환 위해 container_stop 유지(드라이버앱 arrive/depart 등). 개념은 'Point'.
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
from leg.const.status import PointType


class ContainerStopModel(Base, TeamScopedMixin):
    """Container 의 Point 시퀀스 (타입별 마스터 참조)."""
    __tablename__ = "container_stop"

    container_id: Mapped[int] = mapped_column(
        ForeignKey("container.id", ondelete="CASCADE"), nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    point_type: Mapped[PointType] = mapped_column(
        SAEnum(PointType, name="point_type"), nullable=False,
    )
    # ── 타입별 마스터 참조 (정확히 하나 non-null — 서비스에서 검증) ──
    terminal_id: Mapped[int | None] = mapped_column(
        ForeignKey("terminal.id", ondelete="SET NULL"), nullable=True,
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), nullable=True,
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
        Index("ix_container_stop_team_type",       "team_id", "point_type"),
        Index("ix_container_stop_team_location",   "team_id", "location_id"),
        Index("ix_container_stop_team_active_id",  "team_id", "is_active", "id"),
    )
