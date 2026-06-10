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
from charge_code.const.status import ChargeKind, ChargeUnit, ChargeCategory, PartyKind


class ChargeCodeModel(Base, TeamScopedMixin):
    """청구 코드 마스터 (Team-Scoped). 청구/정산 라인이 참조."""
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

    # ── 변동 청구 라인 마스터 정밀화 ─────────────
    # UI 라벨 (예: "10분", "건", "정차", "%")
    unit_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 변동 라인 분류 (UI 그룹핑/필터)
    category: Mapped[ChargeCategory | None] = mapped_column(
        SAEnum(ChargeCategory, name="charge_category"), nullable=True,
    )
    # 음수 입력 허용 (페널티/할인 등)
    signed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False,
    )
    # 청구 라인 생성 시 payee 기본값
    payee_default: Mapped[PartyKind | None] = mapped_column(
        SAEnum(PartyKind, name="party_kind"), nullable=True,
    )
    payer_default: Mapped[PartyKind | None] = mapped_column(
        SAEnum(PartyKind, name="party_kind"), nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_charge_code_team_id_id"),
        UniqueConstraint("team_id", "code", name="uq_charge_code_team_code"),
        Index("ix_charge_code_team_kind", "team_id", "kind"),
        Index("ix_charge_code_team_active_id", "team_id", "is_active", "id"),
    )
