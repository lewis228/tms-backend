"""SQLAlchemy 베이스 + 믹스인.

- Base: DeclarativeBase
- UUIDPrimaryKeyMixin: id (CHAR(36) UUID4)
- TimestampMixin: created_at / updated_at
- SoftDeleteMixin: is_deleted
- TenantMixin: tenant_id (FK → tenants.id ON DELETE CASCADE)
- AuditMixin = UUID + Timestamp + SoftDelete
- TenantAuditMixin = Audit + Tenant  ← 도메인 표준
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """모든 ORM 클래스의 베이스. alembic 이 metadata 를 여기서 가져간다."""


def _gen_uuid() -> str:
    return str(uuid.uuid4())


class UUIDPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_gen_uuid
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", index=True
    )


class TenantMixin:
    @declared_attr
    def tenant_id(cls) -> Mapped[str]:
        return mapped_column(
            String(36),
            ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )


class AuditMixin(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    pass


class TenantAuditMixin(AuditMixin, TenantMixin):
    """⭐ 도메인 모델 기본 베이스 (Tenant + Audit)."""
