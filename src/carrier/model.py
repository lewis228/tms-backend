from __future__ import annotations
from typing import Any, Optional
from sqlalchemy import JSON, Boolean, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column
from common.model.base_model import Base


class CarrierModel(Base):
    """해상 운송사(선사) 마스터 카탈로그.

    전역(global) 테이블 — ``TeamScopedMixin`` 을 상속하지 않는다.
    선사는 업계 공통 개념이므로 팀별로 다른 선사 목록을 가질 이유가 없다.
    Shipment 는 ``carrier_id`` FK 로 이 테이블을 참조한다.

    SCAC(Standard Carrier Alpha Code)는 업계 표준 4자리 식별자이며
    MBL 번호의 prefix 와 거의 일치한다. ``mbl_prefixes`` 에는 "이 SCAC 이
    아니지만 같은 선사의 MBL 에 쓰이는 prefix 목록" 을 담아 자동 감지 정확도를
    높인다 (예: Yang Ming 은 YMLU / YMJA 둘 다).

    ``scraper_key`` 는 ``backend_scraping`` 쪽 스크래퍼 모듈 식별자 (예:
    ``"maersk"``, ``"smline"``). NULL 이면 아직 스크래퍼가 없는 선사로, 등록은
    허용하되 자동 추적은 실패 처리.
    """

    __tablename__ = "carriers"

    # SCAC — 4자 대문자. 업계 표준 유니크 식별자. MBL prefix 의 기본값이기도 함.
    scac: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    # 표시용 이름 (UI dropdown, shipment 상세).
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # MBL 자동 감지용 prefix 리스트. 대개 SCAC 과 동일하지만 별칭/합병사
    # 이력 등으로 여러 개 필요할 수 있음. 예: ["YMLU", "YMJA"].
    mbl_prefixes: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    # 스크래퍼 모듈 식별자 (backend_scraping/src/ocean/scrapers/carriers/{scraper_key}.py 와 매칭).
    # NULL 이면 등록은 가능하지만 자동 스크래핑은 skip.
    scraper_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # 선사 공식 tracking 페이지 딥링크 템플릿 (예: "https://.../{mbl}").
    tracking_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # 로고 이미지 URL (향후 CDN / MinIO 경로).
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # 대형 선사(ALLIANCE_MAJOR) 가 UI 상단에 오게 하는 정렬 용도. 낮을수록 위.
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1000, server_default="1000",
    )
    # 선사 폐업/통합 등으로 추적 불가해진 경우 false. 피커에서 숨김.
    is_supported: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1",
    )

    __table_args__ = (
        Index("ix_carriers_scac", "scac"),
        Index("ix_carriers_scraper_key", "scraper_key"),
        Index("ix_carriers_display_order", "display_order"),
    )
