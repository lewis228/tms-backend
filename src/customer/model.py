from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, UniqueConstraint, Index
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin


class CustomerModel(Base, TeamScopedMixin):
    """Shipment 에 매핑되는 팀 scoped 고객 마스터.

    shipment:customer = N:1. Tag 와 달리 shipment 당 **단일** 고객만 붙는다.
    팀당 ``name`` 은 unique — 같은 이름을 중복 생성할 수 없다 (Tag 와 동일 규약).
    """

    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_customers_team_id_id"),
        UniqueConstraint("team_id", "name", name="uq_customers_team_name"),
        Index("ix_customers_team_id_id", "team_id", "id"),
        Index("ix_customers_team_name", "team_id", "name"),
    )
