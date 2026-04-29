# src/leg_driver_segment/model.py
"""v3: 한 leg 안의 기사 segment.

한 leg = 보통 1명의 기사가 끝까지 완주, 그러나 다음 케이스에선 여러 기사 등장:
  - 터미널 closed 로 다음 날 다른 기사가 다시 감
  - 사고로 컨테이너를 다른 트럭/기사에 인계
  - 교대 시간

LegDriverSegment 가 이 시퀀스를 표현. 정산 라인은 segment.driver_id 로 귀속 가능.
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
from leg.const.status import HandoverReason


class LegDriverSegmentModel(Base, TeamScopedMixin):
    """한 leg 안 기사 segment 시퀀스 (v3)."""
    __tablename__ = "leg_driver_segment"

    leg_id: Mapped[int] = mapped_column(
        ForeignKey("leg.id", ondelete="CASCADE"), nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)

    driver_id: Mapped[int] = mapped_column(
        ForeignKey("driver.id", ondelete="RESTRICT"), nullable=False,
    )
    truck_id: Mapped[int | None] = mapped_column(
        ForeignKey("truck.id", ondelete="SET NULL"), nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    handover_reason: Mapped[HandoverReason | None] = mapped_column(
        SAEnum(HandoverReason, name="handover_reason"), nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_leg_driver_segment_team_id_id"),
        UniqueConstraint("leg_id", "sequence_no", name="uq_leg_driver_segment_leg_seq"),
        Index("ix_leg_driver_segment_team_leg",       "team_id", "leg_id", "sequence_no"),
        Index("ix_leg_driver_segment_team_driver",    "team_id", "driver_id"),
        Index("ix_leg_driver_segment_team_active_id", "team_id", "is_active", "id"),
    )
