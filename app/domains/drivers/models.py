"""Driver 모델 — User 와 1:1 (user.role=DRIVER).

Driver 는 운전 면허/차량 메타. 인증/이메일/이름은 User 에 있음.
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantAuditMixin


class Driver(TenantAuditMixin, Base):
    __tablename__ = "drivers"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_drivers_user"),
        Index("ix_drivers_tenant_status", "tenant_id", "is_active"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    license_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    license_state: Mapped[str | None] = mapped_column(String(8), nullable=True)
    truck_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
