# src/rate_quote/model.py
"""v3: 정찰가 마스터 (RateCard / fixed amount).

사전 협상된 *정확한 location pair* 의 고정 금액. RateTariff(거리×단가)보다
우선 매칭 — 매칭되면 거리/단가 모두 무시하고 fixed_amount 그대로 사용.

기존 `rate_card` 테이블은 ChargeCode 기반 부가요금 매트릭스로 의미가 다르므로
혼동 방지를 위해 신설 테이블명은 `rate_quote` 로 분리.
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


class RateQuoteModel(Base, TeamScopedMixin):
    """정찰가 매트릭스 (v3)."""
    __tablename__ = "rate_quote"

    name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 매칭 키 (전부 nullable; null 이면 wildcard) ──
    origin_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="CASCADE"), nullable=True,
    )
    destination_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="CASCADE"), nullable=True,
    )
    container_size: Mapped[ContainerSize | None] = mapped_column(
        SAEnum(ContainerSize, name="container_size"), nullable=True,
    )
    move_type: Mapped[MoveTypeV3 | None] = mapped_column(
        SAEnum(MoveTypeV3, name="move_type_v3"), nullable=True,
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=True,
    )

    # ── 고정 금액 (단위 무관 Decimal) ──
    fixed_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # ── 유효 기간 / 우선순위 ──
    effective_from: Mapped[date]        = mapped_column(Date, nullable=False)
    effective_to:   Mapped[date | None] = mapped_column(Date, nullable=True)
    priority:       Mapped[int]         = mapped_column(Integer, default=0, server_default="0", nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_rate_quote_team_id_id"),
        Index("ix_rate_quote_team_origin",       "team_id", "origin_location_id"),
        Index("ix_rate_quote_team_destination",  "team_id", "destination_location_id"),
        Index("ix_rate_quote_team_customer",     "team_id", "customer_id"),
        Index("ix_rate_quote_team_priority",     "team_id", "priority"),
        Index("ix_rate_quote_team_effective",    "team_id", "effective_from"),
        Index("ix_rate_quote_team_active_id",    "team_id", "is_active", "id"),
    )
