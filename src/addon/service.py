# src/addon/service.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, ConflictException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from addon.repository import AddonRepository
from addon.const.status import AddonCategory, AddonUnit
from addon.schemas.request import (
    AddonCreateRequest, AddonUpdateRequest, PaginateAddonRequest,
)
from addon.schemas.response import (
    AddonResponseSchema, AddonDeleteResponseSchema, AddonSeedResultSchema,
)

_LABEL = "Addon"

# 시스템 기본 부가요금 타입 (code, name, category, unit, amount, percent)
_SEED = [
    ("NGT", "Night Gate", AddonCategory.NIGHT_GATE, AddonUnit.FLAT, None, None),
    ("PPS", "Pier Pass", AddonCategory.PIER_PASS, AddonUnit.FLAT, Decimal("35"), None),
    ("PREPULL", "Pre-pull", AddonCategory.PREPULL, AddonUnit.FLAT, None, None),
    ("LFT", "Lift", AddonCategory.LIFT, AddonUnit.FLAT, None, None),
    ("STP", "Stop Off", AddonCategory.EXTRA_STOP, AddonUnit.FLAT, None, None),
    ("DRY", "Dry Run", AddonCategory.DRY_RUN, AddonUnit.FLAT, None, None),
    ("FUEL", "Fuel Surcharge", AddonCategory.FUEL, AddonUnit.PERCENT, None, Decimal("0.20")),
    ("DET", "Detention", AddonCategory.WAITING, AddonUnit.DAY, None, None),
    ("DMR", "Demurrage", AddonCategory.PENALTY, AddonUnit.DAY, None, None),
    ("HZM", "Hazmat", AddonCategory.HAZMAT, AddonUnit.FLAT, None, None),
    ("RFR", "Reefer", AddonCategory.REEFER, AddonUnit.FLAT, None, None),
    ("CHS", "Chassis Split", AddonCategory.CHASSIS_SPLIT, AddonUnit.FLAT, None, None),
]


class AddonService:
    """부가요금 규칙 마스터 + find_for_code (정산 snapshot 시 사용)."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = AddonRepository(db, team_id)

    async def create(self, payload: AddonCreateRequest, actor_user_id: int | None = None) -> AddonResponseSchema:
        dup = await self.repo.find_for_code(payload.code, payload.driver_id)
        if dup is not None and dup.driver_id == payload.driver_id:
            raise ConflictException(f"이미 존재하는 부가요금 코드: {payload.code} (driver={payload.driver_id})")
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return AddonResponseSchema.model_validate(row)

    async def get(self, acc_id: int) -> AddonResponseSchema:
        row = await self.repo.get(acc_id)
        if not row:
            raise NotFoundException(_LABEL)
        return AddonResponseSchema.model_validate(row)

    async def get_for_code(self, code: str, driver_id: int | None = None) -> AddonResponseSchema | None:
        row = await self.repo.find_for_code(code, driver_id)
        return AddonResponseSchema.model_validate(row) if row else None

    async def list_paginated(self, request: PaginateAddonRequest) -> CursorPaginationResult[AddonResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [AddonResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(self, acc_id: int, payload: AddonUpdateRequest, actor_user_id: int | None = None) -> AddonResponseSchema:
        row = await self.repo.update(acc_id, payload.model_dump(exclude_unset=True), actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException(_LABEL)
        return AddonResponseSchema.model_validate(row)

    async def delete(self, acc_id: int, actor_user_id: int | None = None) -> AddonDeleteResponseSchema:
        row = await self.repo.get(acc_id)
        if not row:
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_by_id(acc_id, actor_user_id=actor_user_id)
        return AddonDeleteResponseSchema(id=acc_id, deleted=True, soft_deleted=True)

    async def seed_defaults(self, actor_user_id: int | None = None) -> AddonSeedResultSchema:
        """시스템 기본 부가요금 타입 시드(이미 있는 code 는 건너뜀, 팀 전역=driver_id NULL)."""
        created = skipped = 0
        for code, name, cat, unit, amount, percent in _SEED:
            if await self.repo.find_for_code(code, None) is not None:
                skipped += 1
                continue
            await self.repo.create({
                "code": code, "name": name, "category": cat, "unit": unit,
                "amount": amount, "percent": percent, "auto_apply": code == "FUEL",
                "is_system": True, "is_billable_to_customer": True, "is_payable_to_driver": True,
            }, actor_user_id=actor_user_id)
            created += 1
        return AddonSeedResultSchema(created=created, skipped=skipped)

    async def sync_delta(self, since_str: str):
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)
        result.items = [AddonResponseSchema.model_validate(r) for r in result.items]
        return result
