# src/rate_setting/model.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Numeric, Date, Text, Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.tenant_scoped_mixin import TenantScopedMixin
from rate_setting.const.rate_type import RateType


class RateSettingModel(Base, TenantScopedMixin):
    """
    요율 정의 (Tenant-Scoped).

    rate_type 별로 활성화되는 amount 컬럼이 다름:
    - FLAT_RATE  → flat_amount
    - PERCENTAGE → rate_percent
    - PER_MILE   → rate_per_mile
    (다른 컬럼은 NULL — service 가 강제)
    """
    __tablename__ = "rate_setting"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rate_type: Mapped[RateType] = mapped_column(
        SAEnum(RateType, name="rate_type"), nullable=False,
    )

    flat_amount:    Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    rate_percent:   Mapped[Decimal | None] = mapped_column(Numeric(7, 4),  nullable=True)
    rate_per_mile:  Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    description:    Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_rate_setting_tenant_id_id"),
        Index("ix_rate_setting_tenant_active_id", "tenant_id", "is_active", "id"),
        Index("ix_rate_setting_tenant_name",       "tenant_id", "name"),
        Index("ix_rate_setting_tenant_effective",  "tenant_id", "effective_date"),
        Index("ix_rate_setting_tenant_updated_at", "tenant_id", "updated_at"),
    )
