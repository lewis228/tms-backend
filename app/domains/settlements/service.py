"""Settlement 서비스.

라이프사이클:
  PENDING → CALCULATED → ADJUSTED → APPROVED
                          (사유필수)  (잠금)

Approve 후 모든 금액 필드 readonly. Unapprove 는 ADMIN+ 만 (라우터에서 게이트).
모든 상태 전이는 SettlementAuditLog 1행씩 기록.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.core.exceptions import (
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.domains.settlements.models import (
    ExtraCharge,
    Settlement,
    SettlementAuditLog,
)
from app.domains.settlements.repository import SettlementRepository
from app.domains.settlements.schema import (
    ExtraChargeRequest,
    SettlementAdjustRequest,
    SettlementApproveRequest,
    SettlementCalculateRequest,
    SettlementUnapproveRequest,
)
from app.models.enums import SettlementStatus


def _snapshot(s: Settlement) -> dict[str, Any]:
    return {
        "system_total": str(s.system_total),
        "driver_reported_amount": str(s.driver_reported_amount) if s.driver_reported_amount is not None else None,
        "discrepancy": str(s.discrepancy) if s.discrepancy is not None else None,
        "has_flag": s.has_flag,
        "final_amount": str(s.final_amount) if s.final_amount is not None else None,
        "settlement_status": s.settlement_status.value,
        "is_settled": s.is_settled,
    }


class SettlementService:
    def __init__(self, repo: SettlementRepository, tenant_id: str) -> None:
        self.repo = repo
        self.tenant_id = tenant_id

    async def get(self, id_: str) -> Settlement:
        s = await self.repo.get_by_id(id_)
        if not s:
            raise NotFoundError("Settlement not found")
        return s

    async def list_paged(self, params):
        return await self.repo.list_paged(params)

    async def get_with_extras(
        self, id_: str
    ) -> tuple[Settlement, list[ExtraCharge]]:
        s = await self.get(id_)
        extras = await self.repo.list_extras(s.id)
        return s, extras

    async def list_audit_logs(self, id_: str) -> list[SettlementAuditLog]:
        await self.get(id_)
        return await self.repo.list_audit_logs(id_)

    async def calculate(
        self,
        id_: str,
        payload: SettlementCalculateRequest,
        *,
        actor_id: str,
    ) -> Settlement:
        s = await self.get(id_)
        if s.settlement_status not in (SettlementStatus.PENDING, SettlementStatus.CALCULATED):
            raise InvalidStateTransitionError(
                f"Cannot calculate from {s.settlement_status.value}"
            )
        before = _snapshot(s)
        s.system_total = payload.system_total
        s.settlement_status = SettlementStatus.CALCULATED
        await self._set_extras(s, payload.extra_charges)
        self._log(s, "CALCULATED", actor_id, before)
        await self.repo.db.commit()
        await self.repo.db.refresh(s)
        return s

    async def adjust(
        self,
        id_: str,
        payload: SettlementAdjustRequest,
        *,
        actor_id: str,
    ) -> Settlement:
        s = await self.get(id_)
        if s.settlement_status == SettlementStatus.APPROVED:
            raise ConflictError("Cannot adjust APPROVED settlement", code="ERR_APPROVED_LOCKED")
        before = _snapshot(s)
        if payload.final_amount is not None:
            s.final_amount = payload.final_amount
        if payload.driver_reported_amount is not None:
            s.driver_reported_amount = payload.driver_reported_amount
        if payload.has_flag is not None:
            s.has_flag = payload.has_flag
        if (
            s.driver_reported_amount is not None
            and s.system_total is not None
        ):
            s.discrepancy = Decimal(s.driver_reported_amount) - Decimal(s.system_total)
        s.note = payload.note
        s.settlement_status = SettlementStatus.ADJUSTED
        if payload.extra_charges is not None:
            await self._set_extras(s, payload.extra_charges)
        self._log(s, "ADJUSTED", actor_id, before, reason=payload.note)
        await self.repo.db.commit()
        await self.repo.db.refresh(s)
        return s

    async def approve(
        self,
        id_: str,
        payload: SettlementApproveRequest,
        *,
        actor_id: str,
    ) -> Settlement:
        s = await self.get(id_)
        if s.settlement_status == SettlementStatus.APPROVED:
            raise ConflictError("Already approved")
        if s.settlement_status == SettlementStatus.PENDING:
            raise InvalidStateTransitionError("Cannot approve PENDING settlement — calculate first")
        before = _snapshot(s)
        if payload.final_amount is not None:
            s.final_amount = payload.final_amount
        if s.final_amount is None:
            s.final_amount = s.system_total
        if payload.note is not None:
            s.note = payload.note
        s.settlement_status = SettlementStatus.APPROVED
        s.is_settled = True
        s.approved_at = datetime.now(timezone.utc)
        s.approved_by = actor_id
        s.unapproved_at = None
        s.unapproved_by = None
        s.unapproved_reason = None
        self._log(s, "APPROVED", actor_id, before)
        await self.repo.db.commit()
        await self.repo.db.refresh(s)
        return s

    async def unapprove(
        self,
        id_: str,
        payload: SettlementUnapproveRequest,
        *,
        actor_id: str,
    ) -> Settlement:
        s = await self.get(id_)
        if s.settlement_status != SettlementStatus.APPROVED:
            raise InvalidStateTransitionError("Only APPROVED can be unapproved")
        before = _snapshot(s)
        s.settlement_status = SettlementStatus.ADJUSTED
        s.is_settled = False
        s.unapproved_at = datetime.now(timezone.utc)
        s.unapproved_by = actor_id
        s.unapproved_reason = payload.reason
        self._log(s, "UNAPPROVED", actor_id, before, reason=payload.reason)
        await self.repo.db.commit()
        await self.repo.db.refresh(s)
        return s

    async def _set_extras(
        self, s: Settlement, extras: list[ExtraChargeRequest]
    ) -> None:
        new_rows = [
            ExtraCharge(
                tenant_id=self.tenant_id,
                settlement_id=s.id,
                type=e.type,
                amount=e.amount,
                description=e.description,
            )
            for e in extras
        ]
        await self.repo.replace_extras(s.id, new_rows)

    def _log(
        self,
        s: Settlement,
        action: str,
        actor_id: str,
        before: dict[str, Any],
        *,
        reason: str | None = None,
    ) -> None:
        log = SettlementAuditLog(
            tenant_id=self.tenant_id,
            settlement_id=s.id,
            action=action,
            actor_id=actor_id,
            before=before,
            after=_snapshot(s),
            reason=reason,
        )
        self.repo.db.add(log)
