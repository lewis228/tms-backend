from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Index, UniqueConstraint,
    ForeignKeyConstraint, and_,
)
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from common.const.settings import settings


class ContainerModel(Base, TeamScopedMixin):
    """컨테이너 단위 상세. Shipment(= MBL) 의 자식 라인 테이블.

    ``(team_id, shipment_id)`` 복합 FK 로 크로스 테넌시 누출을 DB 레벨에서 차단한다.
    부모 shipment 가 삭제되면 CASCADE 로 같이 삭제된다.
    """

    __tablename__ = "ocean_containers"
    # 라인 테이블 — ``.team`` 관계는 부모(ShipmentModel) 를 통해 접근.
    __with_team_rel__ = False

    shipment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[str] = mapped_column(String(20), nullable=False)
    # 선사가 돌려준 raw 문자열 — 디버깅 / 재해석용 원본 보존. 예: "40' DH",
    # "40HC", "40 HIGH CUBE" 처럼 포맷이 제각각이라 집계 쿼리엔 쓰지 못한다.
    size_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # 정규화된 ContainerSizeType Enum 값 (예: "40HC"). 집계 / 필터 / 프론트
    # 탭 분류는 이 컬럼을 사용. normalizer 매칭 실패 시 NULL → 로그 모니터링
    # 후 정규식 추가 + backfill 로 채움.
    size_type_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # 최신 이벤트 description 의 raw 문자열 — 예: "Empty returned", "gate out".
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # 정규화된 ContainerPhysicalStatus Enum 값 (예: "empty_returned").
    # Shipments 리스트의 "On Ship / Arrived / Stopped" 탭이 이 컬럼으로 EXISTS
    # 서브쿼리 필터링한다.
    physical_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # 터미널 = 전역 locations 테이블에서 kind='cargo_terminal' (parent = 모항) 로
    # 표현. varchar 폴백 없음 — raw 텍스트는 scrape_logs.result_json 에 보존.
    terminal_location_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    lfd: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── 관계 ────────────────────────────────────────────────
    shipment = relationship(
        "ShipmentModel",
        back_populates="containers",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: and_(
            foreign(ContainerModel.team_id) == __import__("ocean.shipment.model", fromlist=["ShipmentModel"]).ShipmentModel.team_id,
            foreign(ContainerModel.shipment_id) == __import__("ocean.shipment.model", fromlist=["ShipmentModel"]).ShipmentModel.id,
        ),
    )

    events = relationship(
        "ContainerEventModel",
        back_populates="container",
        cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by="ContainerEventModel.timestamp.desc()",
        primaryjoin=lambda: and_(
            foreign(__import__("ocean.container_event.model", fromlist=["ContainerEventModel"]).ContainerEventModel.team_id) == ContainerModel.team_id,
            foreign(__import__("ocean.container_event.model", fromlist=["ContainerEventModel"]).ContainerEventModel.container_id) == ContainerModel.id,
        ),
        passive_deletes=True,
        # ShipmentModel.events / ContainerEventModel.shipment/container 와 team_id 컬럼 공유 — 경고 억제.
        overlaps="shipment,container,events",
    )

    terminal_location = relationship(
        "LocationModel",
        foreign_keys=[terminal_location_id],
        lazy="selectin",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "shipment_id"],
            ["ocean_shipments.team_id", "ocean_shipments.id"],
            ondelete="CASCADE",
            name="fk_ocean_containers_shipment_team_id_id",
        ),
        UniqueConstraint("team_id", "id", name="uq_ocean_containers_team_id_id"),
        Index("ix_ocean_containers_team_id_id", "team_id", "id"),
        Index("ix_ocean_containers_team_shipment", "team_id", "shipment_id"),
        Index("ix_ocean_containers_team_number", "team_id", "number"),
        Index("ix_ocean_containers_team_terminal_location_id", "team_id", "terminal_location_id"),
        # 프론트 Shipments 탭 (On Ship / Arrived / Stopped Tracking) 이
        # physical_status 로 EXISTS 서브쿼리를 돌리므로 필수.
        Index("ix_ocean_containers_team_physical_status", "team_id", "physical_status"),
        Index("ix_ocean_containers_team_size_type_code", "team_id", "size_type_code"),
    )
