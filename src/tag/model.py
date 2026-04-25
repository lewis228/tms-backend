from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, UniqueConstraint, Index, ForeignKeyConstraint
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin


class TagModel(Base, TeamScopedMixin):
    """Shipment 분류용 팀-scoped 태그 (우선순위, 고객 세그먼트 등).
    유니크는 팀당이라 서로 다른 팀이 독립적으로 'priority' 태그를 가질 수 있다.
    색상은 칩 렌더링용 hex 문자열 그대로 저장.
    """

    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_tags_team_id_id"),
        UniqueConstraint("team_id", "name", name="uq_tags_team_name"),
        Index("ix_tags_team_id_id", "team_id", "id"),
        Index("ix_tags_team_name", "team_id", "name"),
    )


class OceanShipmentTagModel(Base, TeamScopedMixin):
    """ocean_shipments 와 tags 의 조인 테이블.

    - ``(team_id, shipment_id)`` 복합 FK: 하드 삭제 시 cascade 로 링크 정리.
      (soft-delete 된 shipment 는 링크 유지 — 복구 가능.)
    - ``(team_id, tag_id)`` 복합 FK: RESTRICT — 여전히 어딘가에 붙어있는 태그
      하드 삭제 차단. 호출부가 먼저 detach 하거나 태그를 soft-delete (`is_active=False`) 하도록.
    """

    __tablename__ = "ocean_shipment_tags"
    __with_team_rel__ = False

    shipment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tag_id: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "shipment_id"],
            ["ocean_shipments.team_id", "ocean_shipments.id"],
            ondelete="CASCADE",
            name="fk_ocean_shipment_tags_shipment_team_id_id",
        ),
        ForeignKeyConstraint(
            ["team_id", "tag_id"],
            ["tags.team_id", "tags.id"],
            ondelete="RESTRICT",
            name="fk_ocean_shipment_tags_tag_team_id_id",
        ),
        UniqueConstraint("team_id", "id", name="uq_ocean_shipment_tags_team_id_id"),
        UniqueConstraint(
            "team_id", "shipment_id", "tag_id",
            name="uq_ocean_shipment_tags_team_shipment_tag",
        ),
        Index("ix_ocean_shipment_tags_team_id_id", "team_id", "id"),
        Index("ix_ocean_shipment_tags_team_shipment", "team_id", "shipment_id"),
        Index("ix_ocean_shipment_tags_team_tag", "team_id", "tag_id"),
    )
