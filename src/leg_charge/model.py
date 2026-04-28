# src/leg_charge/model.py
from __future__ import annotations
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Boolean, Numeric, Text, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from charge_code.const.status import ChargeUnit, ChargeSource, PartyKind


class LegChargeModel(Base, TeamScopedMixin):
    """leg 단위 청구 line item.

    Manifest 표의 한 줄 = leg 1건 + leg_charge N개 (BASE + accessorials).
    H-7 에서 rate_card 매칭 → AUTO source 로 자동 생성.
    H-2 단계에선 MANUAL 생성/조회 + Container Drawer 정산 탭 표시까지.
    """
    __tablename__ = "leg_charge"

    leg_id: Mapped[int] = mapped_column(
        ForeignKey("leg.id", ondelete="CASCADE"), nullable=False,
    )
    charge_code_id: Mapped[int] = mapped_column(
        ForeignKey("charge_code.id", ondelete="RESTRICT"), nullable=False,
    )
    rate_card_id: Mapped[int | None] = mapped_column(
        ForeignKey("rate_card.id", ondelete="SET NULL"), nullable=True,
    )

    # ── 금액 ─────
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    unit: Mapped[ChargeUnit | None] = mapped_column(
        SAEnum(ChargeUnit, name="charge_unit"), nullable=True,
    )

    # ── 메타 ─────
    source: Mapped[ChargeSource] = mapped_column(
        SAEnum(ChargeSource, name="charge_source"),
        default=ChargeSource.MANUAL, server_default=ChargeSource.MANUAL.value, nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 정산 흐름 (H-7 에서 settlement 묶임) ─────
    settlement_id: Mapped[int | None] = mapped_column(
        ForeignKey("settlement.id", ondelete="SET NULL"), nullable=True,
    )
    is_settled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False,
    )

    # ── Payee/Payer (H-7) — 주체별 P&L 분리 ──
    payee_kind: Mapped[PartyKind | None] = mapped_column(
        SAEnum(PartyKind, name="party_kind"), nullable=True,
    )
    payee_partner_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), nullable=True,
    )
    payee_driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("driver.id", ondelete="SET NULL"), nullable=True,
    )
    payee_pool_id: Mapped[int | None] = mapped_column(
        ForeignKey("equipment_pool.id", ondelete="SET NULL"), nullable=True,
    )
    payer_kind: Mapped[PartyKind | None] = mapped_column(
        SAEnum(PartyKind, name="party_kind"), nullable=True,
    )
    payer_partner_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_leg_charge_team_id_id"),
        Index("ix_leg_charge_team_leg",          "team_id", "leg_id"),
        Index("ix_leg_charge_team_charge_code",  "team_id", "charge_code_id"),
        Index("ix_leg_charge_team_settlement",   "team_id", "settlement_id"),
        Index("ix_leg_charge_team_source",       "team_id", "source"),
        Index("ix_leg_charge_team_active_id",    "team_id", "is_active", "id"),
    )
