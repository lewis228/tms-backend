# src/invoice/service.py
"""고객 인보이스 서비스 (재설계 2c) — cost-plus(원가 프리필 + 수동 마크업)."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, ConflictException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from container.model import ContainerModel
from invoice.repository import InvoiceRepository
from invoice.cost import compute_do_cost
from invoice.const.status import InvoiceStatus, InvoiceLineSource
from invoice.state_machine import assert_can_transition
from invoice.schemas.request import (
    InvoiceCreateRequest, InvoiceUpdateRequest,
    InvoiceLineCreateRequest, InvoiceLineUpdateRequest, PaginateInvoiceRequest,
)
from invoice.schemas.response import (
    InvoiceSummarySchema, InvoiceDetailSchema, InvoiceLineResponseSchema,
    InvoiceDeleteResponseSchema,
)

_LABEL = "Invoice"


class InvoiceService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = InvoiceRepository(db, team_id)

    # ── 생성 (옵션: D/O 원가 라인 프리필) ──────────────────────
    async def create(self, body: InvoiceCreateRequest, actor_user_id: int | None = None) -> InvoiceDetailSchema:
        header = await self.repo.create({
            "customer_id": body.customer_id,
            "delivery_order_id": body.delivery_order_id,
            "invoice_number": body.invoice_number,
            "issue_date": body.issue_date,
            "due_date": body.due_date,
            "note": body.note,
            "status": InvoiceStatus.DRAFT,
        }, actor_user_id=actor_user_id)

        if body.delivery_order_id is not None and body.prefill_from_do:
            await self._prefill_from_do(header.id, body.delivery_order_id, actor_user_id=actor_user_id)
        return await self._to_detail(header.id)

    async def _prefill_from_do(self, invoice_id: int, do_id: int, actor_user_id: int | None = None) -> None:
        """D/O 컨테이너별 기사 원가로 청구 라인 프리필(시작값) + cost_total 동결."""
        total, by_container = await compute_do_cost(self.db, self.team_id, do_id)
        # 컨테이너 메타(번호) — 라인 설명용
        containers = list((await self.db.execute(select(ContainerModel).where(
            ContainerModel.team_id == self.team_id,
            ContainerModel.delivery_order_id == do_id,
            ContainerModel.is_active.is_(True),
        ).order_by(ContainerModel.sequence_no.asc()))).scalars().all())

        for c in containers:
            cost = by_container.get(c.id, Decimal("0"))
            label = c.container_number or f"Container #{c.sequence_no}"
            await self.repo.add_line(invoice_id, {
                "container_id": c.id,
                "description": f"Drayage - {label}",
                "quantity": Decimal("1"),
                "unit_amount": cost,
                "amount": cost,
                "source": InvoiceLineSource.PREFILL,
                "cost_amount": cost,
            }, actor_user_id=actor_user_id)

        header = await self.repo.get(invoice_id)
        header.cost_total = total
        await self.repo.update_charge_total(header)

    async def recompute_cost(self, invoice_id: int, actor_user_id: int | None = None) -> InvoiceDetailSchema:
        """원가만 D/O 기준 재계산 (DRAFT). 라인은 건드리지 않음."""
        header = await self.repo.get(invoice_id)
        if not header:
            raise NotFoundException(_LABEL)
        self._assert_draft(header)
        if header.delivery_order_id is None:
            raise ConflictException("D/O 연결이 없어 원가를 계산할 수 없습니다.")
        total, _ = await compute_do_cost(self.db, self.team_id, header.delivery_order_id)
        header.cost_total = total
        if actor_user_id is not None:
            header.updated_by_user_id = actor_user_id
        await self.db.flush()
        return await self._to_detail(invoice_id)

    # ── Read ────────────────────────────────────────────────────
    async def get(self, invoice_id: int) -> InvoiceDetailSchema:
        if not await self.repo.get(invoice_id):
            raise NotFoundException(_LABEL)
        return await self._to_detail(invoice_id)

    async def _to_detail(self, invoice_id: int) -> InvoiceDetailSchema:
        header = await self.repo.get_with_lines(invoice_id)
        if not header:
            raise NotFoundException(_LABEL)
        detail = InvoiceDetailSchema(**InvoiceSummarySchema.model_validate(header).model_dump())
        detail.lines = [InvoiceLineResponseSchema.model_validate(l) for l in header.lines]
        return detail

    async def list_paginated(self, request: PaginateInvoiceRequest) -> CursorPaginationResult[InvoiceSummarySchema]:
        result = await self.repo.get_paginated(request)
        result.data = [InvoiceSummarySchema.model_validate(r) for r in result.data]
        return result

    async def sync_delta(self, since_str: str):
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)
        result.items = [InvoiceSummarySchema.model_validate(r) for r in result.items]
        return result

    # ── 헤더 수정 ───────────────────────────────────────────────
    async def update(self, invoice_id: int, body: InvoiceUpdateRequest, actor_user_id: int | None = None) -> InvoiceDetailSchema:
        header = await self.repo.get(invoice_id)
        if not header:
            raise NotFoundException(_LABEL)
        self._assert_draft(header)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(header, k, v)
        if actor_user_id is not None:
            header.updated_by_user_id = actor_user_id
        await self.db.flush()
        return await self._to_detail(invoice_id)

    # ── 라인 ────────────────────────────────────────────────────
    async def add_line(self, invoice_id: int, body: InvoiceLineCreateRequest, actor_user_id: int | None = None) -> InvoiceDetailSchema:
        header = await self.repo.get(invoice_id)
        if not header:
            raise NotFoundException(_LABEL)
        self._assert_draft(header)
        amount = (body.quantity or Decimal("1")) * (body.unit_amount or Decimal("0"))
        await self.repo.add_line(invoice_id, {
            "container_id": body.container_id,
            "description": body.description,
            "quantity": body.quantity,
            "unit_amount": body.unit_amount,
            "amount": amount,
            "source": InvoiceLineSource.MANUAL,
            "note": body.note,
        }, actor_user_id=actor_user_id)
        await self.repo.update_charge_total(header)
        return await self._to_detail(invoice_id)

    async def update_line(self, invoice_id: int, line_id: int, body: InvoiceLineUpdateRequest, actor_user_id: int | None = None) -> InvoiceDetailSchema:
        header = await self.repo.get(invoice_id)
        if not header:
            raise NotFoundException(_LABEL)
        self._assert_draft(header)
        line = await self.repo.get_line(invoice_id, line_id)
        if not line:
            raise NotFoundException("Invoice line")
        data = body.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(line, k, v)
        line.amount = (line.quantity or Decimal("1")) * (line.unit_amount or Decimal("0"))
        if actor_user_id is not None:
            line.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.repo.update_charge_total(header)
        return await self._to_detail(invoice_id)

    async def delete_line(self, invoice_id: int, line_id: int, actor_user_id: int | None = None) -> InvoiceDetailSchema:
        header = await self.repo.get(invoice_id)
        if not header:
            raise NotFoundException(_LABEL)
        self._assert_draft(header)
        line = await self.repo.get_line(invoice_id, line_id)
        if not line:
            raise NotFoundException("Invoice line")
        await self.repo.delete_line(line)
        await self.repo.update_charge_total(header)
        return await self._to_detail(invoice_id)

    # ── 상태 전이 ───────────────────────────────────────────────
    async def transition(self, invoice_id: int, target: InvoiceStatus, actor_user_id: int | None = None) -> InvoiceDetailSchema:
        header = await self.repo.get(invoice_id)
        if not header:
            raise NotFoundException(_LABEL)
        assert_can_transition(header.status, target)
        await self.repo.set_status(header, target, actor_user_id=actor_user_id)
        return await self._to_detail(invoice_id)

    async def delete(self, invoice_id: int, actor_user_id: int | None = None) -> InvoiceDeleteResponseSchema:
        if not await self.repo.get(invoice_id):
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_by_id(invoice_id, actor_user_id=actor_user_id)
        return InvoiceDeleteResponseSchema(id=invoice_id, deleted=True, soft_deleted=True)

    # ── helper ──────────────────────────────────────────────────
    @staticmethod
    def _assert_draft(header) -> None:
        if header.status != InvoiceStatus.DRAFT:
            raise ConflictException(f"DRAFT 상태에서만 편집 가능 (현재 {header.status.value}).")
