"""Vessel + VesselPosition 모델.

================================================================================
⭐ 왜 전역 (Team scoped 아님) 인가
================================================================================
선박은 **물리적 자산**이다. 한 척의 배가 여러 팀의 여러 MBL 을 동시에 실고
다닌다 — 예를 들어 X-PRESS PHOENIX 가 Lewis 팀의 MAEU265099858 과 Acme 팀의
SMLMSEL6A6437700 을 같이 실을 수 있다. 각 팀마다 같은 선박 행을 중복 저장하면:
  - AIS API 호출이 N 배 늘어나 비용 폭발 (MarineTraffic 은 MMSI 수 기반 과금)
  - 같은 선박의 위치가 팀마다 다르게 보일 수 있음 (정합성 깨짐)
  - vessel_name / MMSI 변경 시 N 곳을 업데이트해야 함

따라서 `carrier`, `location` 과 동일한 **전역 마스터** 설계를 쓴다. 팀 격리는
`ocean_shipments.vessel_id` 를 통해 "이 팀이 추적하는 선박 목록" 을 조인으로
풀어낸다 — 선박 자체는 공유, 매핑만 팀별.

================================================================================
테이블 구조
================================================================================

1. **vessels** — 선박 마스터 (식별자 + 스펙)
     id, mmsi, imo_number, name, flag, length_m, breadth_m,
     gross_tonnage, vessel_type, year_built, owner, ...

2. **vessel_positions** — 선박별 최신 위치 (1-to-1)
     id, vessel_id (UNIQUE), latitude, longitude, speed_knots,
     heading_degrees, navigation_status, reported_at

   ⚠️ 히스토리(항적) 가 필요하면 별도 `vessel_position_history` 테이블을
   추가하라. 여기는 "지금 어디 있는가" 한 행만 유지 (frequent UPDATE).

================================================================================
MMSI 가 없는 경우 (nullable)
================================================================================
스크래퍼는 Vessel Name 까지만 주는 경우가 대부분. MMSI 는 AIS 업체 Search API
를 별도 호출해야 얻는다. 실패하거나 대기 중에는 MMSI 가 NULL 상태로 vessels
row 가 먼저 생성될 수 있다. 이런 row 에 대해서는:
  - `poll_fleet_positions` 태스크가 skip (MMSI 필요)
  - `resolve_vessel` 태스크가 재시도로 MMSI 채움
  - 채워지면 다음 poll 사이클부터 위치 추적 대상에 포함

================================================================================
Ocean 도메인과의 연결
================================================================================
`ocean_shipments.vessel_id` 를 추가해 "이 shipment 를 실은 선박" 을 가리킨다.
Nullable — 새 MBL 등록 직후 vessel 해석 전에는 NULL. scraping 완료 후
`resolve_vessel` 태스크가 vessel 을 찾아 UPDATE.

크로스 테넌시 우려? 없다 — `vessels` 자체에 team_id 가 없으니 어떤 팀이든 동일
vessel 행을 참조할 수 있다. 팀 격리는 `ocean_shipments.team_id` 필터로 이미
보장됨 (Repository 레벨).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DECIMAL,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.const.settings import settings
from common.model.base_model import Base

if TYPE_CHECKING:
    # Avoid runtime circular import. Only needed for type hints.
    pass


class VesselModel(Base):
    """선박 마스터.

    AIS 업체 search API 가 반환하는 식별자 + 스펙을 보관한다.
    같은 선박이 여러 MBL / 여러 팀에서 참조되더라도 이 테이블에는 1 행만 존재.

    Lookup 키 우선순위 (Service 레벨):
      1. IMO Number (평생 불변) ← 가장 정확
      2. MMSI (장비 ID, 드물게 변경)
      3. Vessel Name + Flag (동명 선박 대비)
    """

    __tablename__ = "vessels"
    __table_args__ = (
        # MMSI / IMO 는 같은 선박에 대해 유일. NULL 허용이지만 값이 있으면
        # 중복 방지 (SQLite / PostgreSQL / MySQL 모두 NULL 은 unique 에 포함
        # 시키지 않음).
        UniqueConstraint("mmsi", name="uq_vessels_mmsi"),
        UniqueConstraint("imo_number", name="uq_vessels_imo_number"),
    )

    # --- 식별자 ---
    # MMSI: 9자리. ITU 가 발급. AIS 방송에 포함되는 유일 ID. 위치 추적에 필수.
    # 문자열로 저장하는 이유: 일부 업체가 "leading zero" 를 의미 있게 보냄
    # (실제로는 정수지만 표준화 위해 문자열 유지).
    mmsi: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)
    # IMO Number: 7자리. 선박 평생 불변. 선주 / 국기 바뀌어도 그대로.
    imo_number: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)

    # --- 이름 / 국가 ---
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # ISO 2-letter country code. 일부 응답은 풀네임을 주기도 하지만 2자리로 통일.
    flag: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    call_sign: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # --- 스펙 (선택적 — AIS search 에서 받으면 채움) ---
    length_m: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    breadth_m: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gross_tonnage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # AIS / ITU 분류 코드 (숫자). 우리 UI 에서는 일반 카테고리로 매핑해서 표시.
    # 70~79: Cargo, 80~89: Tanker, 60~69: Passenger 등.
    vessel_type_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    year_built: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # --- 마지막 AIS 업체 조회 시각 ---
    # resolve_vessel 태스크가 이 필드를 갱신한다. 너무 오래된 row 는 다시 조회
    # (스펙 변경, MMSI 업데이트 반영).
    last_resolved_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 1:1 최신 위치. selectin 으로 자동 로드.
    position: Mapped[Optional["VesselPositionModel"]] = relationship(
        "VesselPositionModel",
        back_populates="vessel",
        uselist=False,
        cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT,
    )


class VesselPositionModel(Base):
    """선박별 최신 위치 (1 vessel = 1 row).

    `poll_fleet_positions` 태스크가 주기적으로 UPDATE 한다.
    히스토리 (항적) 는 여기 쌓지 않는다 — 필요 시 별도 테이블 추가.

    ⚠️ 'Base.is_active' 는 사실상 안 씀 (위치는 soft-delete 대상 아님).
    하지만 Base 공통 필드를 상속하는 관례 유지.
    """

    __tablename__ = "vessel_positions"
    __table_args__ = (
        # 선박당 최신 위치 1행만 허용.
        UniqueConstraint("vessel_id", name="uq_vessel_positions_vessel_id"),
    )

    vessel_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vessels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- 위치 ---
    # DECIMAL(10, 6) — 위경도는 소수점 6자리 = 약 0.11 m 정밀도. 넉넉하다.
    # 범위: 위도 ±90, 경도 ±180.
    latitude: Mapped[Decimal] = mapped_column(DECIMAL(10, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(DECIMAL(10, 6), nullable=False)

    # --- 운항 정보 ---
    # 속도 (knots) — DECIMAL 로 0.1 kn 해상도.
    speed_knots: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2), nullable=True)
    # 진행 방향 (0~359.9°) — Leaflet 마커 회전에 사용.
    heading_degrees: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2), nullable=True)

    # AIS 항해 상태 (0: Under way, 1: At anchor, 5: Moored, ...)
    # 문자열 열거형으로 저장하면 UI 가 읽기 편하다 — "underway" / "anchored" /
    # "moored" / "aground" / "not-under-command" / "unknown"
    navigation_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # AIS 원본이 기록한 시각 (선박이 방송한 시간). 우리 DB 에 도착한 시간과
    # 구분하기 위해 별도 컬럼.
    reported_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    vessel: Mapped[VesselModel] = relationship(
        VesselModel,
        back_populates="position",
        lazy=settings.ORM_LAZY_DEFAULT,
    )
