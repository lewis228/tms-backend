# src/dual_transaction/service.py
"""Dual Transaction 서비스 — 반납 leg + 픽업 leg 1드라이버 묶음 (Phase 4)."""
from __future__ import annotations
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, BadRequestException, ConflictException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from leg.model import LegModel
from leg.const.status import LegStatus
from dual_transaction.repository import DualTransactionRepository
from dual_transaction.const.status import DualTransactionStatus
from dual_transaction.schemas.request import (
    DualTransactionCreateRequest, DualTransactionUpdateRequest, PaginateDualTransactionRequest,
)
from dual_transaction.schemas.response import (
    DualTransactionResponseSchema, DualTransactionDeleteResponseSchema,
)

_LABEL = "Dual Transaction"


class DualTransactionService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = DualTransactionRepository(db, team_id)

    async def _get_leg(self, leg_id: int) -> LegModel:
        leg = (await self.db.execute(select(LegModel).where(
            LegModel.team_id == self.team_id, LegModel.id == leg_id,
            LegModel.is_active.is_(True),
        ))).scalar_one_or_none()
        if leg is None:
            raise NotFoundException(f"Leg {leg_id}")
        return leg

    async def create(self, body: DualTransactionCreateRequest, actor_user_id: int | None = None) -> DualTransactionResponseSchema:
        return_leg = await self._get_leg(body.return_leg_id)
        pickup_leg = await self._get_leg(body.pickup_leg_id)
        for leg in (return_leg, pickup_leg):
            if leg.status in (LegStatus.COMPLETED, LegStatus.DRY_RUN):
                raise BadRequestException(f"종료된 leg {leg.id} 는 묶을 수 없습니다.")

        row = await self.repo.create({
            "driver_id": body.driver_id,
            "truck_id": body.truck_id,
            "return_leg_id": body.return_leg_id,
            "pickup_leg_id": body.pickup_leg_id,
            "scheduled_at": body.scheduled_at,
            "note": body.note,
            "status": DualTransactionStatus.PLANNED,
        }, actor_user_id=actor_user_id)

        # 두 leg 를 동일 드라이버로 배차 (PENDING/ASSIGNED 인 경우)
        from leg.service import LegService
        leg_svc = LegService(self.db, self.team_id)
        for leg in (return_leg, pickup_leg):
            if leg.status in (LegStatus.PENDING, LegStatus.ASSIGNED):
                await leg_svc.assign_driver(
                    leg.id, body.driver_id, truck_id=body.truck_id, actor_user_id=actor_user_id,
                )
        return DualTransactionResponseSchema.model_validate(await self.repo.get(row.id))

    async def get(self, dtx_id: int) -> DualTransactionResponseSchema:
        row = await self.repo.get(dtx_id)
        if not row:
            raise NotFoundException(_LABEL)
        return DualTransactionResponseSchema.model_validate(row)

    async def list_paginated(self, request: PaginateDualTransactionRequest) -> CursorPaginationResult[DualTransactionResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [DualTransactionResponseSchema.model_validate(r) for r in result.data]
        return result

    async def sync_delta(self, since_str: str):
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)
        result.items = [DualTransactionResponseSchema.model_validate(r) for r in result.items]
        return result

    async def update(self, dtx_id: int, body: DualTransactionUpdateRequest, actor_user_id: int | None = None) -> DualTransactionResponseSchema:
        row = await self.repo.get(dtx_id)
        if not row:
            raise NotFoundException(_LABEL)
        if row.status != DualTransactionStatus.PLANNED:
            raise ConflictException("PLANNED 상태에서만 수정 가능.")
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        return DualTransactionResponseSchema.model_validate(row)

    async def complete(self, dtx_id: int, actor_user_id: int | None = None) -> DualTransactionResponseSchema:
        row = await self.repo.get(dtx_id)
        if not row:
            raise NotFoundException(_LABEL)
        if row.status != DualTransactionStatus.PLANNED:
            raise ConflictException("PLANNED 상태만 완료 처리 가능.")
        row.status = DualTransactionStatus.COMPLETED
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        return DualTransactionResponseSchema.model_validate(row)

    async def cancel(self, dtx_id: int, actor_user_id: int | None = None) -> DualTransactionResponseSchema:
        row = await self.repo.get(dtx_id)
        if not row:
            raise NotFoundException(_LABEL)
        if row.status == DualTransactionStatus.COMPLETED:
            raise ConflictException("완료된 묶음은 취소할 수 없습니다.")
        row.status = DualTransactionStatus.CANCELLED
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        return DualTransactionResponseSchema.model_validate(row)

    async def delete(self, dtx_id: int, actor_user_id: int | None = None) -> DualTransactionDeleteResponseSchema:
        if not await self.repo.get(dtx_id):
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_by_id(dtx_id, actor_user_id=actor_user_id)
        return DualTransactionDeleteResponseSchema(id=dtx_id, deleted=True, soft_deleted=True)
