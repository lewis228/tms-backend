from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Index, UniqueConstraint, and_,
)
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from common.const.settings import settings


class ShipmentModel(Base, TeamScopedMixin):
    """MBL 단위 해상 shipment. 팀 scoped — 팀 삭제 시 `team_id` FK CASCADE로
    shipment/container/event/scrape_log/tag 링크까지 일괄 정리된다.

    MBL 은 전역 unique 가 아니라 **팀당 unique** 다. 같은 MBL 을 여러 팀이
    독립적으로 추적하는 경우를 허용한다.
    """

    __tablename__ = "ocean_shipments"

    mbl: Mapped[str] = mapped_column(String(50), nullable=False)
    # 전역 carriers 테이블 FK. 프론트 Quick Entry 단계에서 필수 입력이며
    # 요청 스키마가 선-검증한다. 자동 감지(prefix 매핑) 는 프론트에서 기본값을
    # 채우는 편의 기능일 뿐, 서버는 ``carrier_id`` 가 실제 유효한 row 를 가리키는지
    # 검증한 뒤 저장한다. 미지정 시점은 존재하지 않으므로 NOT NULL.
    carrier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("carriers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # 시스템 레벨 추적 상태. 기본값은 등록 직후의 PENDING —
    # 첫 스크래핑 결과로 tracking/awaiting_manifest/failed 중 하나로 전이된다.
    # 값 목록은 `ocean/shipment/const/status.py:ShipmentStatus` 참조.
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending")
    vessel_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 선박 정규화 — 스크래퍼는 vessel_name 문자열만 주므로 `vessel_name` 은 raw
    # 보존용으로 두고, `vessels` 전역 마스터로 해석된 FK 를 별도로 들고 있는다.
    # `resolve_vessel` 태스크가 MMSI/IMO/name 순으로 매칭해 이 컬럼을 채운다
    # (해석 실패 시 NULL). `vessel` 관계는 실시간 위치(VesselPositionModel) 조회
    # 경로로 사용된다 — self.vessel.position.latitude 등.
    vessel_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("vessels.id", ondelete="SET NULL"),
        nullable=True,
    )
    voyage_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Port of Loading / Port of Discharge — 전역 locations 테이블 FK.
    # 매핑 실패 시 NULL; 원본 raw 텍스트는 scrape_logs.result_json 에 보존.
    pol_location_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    pod_location_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    etd: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    eta: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tracking_frequency: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    next_scrape_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # 사용자 표시용 메타. 스크래퍼는 건드리지 않음.
    # Customer 는 팀 scoped ``customers`` 마스터 FK — 한 shipment 당 단일 고객.
    # ON DELETE RESTRICT: 연결된 shipment 가 있는 고객은 하드 삭제 차단 (soft delete 만 허용).
    customer_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # ── 관계 ────────────────────────────────────────────────
    # ``team`` 관계는 TeamScopedMixin 이 자동으로 제공 (lazy="selectin").

    # Carrier 는 조회 시 거의 항상 함께 쓰이므로 lazy="selectin" — ORM default
    # 인 "raise" 예외. N+1 리스크는 목록 쿼리가 selectinload 로 수동 제어.
    carrier = relationship(
        "CarrierModel",
        lazy="selectin",
    )

    # Vessel 은 거의 항상 같이 쓰이므로 selectin — 실시간 위치 표시에도 nested
    # position 이 필요하다 (VesselModel.position 이 이미 selectin 이라 vessel 만
    # 당기면 위치까지 한 번에 들어옴).
    vessel = relationship(
        "VesselModel",
        foreign_keys=[vessel_id],
        lazy="selectin",
    )

    # Location FK 들도 selectin — 목록/상세 모두 nested 객체 필요.
    pol_location = relationship(
        "LocationModel",
        foreign_keys=[pol_location_id],
        lazy="selectin",
    )
    pod_location = relationship(
        "LocationModel",
        foreign_keys=[pod_location_id],
        lazy="selectin",
    )

    # Customer 는 목록/상세 양쪽에서 nested 객체로 렌더링 — selectin.
    customer = relationship(
        "CustomerModel",
        foreign_keys=[customer_id],
        lazy="selectin",
    )

    # Ref numbers — 1:N 자식 라인. 헤더 삭제 시 FK CASCADE 로 정리.
    ref_numbers = relationship(
        "RefNumberModel",
        back_populates="shipment",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="RefNumberModel.id.asc()",
        primaryjoin=lambda: and_(
            foreign(__import__("ocean.ref_number.model", fromlist=["RefNumberModel"]).RefNumberModel.team_id) == ShipmentModel.team_id,
            foreign(__import__("ocean.ref_number.model", fromlist=["RefNumberModel"]).RefNumberModel.shipment_id) == ShipmentModel.id,
        ),
        passive_deletes=True,
    )

    containers = relationship(
        "ContainerModel",
        back_populates="shipment",
        cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by="ContainerModel.id.asc()",
        primaryjoin=lambda: and_(
            foreign(__import__("ocean.container.model", fromlist=["ContainerModel"]).ContainerModel.team_id) == ShipmentModel.team_id,
            foreign(__import__("ocean.container.model", fromlist=["ContainerModel"]).ContainerModel.shipment_id) == ShipmentModel.id,
        ),
        passive_deletes=True,
    )

    events = relationship(
        "ContainerEventModel",
        back_populates="shipment",
        cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by="ContainerEventModel.timestamp.desc()",
        primaryjoin=lambda: and_(
            foreign(__import__("ocean.container_event.model", fromlist=["ContainerEventModel"]).ContainerEventModel.team_id) == ShipmentModel.team_id,
            foreign(__import__("ocean.container_event.model", fromlist=["ContainerEventModel"]).ContainerEventModel.shipment_id) == ShipmentModel.id,
        ),
        passive_deletes=True,
        # ContainerModel.events / ContainerEventModel.shipment 와 team_id 컬럼 공유 — 경고 억제.
        overlaps="container,shipment,events",
    )

    scrape_logs = relationship(
        "ScrapeLogModel",
        back_populates="shipment",
        cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by="ScrapeLogModel.scraped_at.desc()",
        primaryjoin=lambda: and_(
            foreign(__import__("ocean.scrape_log.model", fromlist=["ScrapeLogModel"]).ScrapeLogModel.team_id) == ShipmentModel.team_id,
            foreign(__import__("ocean.scrape_log.model", fromlist=["ScrapeLogModel"]).ScrapeLogModel.shipment_id) == ShipmentModel.id,
        ),
        passive_deletes=True,
    )

    # M2M to Tag via ocean_shipment_tags (팀 scoped 조인 테이블).
    tags = relationship(
        "TagModel",
        secondary="ocean_shipment_tags",
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by="TagModel.created_at.asc()",
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_ocean_shipments_team_id_id"),
        UniqueConstraint("team_id", "mbl", name="uq_ocean_shipments_team_mbl"),
        Index("ix_ocean_shipments_team_id_id", "team_id", "id"),
        Index("ix_ocean_shipments_team_mbl", "team_id", "mbl"),
        Index("ix_ocean_shipments_team_status", "team_id", "status"),
        Index("ix_ocean_shipments_team_carrier_id", "team_id", "carrier_id"),
        Index("ix_ocean_shipments_team_customer_id", "team_id", "customer_id"),
        Index("ix_ocean_shipments_team_vessel_id", "team_id", "vessel_id"),
        Index("ix_ocean_shipments_team_pol_location_id", "team_id", "pol_location_id"),
        Index("ix_ocean_shipments_team_pod_location_id", "team_id", "pod_location_id"),
        Index("ix_ocean_shipments_team_next_scrape_at", "team_id", "next_scrape_at"),
        # Beat 주기 스캔용 — team 무관하게 전체 shipment 에서 next_scrape_at 필터링 한다.
        Index("ix_ocean_shipments_next_scrape_at", "next_scrape_at"),
    )
