"""Vessel 도메인 비즈니스 로직.

Service 는 두 가지 진입점을 제공:
  1. `resolve_by_name` — 선박 이름을 AIS provider 로 조회해서 DB 에 캐싱
     (호출자는 ocean scraping pipeline / Celery task)
  2. `refresh_positions` — 특정 MMSI 배치에 대해 최신 위치 가져와서 UPSERT
     (호출자는 poll_fleet_positions 태스크)

둘 다 실패 시 예외 raise 대신 **None 반환 / 빈 리스트 반환**. 호출자(task)
가 로그만 남기고 다음 tick 에 재시도하도록.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Sequence

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from vessel.ais.base import VesselProfile
from vessel.ais.factory import get_ais_provider
from vessel.model import VesselModel, VesselPositionModel
from vessel.repository import VesselRepository

logger = structlog.get_logger(__name__)


class VesselService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = VesselRepository(db)

    # ---------------------------------------------------------------
    # Vessel resolve (name → profile → DB cache)
    # ---------------------------------------------------------------

    async def resolve_by_name(
        self,
        *,
        name: str,
        imo_number: Optional[str] = None,
    ) -> Optional[VesselModel]:
        """AIS provider 에게 프로필 조회 후 DB 에 저장/병합 후 반환.

        이미 DB 에 동일 이름/IMO 가 있으면 provider 호출 건너뛰고 기존 반환
        (비용 절감). 단, `last_resolved_at` 이 너무 오래됐으면 re-fetch 하는
        정책을 추가해도 됨 (선박 이름 변경/매각 반영).

        None 반환 조건:
          - 이름이 비었거나
          - provider 가 None 반환 (못 찾음)
          - provider 호출 실패 (예외는 여기서 삼키고 로그만)
        """
        normalized = (name or "").strip()
        if not normalized:
            return None

        # 1) 로컬 캐시 히트 체크 — IMO > name 순
        if imo_number:
            cached = await self.repo.get_by_imo(imo_number)
            if cached is not None:
                return cached
        cached = await self.repo.get_by_name(normalized)
        if cached is not None and cached.mmsi:
            # MMSI 까지 채워진 완전한 캐시 — provider 호출 스킵.
            return cached

        # 2) Provider 호출
        provider = get_ais_provider()
        try:
            profile: Optional[VesselProfile] = await provider.search_vessel_by_name(
                normalized, imo_number=imo_number
            )
        except Exception:
            logger.exception(
                "vessel_resolve_failed", name=normalized, imo=imo_number
            )
            return None

        if profile is None:
            logger.info("vessel_not_found_in_ais", name=normalized)
            return cached  # provider 가 못 찾았어도 최소한 name-only row 는 반환

        # 3) DB upsert
        return await self.repo.create_or_update_profile(
            name=profile.name,
            mmsi=profile.mmsi,
            imo_number=profile.imo_number,
            flag=profile.flag,
            call_sign=profile.call_sign,
            length_m=profile.length_m,
            breadth_m=profile.breadth_m,
            gross_tonnage=profile.gross_tonnage,
            vessel_type_code=profile.vessel_type_code,
            year_built=profile.year_built,
            owner=profile.owner,
        )

    # ---------------------------------------------------------------
    # Position batch refresh
    # ---------------------------------------------------------------

    async def refresh_positions(
        self, mmsis: Sequence[str]
    ) -> list[VesselPositionModel]:
        """AIS 업체에 위치 배치 조회 후 vessel_positions 에 upsert.

        반환: 실제 UPDATE/INSERT 된 row 리스트. task 에서 이 리스트를 받아
        해당 vessel 을 추적 중인 팀에 WebSocket 이벤트 push.

        실패 케이스:
          - provider 예외 → 빈 리스트 (다음 tick 에 재시도 되게)
          - 일부 MMSI 결과 없음 → 그 부분만 누락, 나머지는 처리
        """
        if not mmsis:
            return []

        provider = get_ais_provider()
        try:
            reports = await provider.get_positions(list(mmsis))
        except Exception:
            logger.exception("vessel_positions_fetch_failed", count=len(mmsis))
            return []

        if not reports:
            return []

        # MMSI → vessel_id 매핑 (한 번 조회)
        vessels_by_mmsi: dict[str, VesselModel] = {}
        for report in reports:
            if report.mmsi in vessels_by_mmsi:
                continue
            v = await self.repo.get_by_mmsi(report.mmsi)
            if v is not None:
                vessels_by_mmsi[report.mmsi] = v

        updated: list[VesselPositionModel] = []
        for report in reports:
            vessel = vessels_by_mmsi.get(report.mmsi)
            if vessel is None:
                # MMSI 가 우리 DB 에 없는 선박 — 일반적으로는 있을 리 없지만
                # provider 가 엉뚱한 MMSI 를 섞어 보낼 수도 있어서 방어.
                continue
            row = await self.repo.upsert_position(
                vessel_id=vessel.id,
                latitude=Decimal(str(report.latitude)),
                longitude=Decimal(str(report.longitude)),
                speed_knots=(
                    Decimal(str(report.speed_knots))
                    if report.speed_knots is not None
                    else None
                ),
                heading_degrees=(
                    Decimal(str(report.heading_degrees))
                    if report.heading_degrees is not None
                    else None
                ),
                navigation_status=report.navigation_status,
                reported_at=report.reported_at,
            )
            updated.append(row)

        return updated
