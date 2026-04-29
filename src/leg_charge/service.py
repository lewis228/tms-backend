# src/leg_charge/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from leg_charge.repository import LegChargeRepository
from leg_charge.auto_match import auto_match_for_leg
from leg_charge.schemas.request import (
    LegChargeCreateRequest, LegChargeUpdateRequest,
    PaginateLegChargeRequest, LegChargeBulkDeleteRequest,
)
from leg_charge.schemas.response import (
    LegChargeResponseSchema, LegChargeDeleteResponseSchema,
    LegChargeBulkDeleteResponseSchema, BulkDeleteResultItem, BulkSummary,
)


class LegChargeService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = LegChargeRepository(db, team_id)

    async def auto_match(
        self, leg_id: int, actor_user_id: int | None = None,
    ) -> list[LegChargeResponseSchema]:
        rows = await auto_match_for_leg(self.db, self.team_id, leg_id, actor_user_id)
        return [LegChargeResponseSchema.model_validate(r) for r in rows]

    async def create(
        self, payload: LegChargeCreateRequest, actor_user_id: int | None = None,
    ) -> LegChargeResponseSchema:
        # v3 Snapshot: snapshot_unit_amount × quantity = amount.
        # 미입력 시 ChargeCode.default_amount 로 자동 채움 + amount 자동 계산.
        from sqlalchemy import select
        from charge_code.model import ChargeCodeModel
        from decimal import Decimal as _D

        data = payload.model_dump()
        if data.get("snapshot_unit_amount") is None:
            cc = (await self.db.execute(
                select(ChargeCodeModel).where(
                    ChargeCodeModel.team_id == self.team_id,
                    ChargeCodeModel.id == data["charge_code_id"],
                )
            )).scalar_one_or_none()
            if cc and cc.default_amount is not None:
                data["snapshot_unit_amount"] = cc.default_amount
            # payee 기본값 채우기
            if cc and data.get("payee_kind") is None and cc.payee_default is not None:
                data["payee_kind"] = cc.payee_default
        if data.get("quantity") is None:
            data["quantity"] = _D("1")
        if data.get("amount") is None and data.get("snapshot_unit_amount") is not None:
            data["amount"] = _D(str(data["snapshot_unit_amount"])) * _D(str(data["quantity"]))
        elif data.get("amount") is None:
            data["amount"] = _D("0")

        row = await self.repo.create(data, actor_user_id=actor_user_id)
        from realtime.v3_publish import safe_publish, EVT_LEG_CHARGE_CREATED
        await safe_publish(
            type=EVT_LEG_CHARGE_CREATED, team_id=self.team_id, actor_id=actor_user_id,
            payload={"charge_id": row.id, "leg_id": row.leg_id, "amount": str(row.amount)},
        )
        return LegChargeResponseSchema.model_validate(row)

    async def get(self, id_: int) -> LegChargeResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Leg Charge")
        return LegChargeResponseSchema.model_validate(row)

    async def list_by_leg(self, leg_id: int) -> List[LegChargeResponseSchema]:
        rows = await self.repo.list_by_leg(leg_id)
        return [LegChargeResponseSchema.model_validate(r) for r in rows]

    async def list_paginated(
        self, request: PaginateLegChargeRequest,
    ) -> CursorPaginationResult[LegChargeResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [LegChargeResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(
        self, id_: int, payload: LegChargeUpdateRequest,
        actor_user_id: int | None = None,
    ) -> LegChargeResponseSchema:
        from decimal import Decimal as _D
        data = payload.model_dump(exclude_unset=True)
        # v3: quantity 또는 snapshot_unit_amount 가 변경되고 amount 가 명시 X 면 재계산.
        if ("quantity" in data or "snapshot_unit_amount" in data) and "amount" not in data:
            existing = await self.repo.get(id_)
            if existing is not None:
                qty = data.get("quantity", existing.quantity) or _D("1")
                unit = data.get("snapshot_unit_amount", existing.snapshot_unit_amount)
                if unit is not None:
                    data["amount"] = _D(str(unit)) * _D(str(qty))
        row = await self.repo.update(id_, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("Leg Charge")
        from realtime.v3_publish import safe_publish, EVT_LEG_CHARGE_UPDATED
        await safe_publish(
            type=EVT_LEG_CHARGE_UPDATED, team_id=self.team_id, actor_id=actor_user_id,
            payload={"charge_id": row.id, "leg_id": row.leg_id, "amount": str(row.amount)},
        )
        return LegChargeResponseSchema.model_validate(row)

    async def delete(
        self, id_: int, actor_user_id: int | None = None,
    ) -> LegChargeDeleteResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Leg Charge")
        leg_id = row.leg_id
        await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
        from realtime.v3_publish import safe_publish, EVT_LEG_CHARGE_DELETED
        await safe_publish(
            type=EVT_LEG_CHARGE_DELETED, team_id=self.team_id, actor_id=actor_user_id,
            payload={"charge_id": id_, "leg_id": leg_id},
        )
        return LegChargeDeleteResponseSchema(id=id_, deleted=True, soft_deleted=True)

    async def delete_bulk(
        self, payload: LegChargeBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> LegChargeBulkDeleteResponseSchema:
        existing = await self.repo.get_many(payload.ids)
        existing_ids = {r.id for r in existing}
        missing = set(payload.ids) - existing_ids
        if missing:
            raise NotFoundException(
                f"Leg Charge(ID={list(missing)})", detail={"missing_ids": list(missing)},
            )
        results: List[BulkDeleteResultItem] = []
        for id_ in payload.ids:
            await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
            results.append(BulkDeleteResultItem(id=id_, success=True, soft_deleted=True))
        return LegChargeBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.ids), succeeded=len(results), failed=0),
        )
