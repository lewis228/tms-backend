# src/invoice/model.py
"""고객 인보이스(고객청구) — 재설계 2c.

원가+마진(cost-plus) 모델:
  - cost_total = 그 D/O 기사 정산(leg base) 자동 집계 — 내부 원가(마진 계산용).
  - charge_total = 청구 라인 합 — 고객에 청구.
  - margin = charge_total - cost_total (스키마에서 계산, 미저장).

invoice(헤더: customer + optional D/O) + invoice_line(청구 라인, 프리필/수동).
드라이버 정산(payroll)과 독립. 고객 요율표(별도 AR 모델)는 추후.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from sqlalchemy import (
    String, Integer, Numeric, Date, ForeignKey,
    Index, UniqueConstraint, ForeignKeyConstraint, and_, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from common.const.settings import settings
from invoice.const.status import InvoiceStatus, InvoiceLineSource


class InvoiceModel(Base, TeamScopedMixin):
    """인보이스 헤더 — 고객 × (옵션) D/O."""
    __tablename__ = "invoice"

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False,
    )
    delivery_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_order.id", ondelete="SET NULL"), nullable=True,
    )
    invoice_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, name="invoice_status"),
        default=InvoiceStatus.DRAFT, server_default=InvoiceStatus.DRAFT.value, nullable=False,
    )
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date:   Mapped[date | None] = mapped_column(Date, nullable=True)

    # 금액 — cost_total(원가, 생성/재계산 시 동결), charge_total(라인 합).
    cost_total:   Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    charge_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    lines: Mapped[list["InvoiceLineModel"]] = relationship(
        "InvoiceLineModel", back_populates="invoice", cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT, order_by="InvoiceLineModel.id.asc()",
        primaryjoin=lambda: and_(
            foreign(InvoiceLineModel.team_id) == InvoiceModel.team_id,
            foreign(InvoiceLineModel.invoice_id) == InvoiceModel.id,
        ),
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_invoice_team_id_id"),
        Index("ix_invoice_team_active_id", "team_id", "is_active", "id"),
        Index("ix_invoice_team_customer", "team_id", "customer_id"),
        Index("ix_invoice_team_do", "team_id", "delivery_order_id"),
        Index("ix_invoice_team_status", "team_id", "status"),
        Index("ix_invoice_team_updated_at", "team_id", "updated_at"),
    )


class InvoiceLineModel(Base, TeamScopedMixin):
    """청구 라인 — 고객이 볼 청구 항목."""
    __tablename__ = "invoice_line"
    __with_team_rel__ = False

    invoice_id: Mapped[int] = mapped_column(Integer, nullable=False)
    container_id: Mapped[int | None] = mapped_column(
        ForeignKey("container.id", ondelete="SET NULL"), nullable=True,
    )
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity:    Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1, server_default="1", nullable=False)
    unit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    amount:      Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    source: Mapped[InvoiceLineSource] = mapped_column(
        SAEnum(InvoiceLineSource, name="invoice_line_source"),
        default=InvoiceLineSource.MANUAL, server_default=InvoiceLineSource.MANUAL.value, nullable=False,
    )
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)  # 프리필 시 원가(참고)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    invoice: Mapped["InvoiceModel"] = relationship(
        "InvoiceModel", back_populates="lines", lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: and_(
            foreign(InvoiceLineModel.team_id) == InvoiceModel.team_id,
            foreign(InvoiceLineModel.invoice_id) == InvoiceModel.id,
        ),
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_invoice_line_team_id_id"),
        ForeignKeyConstraint(["team_id", "invoice_id"],
                             ["invoice.team_id", "invoice.id"],
                             ondelete="CASCADE", name="fk_invoice_line_invoice_team_id_id"),
        Index("ix_invoice_line_team_id_id", "team_id", "id"),
        Index("ix_invoice_line_team_invoice", "team_id", "invoice_id"),
    )
