from __future__ import annotations
from typing import List, Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from carrier.model import CarrierModel


class CarrierRepository:
    """전역 carrier 레포. 팀 스코프 무관이라 ``TeamScopedRepoMixin`` 미사용."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_carriers(
        self,
        *,
        supported_only: bool = True,
        scrapable_only: bool = False,
        search: Optional[str] = None,
    ) -> List[CarrierModel]:
        stmt = select(CarrierModel).where(CarrierModel.is_active.is_(True))
        if supported_only:
            stmt = stmt.where(CarrierModel.is_supported.is_(True))
        if scrapable_only:
            stmt = stmt.where(CarrierModel.scraper_key.is_not(None))
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    CarrierModel.name.ilike(pattern),
                    CarrierModel.scac.ilike(pattern),
                )
            )
        stmt = stmt.order_by(
            CarrierModel.display_order.asc(),
            CarrierModel.name.asc(),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, carrier_id: int) -> Optional[CarrierModel]:
        stmt = select(CarrierModel).where(
            CarrierModel.id == carrier_id,
            CarrierModel.is_active.is_(True),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_scac(self, scac: str) -> Optional[CarrierModel]:
        stmt = select(CarrierModel).where(
            CarrierModel.scac == scac.upper(),
            CarrierModel.is_active.is_(True),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_mbl_prefix(self, mbl: str) -> Optional[CarrierModel]:
        """Return the carrier whose ``mbl_prefixes`` list (or whose SCAC)
        matches the leading characters of ``mbl``. None if no match."""
        normalized = (mbl or "").strip().upper()
        if not normalized:
            return None

        # SCAC is always 4 chars in practice, but we compare by startswith
        # against a list of candidates rather than hardcoding the slice so
        # longer prefixes remain possible in the future.
        all_carriers = await self.list_carriers(supported_only=False)
        best_match: Optional[CarrierModel] = None
        best_len = 0
        for carrier in all_carriers:
            candidates = [carrier.scac]
            if isinstance(carrier.mbl_prefixes, list):
                candidates.extend(
                    [p for p in carrier.mbl_prefixes if isinstance(p, str)]
                )
            for prefix in candidates:
                if prefix and normalized.startswith(prefix.upper()):
                    if len(prefix) > best_len:
                        best_match = carrier
                        best_len = len(prefix)
        return best_match
