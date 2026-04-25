"""Vessel / VesselPosition 데이터 접근.

Team-scoped mixin 쓰지 않는다 — 이 테이블들은 전역 마스터. 팀 격리는
`ocean_shipments.vessel_id` join 쪽에서 일어난다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vessel.model import VesselModel, VesselPositionModel


class VesselRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------------------------------------------------------
    # Vessel lookup (resolve 단계)
    # ---------------------------------------------------------------

    async def get_by_mmsi(self, mmsi: str) -> Optional[VesselModel]:
        stmt = select(VesselModel).where(VesselModel.mmsi == mmsi)
        return await self.db.scalar(stmt)

    async def get_by_imo(self, imo_number: str) -> Optional[VesselModel]:
        stmt = select(VesselModel).where(VesselModel.imo_number == imo_number)
        return await self.db.scalar(stmt)

    async def get_by_name(self, name: str) -> Optional[VesselModel]:
        """이름 정확 매칭으로 첫 번째 선박 반환.

        ⚠️ 동명 선박이 있을 수 있으나 현 단계에서는 첫 매칭만 사용한다.
        실제 운영에서 오매칭이 빈번하면 (flag, imo_number) 보조 식별자를
        받아서 좁혀야 한다.
        """
        stmt = (
            select(VesselModel)
            .where(VesselModel.name == name)
            .order_by(VesselModel.id.asc())
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def list_active_mmsis(self, limit: int = 1000) -> list[str]:
        """위치 폴링 대상 선박들의 MMSI 목록.

        `vessels.mmsi IS NOT NULL` + `is_active=True` 한 row 들. 실제로는
        "추적 중인 shipment 가 붙어 있는 선박만" 으로 좁히는 게 효율적이지만
        그러려면 ocean_shipments 조인 + status 필터가 필요하다. 지금은 단순히
        MMSI 가 있는 모든 vessel 을 대상으로 한다.

        TODO (cost-aware):
            JOIN ocean_shipments os ON os.vessel_id = vessels.id
            WHERE os.status IN ('pending','tracking','awaiting_manifest')
            GROUP BY vessels.id
        """
        stmt = (
            select(VesselModel.mmsi)
            .where(
                VesselModel.is_active.is_(True),
                VesselModel.mmsi.is_not(None),
            )
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        return [r[0] for r in rows]

    # ---------------------------------------------------------------
    # Vessel upsert
    # ---------------------------------------------------------------

    async def create_or_update_profile(
        self,
        *,
        name: str,
        mmsi: Optional[str],
        imo_number: Optional[str],
        flag: Optional[str] = None,
        call_sign: Optional[str] = None,
        length_m: Optional[int] = None,
        breadth_m: Optional[int] = None,
        gross_tonnage: Optional[int] = None,
        vessel_type_code: Optional[int] = None,
        year_built: Optional[int] = None,
        owner: Optional[str] = None,
    ) -> VesselModel:
        """프로필 upsert — IMO/MMSI 키로 매칭, 없으면 이름으로, 없으면 INSERT.

        기존 행이 있으면 새 값으로 "비어있던 필드만" 채우는 병합 전략.
        (provider 가 일부 필드만 주는 경우 기존 값을 날리지 않게.)
        """
        existing: Optional[VesselModel] = None
        if imo_number:
            existing = await self.get_by_imo(imo_number)
        if existing is None and mmsi:
            existing = await self.get_by_mmsi(mmsi)
        if existing is None:
            existing = await self.get_by_name(name)

        if existing is None:
            existing = VesselModel(
                name=name,
                mmsi=mmsi,
                imo_number=imo_number,
                flag=flag,
                call_sign=call_sign,
                length_m=length_m,
                breadth_m=breadth_m,
                gross_tonnage=gross_tonnage,
                vessel_type_code=vessel_type_code,
                year_built=year_built,
                owner=owner,
                last_resolved_at=datetime.now(timezone.utc),
            )
            self.db.add(existing)
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        # 병합: 들어온 값 중 기존이 NULL 이었던 것만 채움.
        if mmsi and not existing.mmsi:
            existing.mmsi = mmsi
        if imo_number and not existing.imo_number:
            existing.imo_number = imo_number
        if name and not existing.name:
            existing.name = name
        if flag and not existing.flag:
            existing.flag = flag
        if call_sign and not existing.call_sign:
            existing.call_sign = call_sign
        if length_m and not existing.length_m:
            existing.length_m = length_m
        if breadth_m and not existing.breadth_m:
            existing.breadth_m = breadth_m
        if gross_tonnage and not existing.gross_tonnage:
            existing.gross_tonnage = gross_tonnage
        if vessel_type_code and not existing.vessel_type_code:
            existing.vessel_type_code = vessel_type_code
        if year_built and not existing.year_built:
            existing.year_built = year_built
        if owner and not existing.owner:
            existing.owner = owner
        existing.last_resolved_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(existing)
        return existing

    # ---------------------------------------------------------------
    # VesselPosition upsert
    # ---------------------------------------------------------------

    async def upsert_position(
        self,
        *,
        vessel_id: int,
        latitude: Decimal,
        longitude: Decimal,
        speed_knots: Optional[Decimal],
        heading_degrees: Optional[Decimal],
        navigation_status: Optional[str],
        reported_at: Optional[datetime],
    ) -> VesselPositionModel:
        """선박별 1행 유지하면서 위치 UPDATE 또는 INSERT."""
        existing = await self.db.scalar(
            select(VesselPositionModel).where(
                VesselPositionModel.vessel_id == vessel_id
            )
        )
        if existing is None:
            row = VesselPositionModel(
                vessel_id=vessel_id,
                latitude=latitude,
                longitude=longitude,
                speed_knots=speed_knots,
                heading_degrees=heading_degrees,
                navigation_status=navigation_status,
                reported_at=reported_at,
            )
            self.db.add(row)
            await self.db.flush()
            await self.db.refresh(row)
            return row

        existing.latitude = latitude
        existing.longitude = longitude
        existing.speed_knots = speed_knots
        existing.heading_degrees = heading_degrees
        existing.navigation_status = navigation_status
        existing.reported_at = reported_at
        await self.db.flush()
        await self.db.refresh(existing)
        return existing

    # ---------------------------------------------------------------
    # 팀 관점 조회 (ocean_shipments 조인)
    # ---------------------------------------------------------------

    async def list_vessels_for_team(
        self, team_id: int, *, limit: int = 500
    ) -> Sequence[VesselModel]:
        """특정 팀이 "추적 중인 shipment" 로 연결된 vessel 을 중복 없이 반환.

        TODO: ocean_shipments 의 vessel_id FK 가 추가된 뒤 아래 쿼리 활성화.
        현재는 `vessels` 전체를 반환하는 임시 구현이라 실사용 시 반드시
        join 기반으로 교체. (크로스 팀 노출 방지)

        예상 쿼리 (vessel_id 필드 추가 후):
            SELECT v.* FROM vessels v
            JOIN ocean_shipments s ON s.vessel_id = v.id
            WHERE s.team_id = :team_id
              AND s.is_active = TRUE
              AND s.status IN ('pending','tracking','awaiting_manifest')
            GROUP BY v.id
            LIMIT :limit
        """
        stmt = (
            select(VesselModel)
            .where(VesselModel.is_active.is_(True))
            .options(selectinload(VesselModel.position))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
