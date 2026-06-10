# src/customer/model.py
from __future__ import annotations
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, Date, Text, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from customer.const.status import PartnerKind


class CustomerModel(Base, TeamScopedMixin):
    """협력사 (Team-Scoped). H-5: kind 로 customer/carrier/broker/vendor 구분."""
    __tablename__ = "customer"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[PartnerKind] = mapped_column(
        SAEnum(PartnerKind, name="partner_kind"),
        default=PartnerKind.CUSTOMER,
        server_default=PartnerKind.CUSTOMER.value,
        nullable=False,
    )

    billing_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_name:    Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_email:   Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_phone:   Mapped[str | None] = mapped_column(String(64),  nullable=True)

    # ── CARRIER 전용 컴플라이언스 ─────────────────────────────
    mc_number:           Mapped[str | None]  = mapped_column(String(32), nullable=True)
    dot_number:          Mapped[str | None]  = mapped_column(String(32), nullable=True)
    insurance_expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    insurance_doc_url:   Mapped[str | None]  = mapped_column(String(500), nullable=True)
    w9_doc_url:          Mapped[str | None]  = mapped_column(String(500), nullable=True)
    payment_terms_days:  Mapped[int | None]  = mapped_column(Integer, nullable=True)

    # 배송지 zip(전역 마스터) — 정산 dest 자동채움
    zip_id: Mapped[int | None] = mapped_column(
        ForeignKey("zip_code.id", ondelete="SET NULL"), nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_customer_team_id_id"),
        UniqueConstraint("team_id", "code", name="uq_customer_team_code"),
        Index("ix_customer_team_active_id", "team_id", "is_active", "id"),
        Index("ix_customer_team_kind",       "team_id", "kind"),
        Index("ix_customer_team_name",       "team_id", "name"),
        Index("ix_customer_team_updated_at", "team_id", "updated_at"),
        Index("ix_customer_team_zip", "team_id", "zip_id"),
    )
