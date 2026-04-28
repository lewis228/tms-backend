# src/charge_code/model.py
from __future__ import annotations
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Boolean, Numeric, Text,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from charge_code.const.status import ChargeKind, ChargeUnit


class ChargeCodeModel(Base, TeamScopedMixin):
    """청구 코드 마스터 (Team-Scoped). leg_charge / rate_card 가 참조."""
    __tablename__ = "charge_code"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[ChargeKind] = mapped_column(
        SAEnum(ChargeKind, name="charge_kind"), nullable=False,
    )
    default_unit: Mapped[ChargeUnit] = mapped_column(
        SAEnum(ChargeUnit, name="charge_unit"), nullable=False,
        default=ChargeUnit.FLAT, server_default=ChargeUnit.FLAT.value,
    )
    default_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True,
    )
    is_billable_to_customer: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False,
    )
    is_payable_to_driver: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False,
    )
    gl_account: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_charge_code_team_id_id"),
        UniqueConstraint("team_id", "code", name="uq_charge_code_team_code"),
        Index("ix_charge_code_team_kind", "team_id", "kind"),
        Index("ix_charge_code_team_active_id", "team_id", "is_active", "id"),
    )
