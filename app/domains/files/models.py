"""File 모델 — 폴리모픽 첨부.

(domain, object_id) 쌍이 어떤 도메인 어느 row 에 첨부되는지 가리킴.
실제 FK 는 걸지 않음 (도메인 N개 polymorphic). 화이트리스트 검증은 service 에서.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantAuditMixin


class File(TenantAuditMixin, Base):
    __tablename__ = "files"
    __table_args__ = (
        Index("ix_files_tenant_attach", "tenant_id", "domain", "object_id"),
        Index("ix_files_tenant_kind", "tenant_id", "kind"),
    )

    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)

    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    uploaded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
