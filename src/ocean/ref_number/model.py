from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from sqlalchemy import (
    String, Integer, Index, UniqueConstraint, ForeignKeyConstraint, and_,
)
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from common.const.settings import settings


class RefNumberModel(Base, TeamScopedMixin):
    """Shipment 에 첨부되는 사용자 참조번호 (PO / Order / 내부 코드 등).

    shipment:ref_number = 1:N. Tag 와 달리 전역 마스터가 아니라 **shipment 자체의
    자식 라인** — 다른 shipment 와 값을 공유하지 않고, 같은 값이 여러 shipment 에
    중복 존재할 수 있다. 같은 shipment 안에서는 ``value`` 중복 금지.

    자연키는 ``(team_id, shipment_id, value)`` unique.
    """

    __tablename__ = "ocean_shipment_ref_numbers"
    __with_team_rel__ = False

    shipment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[str] = mapped_column(String(100), nullable=False)

    shipment = relationship(
        "ShipmentModel",
        back_populates="ref_numbers",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: and_(
            foreign(RefNumberModel.team_id) == __import__("ocean.shipment.model", fromlist=["ShipmentModel"]).ShipmentModel.team_id,
            foreign(RefNumberModel.shipment_id) == __import__("ocean.shipment.model", fromlist=["ShipmentModel"]).ShipmentModel.id,
        ),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "shipment_id"],
            ["ocean_shipments.team_id", "ocean_shipments.id"],
            ondelete="CASCADE",
            name="fk_ocean_shipment_ref_numbers_shipment_team_id_id",
        ),
        UniqueConstraint("team_id", "id", name="uq_ocean_shipment_ref_numbers_team_id_id"),
        UniqueConstraint(
            "team_id", "shipment_id", "value",
            name="uq_ocean_shipment_ref_numbers_team_shipment_value",
        ),
        Index("ix_ocean_shipment_ref_numbers_team_id_id", "team_id", "id"),
        Index("ix_ocean_shipment_ref_numbers_team_shipment", "team_id", "shipment_id"),
        # 역검색용 — 사용자가 "PO-1234" 로 shipment 찾을 때 쓴다.
        Index("ix_ocean_shipment_ref_numbers_team_value", "team_id", "value"),
    )
