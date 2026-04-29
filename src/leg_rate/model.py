# src/leg_rate/model.py
"""v3: Leg 의 기본 운임 — 배차 시점에 SNAPSHOT 박힘.

마스터(rate_quote.fixed_amount, rate_tariff.per_value 등) 가 갱신되어도 이 값은
절대 안 흔들림. 명시적 재계산 버튼만이 새 마스터로 갱신.

base_amount =
  source = QUOTE_FIXED  → snapshot_quote_fixed
  source = TARIFF_CALC  → snapshot_flat_base
                          + snapshot_per_value × snapshot_distance_value
                          + snapshot_per_min   × snapshot_duration_min
  source = TARIFF_FLAT  → snapshot_flat_base 만 (거리 미등록)
  source = MANUAL       → 디스패처 수동 입력
  source = NONE         → 0 + ⚠️
"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Numeric, Boolean, DateTime, Text, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from leg.const.status import LegRateSource


class LegRateModel(Base, TeamScopedMixin):
    """Leg 기본 운임 snapshot (v3, leg 1:1)."""
    __tablename__ = "leg_rate"

    leg_id: Mapped[int] = mapped_column(
        ForeignKey("leg.id", ondelete="CASCADE"), nullable=False,
    )

    # ── 추적 (마스터 갱신에 영향 안 받음) ─────
    rate_quote_id:  Mapped[int | None] = mapped_column(
        ForeignKey("rate_quote.id",  ondelete="SET NULL"), nullable=True,
    )
    rate_tariff_id: Mapped[int | None] = mapped_column(
        ForeignKey("rate_tariff.id", ondelete="SET NULL"), nullable=True,
    )

    # ── Snapshot (배차 시점 박힘) ─────
    snapshot_distance_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    snapshot_duration_min:   Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    snapshot_per_value:      Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    snapshot_per_min:        Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    snapshot_flat_base:      Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    snapshot_quote_fixed:    Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    # ── 최종값 (정산은 이걸로) ─────
    base_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)

    source: Mapped[LegRateSource] = mapped_column(
        SAEnum(LegRateSource, name="leg_rate_source"),
        default=LegRateSource.NONE, server_default=LegRateSource.NONE.value, nullable=False,
    )
    manual_override: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False,
    )

    # 정산 귀속 driver (보통 leg 의 마지막 완주 segment driver)
    payee_driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("driver.id", ondelete="SET NULL"), nullable=True,
    )

    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_leg_rate_team_id_id"),
        UniqueConstraint("leg_id", name="uq_leg_rate_leg"),
        Index("ix_leg_rate_team_leg",       "team_id", "leg_id"),
        Index("ix_leg_rate_team_quote",     "team_id", "rate_quote_id"),
        Index("ix_leg_rate_team_tariff",    "team_id", "rate_tariff_id"),
        Index("ix_leg_rate_team_payee",     "team_id", "payee_driver_id"),
        Index("ix_leg_rate_team_active_id", "team_id", "is_active", "id"),
    )
