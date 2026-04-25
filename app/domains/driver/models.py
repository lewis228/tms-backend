"""Driver 모바일 앱 부속 모델 — PushToken, DriverLocationPing.

Driver 본체 모델은 domains/drivers/models.py 에 있음 (테넌트 멤버 관리용).
여기는 모바일 앱에서만 쓰는 토큰/위치 추적용.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantAuditMixin


class DriverPushToken(TenantAuditMixin, Base):
    __tablename__ = "driver_push_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="uq_dpt_token"),
        Index("ix_dpt_tenant_driver_platform", "tenant_id", "driver_id", "platform"),
    )

    driver_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(16), nullable=False)  # ios | android | web
    token: Mapped[str] = mapped_column(String(512), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DriverLocationPing(TenantAuditMixin, Base):
    """Background GPS 배치 — 15분 간격 등.

    실시간 추적 채널은 realtime/ 으로. 여기는 영속 기록.
    """

    __tablename__ = "driver_location_pings"
    __table_args__ = (
        Index("ix_dlp_tenant_driver_time", "tenant_id", "driver_id", "occurred_at"),
    )

    driver_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False
    )
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    speed_kmh: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    heading_deg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    accuracy_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
