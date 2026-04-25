"""StreetTurn 모델.

Import D/O 가 비운 컨테이너를 즉시 Export D/O 로 재사용.
- Import: COMPLETED, Export: DISPATCHED, container_number 동일
- 한 Import / Export 에 하나만 연결 가능 (UniqueConstraint)
"""
from __future__ import annotations

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantAuditMixin
from app.models.enums import StreetTurnLinkType


class StreetTurn(TenantAuditMixin, Base):
    __tablename__ = "street_turns"
    __table_args__ = (
        UniqueConstraint("import_order_id", name="uq_st_import"),
        UniqueConstraint("export_order_id", name="uq_st_export"),
        Index("ix_st_tenant_container", "tenant_id", "container_number"),
    )

    import_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("delivery_orders.id", ondelete="CASCADE"), nullable=False
    )
    export_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("delivery_orders.id", ondelete="CASCADE"), nullable=False
    )
    container_number: Mapped[str] = mapped_column(String(16), nullable=False)
    link_type: Mapped[StreetTurnLinkType] = mapped_column(
        SAEnum(StreetTurnLinkType, name="street_turn_link_type"),
        nullable=False,
        default=StreetTurnLinkType.MANUAL,
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
