# src/invoice/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from invoice.model import InvoiceModel, InvoiceLineModel
from invoice.const.status import InvoiceStatus
from invoice.schemas.request import PaginateInvoiceRequest


class InvoiceRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    # ── 헤더 ────────────────────────────────────────────────────
    async def create(self, payload: dict, actor_user_id: int | None = None) -> InvoiceModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = InvoiceModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, invoice_id: int) -> Optional[InvoiceModel]:
        q = select(InvoiceModel).where(
            InvoiceModel.team_id == self._require_team(),
            InvoiceModel.id == invoice_id,
            InvoiceModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_with_lines(self, invoice_id: int) -> Optional[InvoiceModel]:
        q = (
            select(InvoiceModel)
            .where(
                InvoiceModel.team_id == self._require_team(),
                InvoiceModel.id == invoice_id,
                InvoiceModel.is_active.is_(True),
            )
            .options(selectinload(InvoiceModel.lines))
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_paginated(self, request: PaginateInvoiceRequest):
        team_id = self._require_team()
        base = [InvoiceModel.team_id == team_id]
        if not request.include_inactive:
            base.append(InvoiceModel.is_active.is_(True))
        return await self._common_service.paginate(
            request=request, model=InvoiceModel, session=self.db,
            base_query=select(InvoiceModel).where(*base),
        )

    async def set_status(self, row: InvoiceModel, status: InvoiceStatus, actor_user_id: int | None = None) -> None:
        row.status = status
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()

    async def update_charge_total(self, row: InvoiceModel) -> None:
        total = (await self.db.execute(select(func.coalesce(func.sum(InvoiceLineModel.amount), 0)).where(
            InvoiceLineModel.team_id == self._require_team(), InvoiceLineModel.invoice_id == row.id,
        ))).scalar_one()
        row.charge_total = total
        await self.db.flush()

    async def soft_deactivate_by_id(self, invoice_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(update(InvoiceModel).where(
            InvoiceModel.team_id == self._require_team(),
            InvoiceModel.id == invoice_id,
            InvoiceModel.is_active.is_(True),
        ).values(**values))
        await self.db.flush()

    async def sync_delta(self, since):
        team_id = self._require_team()
        base_query = select(InvoiceModel).where(InvoiceModel.team_id == team_id)
        return await self._common_service.sync_delta(
            model=InvoiceModel, session=self.db, since=since,
            team_id=team_id, base_query=base_query, use_soft_delete=True,
        )

    # ── 라인 ────────────────────────────────────────────────────
    async def add_line(self, invoice_id: int, data: dict, actor_user_id: int | None = None) -> InvoiceLineModel:
        row = InvoiceLineModel(team_id=self._require_team(), invoice_id=invoice_id,
                               created_by_user_id=actor_user_id, **data)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get_line(self, invoice_id: int, line_id: int) -> Optional[InvoiceLineModel]:
        q = select(InvoiceLineModel).where(
            InvoiceLineModel.team_id == self._require_team(),
            InvoiceLineModel.invoice_id == invoice_id,
            InvoiceLineModel.id == line_id,
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def list_lines(self, invoice_id: int) -> List[InvoiceLineModel]:
        q = select(InvoiceLineModel).where(
            InvoiceLineModel.team_id == self._require_team(),
            InvoiceLineModel.invoice_id == invoice_id,
        ).order_by(InvoiceLineModel.id.asc())
        return list((await self.db.execute(q)).scalars().all())

    async def delete_line(self, line: InvoiceLineModel) -> None:
        await self.db.delete(line)
        await self.db.flush()
