# src/rate_card/model.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, Numeric, Date, Text, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from charge_code.const.status import ChargeUnit
from container.const.status import ContainerSize


class RateCardModel(Base, TeamScopedMixin):
    """요율 카드 매트릭스 (Team-Scoped).

    매칭 우선순위: 더 specific 한 scope (priority 큰 값) 가 우선.
    nullable scope 는 wildcard 처럼 동작 — 전부 null 이면 글로벌 default.
    H-7 의 자동 정산 엔진이 leg.completed 시 매칭하여 leg_charge 자동 생성.
    """
    __tablename__ = "rate_card"

    charge_code_id: Mapped[int] = mapped_column(
        ForeignKey("charge_code.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── 스코프 (전부 nullable; null 은 wildcard) ─────────
    scope_customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=True,
    )
    scope_terminal_id: Mapped[int | None] = mapped_column(
        ForeignKey("terminal.id", ondelete="CASCADE"), nullable=True,
    )
    scope_size: Mapped[ContainerSize | None] = mapped_column(
        SAEnum(ContainerSize, name="container_size"), nullable=True,
    )
    scope_zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scope_from_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )
    scope_to_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )

    # ── 금액 (unit 따라 한 컬럼만 채움) ─────────
    unit: Mapped[ChargeUnit] = mapped_column(
        SAEnum(ChargeUnit, name="charge_unit"),
        default=ChargeUnit.FLAT, server_default=ChargeUnit.FLAT.value, nullable=False,
    )
    amount:        Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    percent:       Mapped[Decimal | None] = mapped_column(Numeric(7, 4),  nullable=True)
    per_unit:      Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)

    # ── 유효 기간 ─────────
    effective_from: Mapped[date]         = mapped_column(Date, nullable=False)
    effective_to:   Mapped[date | None]  = mapped_column(Date, nullable=True)

    priority:    Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_rate_card_team_id_id"),
        Index("ix_rate_card_team_charge_code", "team_id", "charge_code_id"),
        Index("ix_rate_card_team_customer",    "team_id", "scope_customer_id"),
        Index("ix_rate_card_team_terminal",    "team_id", "scope_terminal_id"),
        Index("ix_rate_card_team_priority",    "team_id", "priority"),
        Index("ix_rate_card_team_effective",   "team_id", "effective_from"),
        Index("ix_rate_card_team_active_id",   "team_id", "is_active", "id"),
    )
