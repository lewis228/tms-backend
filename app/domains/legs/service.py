"""Leg 서비스 — CRUD + 상태 전이.

상태 전이:
- PENDING → IN_TRANSIT (started_at 기록)
- IN_TRANSIT → COMPLETED (completed_at + Settlement PENDING 자동 생성)
- IN_TRANSIT → FAILED (failure_reason 필수)

Settlement 자동 생성: COMPLETED 시 Leg.settlement_id 가 비어있으면 system_total=0
PENDING 상태로 1건 생성. 정확한 금액은 별도 계산 단계에서. (Phase 1 결정 #6)
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.core.exceptions import InvalidStateTransitionError, NotFoundError, ValidationError
from app.domains.legs.models import Leg
from app.domains.legs.repository import LegRepository
from app.domains.legs.schema import LegCreateRequest, LegUpdateRequest
from app.domains.realtime.schema import RealtimeEvent
from app.domains.realtime.service import publish
from app.domains.settlements.models import Settlement
from app.models.enums import LegStatus, SettlementStatus

_ALLOWED: dict[LegStatus, set[LegStatus]] = {
    LegStatus.PENDING: {LegStatus.IN_TRANSIT, LegStatus.FAILED},
    LegStatus.IN_TRANSIT: {LegStatus.COMPLETED, LegStatus.FAILED},
    LegStatus.COMPLETED: set(),
    LegStatus.FAILED: set(),
}


class LegService:
    def __init__(self, repo: LegRepository, tenant_id: str) -> None:
        self.repo = repo
        self.tenant_id = tenant_id

    async def create(self, payload: LegCreateRequest) -> Leg:
        leg = Leg(
            tenant_id=self.tenant_id,
            status=LegStatus.PENDING,
            **payload.model_dump(),
        )
        await self.repo.create(leg)
        await self.repo.db.commit()
        await self.repo.db.refresh(leg)
        await publish(
            RealtimeEvent.now(
                type="leg.created",
                tenant_id=self.tenant_id,
                payload={
                    "legId": leg.id,
                    "deliveryOrderId": leg.delivery_order_id,
                    "driverId": leg.driver_id,
                },
            ),
            db=self.repo.db,
        )
        return leg

    async def get(self, id_: str) -> Leg:
        leg = await self.repo.get_by_id(id_)
        if not leg:
            raise NotFoundError("Leg not found")
        return leg

    async def list_paged(self, params):
        return await self.repo.list_paged(params)

    async def list_for_delivery_order(self, do_id: str) -> list[Leg]:
        return await self.repo.list_by_delivery_order(do_id)

    async def list_for_driver(self, driver_id: str, params):
        return await self.repo.list_by_driver(driver_id, params)

    async def update(self, id_: str, payload: LegUpdateRequest) -> Leg:
        leg = await self.get(id_)
        await self.repo.update(leg, **payload.model_dump(exclude_unset=True))
        await self.repo.db.commit()
        await self.repo.db.refresh(leg)
        return leg

    async def delete(self, id_: str) -> None:
        leg = await self.get(id_)
        await self.repo.soft_delete(leg)
        await self.repo.db.commit()

    async def transition(
        self, id_: str, target: LegStatus, *, failure_reason: str | None = None
    ) -> Leg:
        leg = await self.get(id_)
        previous = leg.status
        if target not in _ALLOWED.get(leg.status, set()):
            raise InvalidStateTransitionError(
                f"Cannot transition leg {leg.status.value} → {target.value}",
                details={"from": leg.status.value, "to": target.value},
            )
        if target == LegStatus.FAILED and not failure_reason:
            raise ValidationError("failure_reason required for FAILED transition")
        now = datetime.now(timezone.utc)
        if target == LegStatus.IN_TRANSIT:
            leg.started_at = now
        elif target == LegStatus.COMPLETED:
            leg.completed_at = now
            leg.arrived_at = leg.arrived_at or now
            await self._ensure_settlement(leg)
        elif target == LegStatus.FAILED:
            leg.failure_reason = failure_reason
        leg.status = target
        await self.repo.db.flush()
        await self.repo.db.commit()
        await self.repo.db.refresh(leg)
        await publish(
            RealtimeEvent.now(
                type="leg.status_changed",
                tenant_id=self.tenant_id,
                payload={
                    "legId": leg.id,
                    "deliveryOrderId": leg.delivery_order_id,
                    "driverId": leg.driver_id,
                    "from": previous.value,
                    "to": target.value,
                    "settlementId": leg.settlement_id,
                },
            ),
            db=self.repo.db,
        )
        return leg

    async def _ensure_settlement(self, leg: Leg) -> None:
        if leg.settlement_id:
            return
        s = Settlement(
            tenant_id=self.tenant_id,
            leg_id=leg.id,
            system_total=Decimal("0.00"),
            settlement_status=SettlementStatus.PENDING,
            is_settled=False,
        )
        self.repo.db.add(s)
        await self.repo.db.flush()
        leg.settlement_id = s.id
