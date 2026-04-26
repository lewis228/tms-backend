# src/settlement/model.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, Boolean, Text, ForeignKey, DateTime, Numeric, JSON,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.tenant_scoped_mixin import TenantScopedMixin
from settlement.const.status import SettlementStatus, SettlementAuditAction


class SettlementModel(Base, TenantScopedMixin):
    """Leg 의 정산 (1:1)."""
    __tablename__ = "settlement"

    leg_id: Mapped[int] = mapped_column(
        ForeignKey("leg.id", ondelete="CASCADE"), nullable=False,
    )

    settlement_status: Mapped[SettlementStatus] = mapped_column(
        SAEnum(SettlementStatus, name="settlement_status"),
        default=SettlementStatus.PENDING,
        server_default=SettlementStatus.PENDING.value,
        nullable=False,
    )

    # ── 금액 ────────────────────────────────────────────────────
    system_total:           Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    driver_reported_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    discrepancy:            Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    has_flag:               Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    final_amount:           Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    is_settled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)

    # ── 승인 메타 ───────────────────────────────────────────────
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True,
    )
    unapproved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unapproved_by: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True,
    )
    unapproved_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_settlement_tenant_id_id"),
        UniqueConstraint("leg_id", name="uq_settlement_leg_unique"),
        Index("ix_settlement_tenant_status",      "tenant_id", "settlement_status"),
        Index("ix_settlement_tenant_has_flag",    "tenant_id", "has_flag"),
        Index("ix_settlement_tenant_active_id",   "tenant_id", "is_active", "id"),
        Index("ix_settlement_tenant_updated_at",  "tenant_id", "updated_at"),
    )


class ExtraChargeModel(Base, TenantScopedMixin):
    """Settlement 의 추가 청구 (DEMURRAGE, DETENTION, FUEL 등 자유 코드)."""
    __tablename__ = "extra_charge"

    settlement_id: Mapped[int] = mapped_column(
        ForeignKey("settlement.id", ondelete="CASCADE"), nullable=False,
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_extra_charge_tenant_id_id"),
        Index("ix_extra_charge_tenant_settlement", "tenant_id", "settlement_id"),
        Index("ix_extra_charge_tenant_type",       "tenant_id", "type"),
        Index("ix_extra_charge_tenant_active_id",  "tenant_id", "is_active", "id"),
    )


class SettlementAuditLogModel(Base, TenantScopedMixin):
    """Settlement 변경 감사 로그 — append-only."""
    __tablename__ = "settlement_audit_log"

    settlement_id: Mapped[int] = mapped_column(
        ForeignKey("settlement.id", ondelete="CASCADE"), nullable=False,
    )
    action: Mapped[SettlementAuditAction] = mapped_column(
        SAEnum(SettlementAuditAction, name="settlement_audit_action"), nullable=False,
    )
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True,
    )
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state:  Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_settlement_audit_tenant_id_id"),
        Index("ix_settlement_audit_tenant_settlement", "tenant_id", "settlement_id"),
        Index("ix_settlement_audit_tenant_action",     "tenant_id", "action"),
        Index("ix_settlement_audit_tenant_active_id",  "tenant_id", "is_active", "id"),
        Index("ix_settlement_audit_tenant_created_at", "tenant_id", "created_at"),
    )
