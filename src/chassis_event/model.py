# src/chassis_event/model.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Text, ForeignKey, DateTime,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from leg.const.status import ChassisEventKind


class ChassisEventModel(Base, TeamScopedMixin):
    """챠시 라이프사이클 이벤트 로그.

    H-7 의 자동 정산 엔진이 PICKED_UP / RETURNED_TO_POOL 시각차로 CHASSIS_PER_DIEM 산출.
    """
    __tablename__ = "chassis_event"

    chassis_id: Mapped[int] = mapped_column(
        ForeignKey("chassis.id", ondelete="CASCADE"), nullable=False,
    )
    leg_id: Mapped[int | None] = mapped_column(
        ForeignKey("leg.id", ondelete="SET NULL"), nullable=True,
    )
    leg_stop_id: Mapped[int | None] = mapped_column(
        ForeignKey("leg_stop.id", ondelete="SET NULL"), nullable=True,
    )
    event_kind: Mapped[ChassisEventKind] = mapped_column(
        SAEnum(ChassisEventKind, name="chassis_event_kind"), nullable=False,
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_chassis_event_team_id_id"),
        Index("ix_chassis_event_team_chassis", "team_id", "chassis_id", "occurred_at"),
        Index("ix_chassis_event_team_kind",    "team_id", "event_kind"),
        Index("ix_chassis_event_team_active_id", "team_id", "is_active", "id"),
    )
