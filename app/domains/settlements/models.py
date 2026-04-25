"""Settlement / ExtraCharge / SettlementAuditLog.

Settlement 는 Leg 와 1:1 (leg_id unique).
APPROVED 후 잠금. Unapprove 는 ADMIN+, AuditLog 자동 기록.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantAuditMixin
from app.models.enums import SettlementStatus


class Settlement(TenantAuditMixin, Base):
    __tablename__ = "settlements"
    __table_args__ = (
        UniqueConstraint("leg_id", name="uq_settlements_leg"),
        Index("ix_settlements_tenant_status", "tenant_id", "settlement_status"),
        Index("ix_settlements_tenant_settled", "tenant_id", "is_settled"),
    )

    leg_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("legs.id", ondelete="CASCADE", use_alter=True, name="fk_settlements_leg"),
        nullable=False,
    )

    system_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    driver_reported_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    discrepancy: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    has_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    final_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    settlement_status: Mapped[SettlementStatus] = mapped_column(
        SAEnum(SettlementStatus, name="settlement_status"),
        nullable=False,
        default=SettlementStatus.PENDING,
    )
    is_settled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    unapproved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unapproved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    unapproved_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExtraCharge(TenantAuditMixin, Base):
    __tablename__ = "extra_charges"
    __table_args__ = (Index("ix_extra_tenant_settlement", "tenant_id", "settlement_id"),)

    settlement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class SettlementAuditLog(TenantAuditMixin, Base):
    __tablename__ = "settlement_audit_logs"
    __table_args__ = (Index("ix_sal_tenant_settlement", "tenant_id", "settlement_id"),)

    settlement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
