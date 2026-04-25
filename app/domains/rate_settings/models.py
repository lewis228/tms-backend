"""RateSetting 모델.

테넌트별 요율 정책. effective_date 기준으로 활성화.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Enum as SAEnum, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantAuditMixin
from app.models.enums import RateType


class RateSetting(TenantAuditMixin, Base):
    __tablename__ = "rate_settings"
    __table_args__ = (
        Index("ix_rate_tenant_active_effective", "tenant_id", "is_active", "effective_date"),
    )

    rate_type: Mapped[RateType] = mapped_column(
        SAEnum(RateType, name="rate_type"), nullable=False
    )
    flat_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    rate_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    rate_per_mile: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
