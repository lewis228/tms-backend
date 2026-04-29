# src/rate_tariff/model.py
"""v3: 거리×단가룰 마스터 (배민형 정산).

base_amount = flat_base + per_value × distance_value + per_min × duration_min

RateQuote 매칭 실패 시 fallback 으로 사용. 단가만 갱신하면 모든 location pair 에 자동 반영.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Integer, Numeric, Date, Text, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from container.const.status import ContainerSize
from leg.const.status import MoveTypeV3


class RateTariffModel(Base, TeamScopedMixin):
    """거리×단가룰 (v3)."""
    __tablename__ = "rate_tariff"

    name: Mapped[str] = mapped_column(Text, nullable=False)

    # ── 매칭 키 (전부 nullable; null 이면 wildcard) ──
    move_type: Mapped[MoveTypeV3 | None] = mapped_column(
        SAEnum(MoveTypeV3, name="move_type_v3"), nullable=True,
    )
    container_size: Mapped[ContainerSize | None] = mapped_column(
        SAEnum(ContainerSize, name="container_size"), nullable=True,
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=True,
    )

    # ── 단가 (단위 무관 Decimal) ──
    per_value:  Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, server_default="0", nullable=False)  # 거리당
    per_min:    Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, server_default="0", nullable=False)  # 분당
    flat_base:  Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)  # 콜비/최소

    # ── 유효 기간 / 우선순위 ──
    effective_from: Mapped[date]        = mapped_column(Date, nullable=False)
    effective_to:   Mapped[date | None] = mapped_column(Date, nullable=True)
    priority:       Mapped[int]         = mapped_column(Integer, default=0, server_default="0", nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_rate_tariff_team_id_id"),
        Index("ix_rate_tariff_team_move",      "team_id", "move_type"),
        Index("ix_rate_tariff_team_size",      "team_id", "container_size"),
        Index("ix_rate_tariff_team_customer",  "team_id", "customer_id"),
        Index("ix_rate_tariff_team_priority",  "team_id", "priority"),
        Index("ix_rate_tariff_team_effective", "team_id", "effective_from"),
        Index("ix_rate_tariff_team_active_id", "team_id", "is_active", "id"),
    )
