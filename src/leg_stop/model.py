# src/leg_stop/model.py
#
# ⚠️ DEPRECATED (Phase v3): leg_stop 은 leg 내부 정차 액션 표현용으로 만들었으나
# v3 부터는 *Container 시퀀스* 를 별도 도메인 `container_stop` 에 분리.
# 신규 leg 생성 시에는 더 이상 leg_stop row 를 만들지 않는다.
# 기존 데이터(H-7 까지의 시드)는 보존하되 새 코드에서 의존 금지.
#
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Integer, Text, ForeignKey, DateTime,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from leg.const.status import StopKind


class LegStopModel(Base, TeamScopedMixin):
    """leg 의 정차점 시퀀스. 한 leg = N stop. 다중 stop 표현 (multi-stop, 챠시 flip).

    각 stop 은 stop_kind 로 동작 분류 (PICKUP_FULL/DROP_FULL/CHASSIS_GET 등).
    container_id, chassis_id 는 이 stop 에서 다루는 자산 (flip 시 stop 별로 다름).
    """
    __tablename__ = "leg_stop"

    leg_id: Mapped[int] = mapped_column(
        ForeignKey("leg.id", ondelete="CASCADE"), nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_kind: Mapped[StopKind] = mapped_column(
        SAEnum(StopKind, name="stop_kind"), nullable=False,
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )

    # 이 stop 에서 다루는 자산 (있으면)
    container_id: Mapped[int | None] = mapped_column(
        ForeignKey("container.id", ondelete="SET NULL"), nullable=True,
    )
    chassis_id: Mapped[int | None] = mapped_column(
        ForeignKey("chassis.id", ondelete="SET NULL"), nullable=True,
    )

    # 진행 시각 (대기 분 → WAIT_PER_MIN 자동 산출용 — H-7 에서 활용)
    arrived_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_leg_stop_team_id_id"),
        UniqueConstraint("leg_id", "sequence_no", name="uq_leg_stop_leg_seq"),
        Index("ix_leg_stop_team_leg",       "team_id", "leg_id"),
        Index("ix_leg_stop_team_kind",      "team_id", "stop_kind"),
        Index("ix_leg_stop_team_active_id", "team_id", "is_active", "id"),
    )
