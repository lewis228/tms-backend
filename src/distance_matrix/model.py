# src/distance_matrix/model.py
"""v3: location pair 거리/소요시간 캐시.

A→B / B→A 방향이 다를 수 있어 양방향 모두 row 별도. source 로 측정 출처 추적.
RateTariff 산출 시 lookup. 미등록이면 lazy 측정 또는 ⚠️.
"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Numeric, DateTime, Text, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from leg.const.status import DistanceProvider


class DistanceMatrixModel(Base, TeamScopedMixin):
    """location pair 거리·시간 캐시 (v3)."""
    __tablename__ = "distance_matrix"

    origin_location_id: Mapped[int] = mapped_column(
        ForeignKey("location.id", ondelete="CASCADE"), nullable=False,
    )
    destination_location_id: Mapped[int] = mapped_column(
        ForeignKey("location.id", ondelete="CASCADE"), nullable=False,
    )
    distance_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)  # 단위 무관
    duration_min:   Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, server_default="0", nullable=False)
    source: Mapped[DistanceProvider] = mapped_column(
        SAEnum(DistanceProvider, name="distance_provider"),
        default=DistanceProvider.MANUAL, server_default=DistanceProvider.MANUAL.value, nullable=False,
    )
    measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_distance_matrix_team_id_id"),
        UniqueConstraint(
            "team_id", "origin_location_id", "destination_location_id",
            name="uq_distance_matrix_pair",
        ),
        Index("ix_distance_matrix_team_origin",     "team_id", "origin_location_id"),
        Index("ix_distance_matrix_team_dest",       "team_id", "destination_location_id"),
        Index("ix_distance_matrix_team_active_id",  "team_id", "is_active", "id"),
    )
