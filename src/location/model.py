from __future__ import annotations
from typing import Any, Optional
from sqlalchemy import (
    JSON, Boolean, Float, ForeignKey, Index, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from common.model.base_model import Base


# Kind enum — stored as short string to keep the schema portable. Mirrors the
# functional classification in UN/LOCODE (Function column positions) but
# normalized into a single categorical field.
KIND_SEAPORT = "seaport"
KIND_AIRPORT = "airport"
KIND_RAIL_TERMINAL = "rail_terminal"
KIND_ROAD_TERMINAL = "road_terminal"
KIND_CARGO_TERMINAL = "cargo_terminal"   # Cargo handling facility inside a port/airport
KIND_INLAND = "inland"                    # Inland clearance depot / ICD / warehouse
KIND_CITY = "city"                        # Generic municipality
KIND_BORDER = "border"                    # Border crossing
KIND_POSTAL = "postal"                    # Postal exchange — rare, mostly ignored
KIND_UNKNOWN = "unknown"

ALL_KINDS = frozenset({
    KIND_SEAPORT, KIND_AIRPORT, KIND_RAIL_TERMINAL, KIND_ROAD_TERMINAL,
    KIND_CARGO_TERMINAL, KIND_INLAND, KIND_CITY, KIND_BORDER, KIND_POSTAL,
    KIND_UNKNOWN,
})


class LocationModel(Base):
    """전역 위치 마스터. **모든 운송 도메인(ocean/air/rail)이 공유**.

    UN/LOCODE 를 기반으로 seed 되며, 포트/공항/내륙거점/도시 등 transport 관련
    노드를 단일 테이블에 담는다. 터미널(port 내 화물 handling 시설)은
    ``kind=cargo_terminal`` + ``parent_location_id`` 로 모항을 가리키는 방식으로
    표현한다 — 별도 terminals 테이블을 만들지 않는 이유.

    ``unlocode`` 는 선택적 — UN/LOCODE 가 발급되지 않은 사설 터미널은 NULL.
    """

    __tablename__ = "locations"

    # UN/LOCODE 5자 코드 (country_code + subdivision_code). 공식 발급 지점만 값.
    unlocode: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    # 표시명. diacritics 포함 (한글 지원은 향후 name_i18n 으로).
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 다국어 표기 — {"ko": "부산", "zh": "釜山"}. 지금은 씨앗 단계에선 NULL.
    name_i18n: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    # ISO 3166-1 alpha-2.
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    # ISO 3166-2 subdivision (예: US-CA, KR-11). nullable — 일부 도시국가.
    subdivision: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # 노드 분류 — ALL_KINDS 중 하나.
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=KIND_UNKNOWN,
    )
    # 터미널 → 모항 같은 계층 관계. self-FK.
    parent_location_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    # WGS84 좌표 (UN/LOCODE 의 DDMM 포맷을 decimal 로 변환해 저장).
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # IATA 3자 (공항인 경우). 다른 kind 에선 NULL.
    iata: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    # UN/LOCODE 외 공식 식별자 — 관리자 운영용.
    external_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 피커에 노출될지 여부. polluted/non-operational 위치는 false 로 숨김.
    is_supported: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1",
    )

    # ── 관계 ────────────────────────────────────────────────
    parent = relationship(
        "LocationModel",
        remote_side="LocationModel.id",
        lazy="selectin",
    )
    aliases = relationship(
        "LocationAliasModel",
        back_populates="location",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )

    __table_args__ = (
        UniqueConstraint("unlocode", name="uq_locations_unlocode"),
        Index("ix_locations_country", "country_code"),
        Index("ix_locations_kind", "kind"),
        Index("ix_locations_name", "name"),
        Index("ix_locations_parent", "parent_location_id"),
        Index("ix_locations_iata", "iata"),
    )


class LocationAliasModel(Base):
    """선사가 반환한 자유-형식 location 텍스트를 정규화된 ``location_id`` 로
    맵핑하는 캐시.

    매퍼가 exact/fuzzy 매칭으로 성공한 결과를 여기에 기록해, 동일한 raw_text
    가 다시 들어오면 fuzzy 계산을 건너뛰고 바로 resolve 한다. 관리자 수동
    매핑도 여기에 쌓임.
    """

    __tablename__ = "location_aliases"

    location_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 원본 그대로 (정규화 X) — 공백/대소문자/쉼표 조합이 곧 키.
    raw_text: Mapped[str] = mapped_column(String(300), nullable=False)
    # 특정 선사에만 적용되는 별칭이면 carrier_id 채움. 보편 별칭은 NULL.
    carrier_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("carriers.id", ondelete="CASCADE"),
        nullable=True,
    )
    # 'exact' / 'fuzzy' / 'manual' / 'seed' — 매핑 출처.
    confidence: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="exact",
    )

    location = relationship("LocationModel", back_populates="aliases", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "raw_text", "carrier_id", name="uq_location_aliases_raw_carrier",
        ),
        Index("ix_location_aliases_location", "location_id"),
        Index("ix_location_aliases_raw", "raw_text"),
    )
