# src/street_turn/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, ForeignKey, Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.tenant_scoped_mixin import TenantScopedMixin
from street_turn.const.link_type import StreetTurnLinkType


class StreetTurnModel(Base, TenantScopedMixin):
    """Street turn — Import 컨테이너를 Export 에 직접 사용 (port 회수 절감).

    사전조건 (service 가 강제):
    - Import D/O 의 status == COMPLETED
    - Export D/O 의 status == DISPATCHED
    - 두 D/O 의 container_number 동일
    - 두 D/O 모두 다른 street_turn 에 연결되지 않음
    """
    __tablename__ = "street_turn"

    import_order_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_order.id", ondelete="RESTRICT"), nullable=False,
    )
    export_order_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_order.id", ondelete="RESTRICT"), nullable=False,
    )
    container_number: Mapped[str] = mapped_column(String(11), nullable=False)
    link_type: Mapped[StreetTurnLinkType] = mapped_column(
        SAEnum(StreetTurnLinkType, name="street_turn_link_type"),
        default=StreetTurnLinkType.MANUAL,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_street_turn_tenant_id_id"),
        # Import / Export 각각 하나의 street turn 에만 연결
        UniqueConstraint("import_order_id", name="uq_street_turn_import"),
        UniqueConstraint("export_order_id", name="uq_street_turn_export"),
        Index("ix_street_turn_tenant_container", "tenant_id", "container_number"),
        Index("ix_street_turn_tenant_active_id", "tenant_id", "is_active", "id"),
        Index("ix_street_turn_tenant_updated_at", "tenant_id", "updated_at"),
    )
