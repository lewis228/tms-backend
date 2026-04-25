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


class ContainerEventModel(Base, TeamScopedMixin):
    """컨테이너별 트래킹 이벤트 히스토리.

    모든 이벤트는 **반드시** 특정 컨테이너에 귀속된다 (``container_id`` NOT NULL).
    선박 레벨 이벤트(출항/입항 등) 는 scraping 측 fan-out 로직이 해당 선적에
    실린 모든 컨테이너로 복제해 저장하므로 개념적 "shipment 레벨" 이벤트도
    결과적으로 각 컨테이너 타임라인에 나타난다.
    """

    __tablename__ = "ocean_container_events"
    __with_team_rel__ = False

    shipment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    container_id: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # 이벤트 발생 위치 — 전역 locations 테이블 FK. 매핑 실패 시 NULL (원본 텍스트는
    # scrape_logs.result_json 에 보존).
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # 선사가 내려준 raw 이벤트 타입 힌트 (일부 선사만 제공). 없으면 NULL.
    event_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 정규화된 ContainerEventType Enum 값 (예: "vessel_departed", "gate_out").
    # normalizer 가 `description` 또는 `event_type` raw 문자열로부터 해석.
    # UI 타임라인 아이콘 / 색상 / 집계 쿼리가 이 컬럼을 사용.
    event_type_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # 이벤트 고유 해시 — sha256(container_id + timestamp_iso + description).
    # 앱 레벨 dedup (save_tracking_result) 외에 DB 레벨 3중 방어선으로 동일
    # 이벤트 중복 INSERT 를 차단한다. NULL 로 들어오지 않도록 insert 시점에
    # 반드시 채워야 함 — scraping 레포의 _event_hash helper 참조.
    event_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default="",
    )

    # ── 관계 ────────────────────────────────────────────────
    # ``team_id`` 컬럼이 ShipmentModel / ContainerModel 양쪽 관계에 공통으로
    # 쓰이므로 SQLAlchemy 가 "writing overlap" 경고를 낸다. 세 관계 모두
    # **읽기/쓰기 의도가 같음** (team_id 는 컨테이너·선적·이벤트가 모두 동일) 이므로
    # ``overlaps`` 로 명시해 경고만 억제한다 (실제 write 주체는 이벤트 삽입 시의
    # team_id 할당 한 번 뿐).
    shipment = relationship(
        "ShipmentModel",
        back_populates="events",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: and_(
            foreign(ContainerEventModel.team_id) == __import__("ocean.shipment.model", fromlist=["ShipmentModel"]).ShipmentModel.team_id,
            foreign(ContainerEventModel.shipment_id) == __import__("ocean.shipment.model", fromlist=["ShipmentModel"]).ShipmentModel.id,
        ),
        overlaps="container,events",
    )

    container = relationship(
        "ContainerModel",
        back_populates="events",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: and_(
            foreign(ContainerEventModel.team_id) == __import__("ocean.container.model", fromlist=["ContainerModel"]).ContainerModel.team_id,
            foreign(ContainerEventModel.container_id) == __import__("ocean.container.model", fromlist=["ContainerModel"]).ContainerModel.id,
        ),
        overlaps="shipment,events",
    )

    location = relationship(
        "LocationModel",
        foreign_keys=[location_id],
        lazy="selectin",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "shipment_id"],
            ["ocean_shipments.team_id", "ocean_shipments.id"],
            ondelete="CASCADE",
            name="fk_ocean_container_events_shipment_team_id_id",
        ),
        ForeignKeyConstraint(
            ["team_id", "container_id"],
            ["ocean_containers.team_id", "ocean_containers.id"],
            ondelete="CASCADE",
            name="fk_ocean_container_events_container_team_id_id",
        ),
        UniqueConstraint("team_id", "id", name="uq_ocean_container_events_team_id_id"),
        # 동일 컨테이너에 대한 중복 이벤트 차단 — Redis 락 장애 / 동시 스크래핑
        # race 방어용 3중 방어선. event_hash 가 NULL 이거나 충돌하면 INSERT 가
        # IntegrityError 로 실패 — 호출부가 try/except 로 흡수한다.
        UniqueConstraint(
            "team_id",
            "container_id",
            "event_hash",
            name="uq_ocean_container_events_team_container_hash",
        ),
        Index("ix_ocean_container_events_team_id_id", "team_id", "id"),
        Index("ix_ocean_container_events_team_shipment", "team_id", "shipment_id"),
        Index("ix_ocean_container_events_team_container", "team_id", "container_id"),
        Index("ix_ocean_container_events_team_timestamp", "team_id", "timestamp"),
        Index("ix_ocean_container_events_team_location_id", "team_id", "location_id"),
        Index(
            "ix_ocean_container_events_team_event_type_code",
            "team_id",
            "event_type_code",
        ),
    )
