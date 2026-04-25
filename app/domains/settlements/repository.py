"""Settlement Repository — Settlement / ExtraCharge / AuditLog 묶음."""
from __future__ import annotations

from sqlalchemy import select

from app.core.repository import BaseRepository
from app.domains.settlements.models import (
    ExtraCharge,
    Settlement,
    SettlementAuditLog,
)


class SettlementRepository(BaseRepository[Settlement]):
    model = Settlement

    async def list_extras(self, settlement_id: str) -> list[ExtraCharge]:
        stmt = select(ExtraCharge).where(
            ExtraCharge.settlement_id == settlement_id,
            ExtraCharge.is_deleted.is_(False),
            ExtraCharge.tenant_id == self.tenant_id,
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_audit_logs(self, settlement_id: str) -> list[SettlementAuditLog]:
        stmt = (
            select(SettlementAuditLog)
            .where(
                SettlementAuditLog.settlement_id == settlement_id,
                SettlementAuditLog.is_deleted.is_(False),
                SettlementAuditLog.tenant_id == self.tenant_id,
            )
            .order_by(SettlementAuditLog.created_at)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def replace_extras(
        self, settlement_id: str, extras: list[ExtraCharge]
    ) -> None:
        existing = await self.list_extras(settlement_id)
        for e in existing:
            e.is_deleted = True
        for e in extras:
            self.db.add(e)
        await self.db.flush()
