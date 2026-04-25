"""DeliveryOrder 서비스 — CRUD + 상태 전이.

상태 전이 게이트 검증은 state_machine.assert_can_transition 에 위임.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.domains.delivery_orders.models import DeliveryOrder
from app.domains.delivery_orders.repository import DeliveryOrderRepository
from app.domains.delivery_orders.schema import (
    DeliveryOrderCreateRequest,
    DeliveryOrderUpdateRequest,
)
from app.domains.delivery_orders.state_machine import (
    TransitionContext,
    assert_can_transition,
)
from app.domains.legs.models import Leg
from app.domains.locations.models import Location
from app.domains.realtime.schema import RealtimeEvent
from app.domains.realtime.service import publish
from app.models.enums import DeliveryStatus


class DeliveryOrderService:
    def __init__(self, repo: DeliveryOrderRepository, tenant_id: str) -> None:
        self.repo = repo
        self.tenant_id = tenant_id

    async def create(self, payload: DeliveryOrderCreateRequest) -> DeliveryOrder:
        do = DeliveryOrder(
            tenant_id=self.tenant_id,
            status=DeliveryStatus.PLANNING,
            **payload.model_dump(),
        )
        await self.repo.create(do)
        await self.repo.db.commit()
        await self.repo.db.refresh(do)
        await publish(
            RealtimeEvent.now(
                type="do.created",
                tenant_id=self.tenant_id,
                payload={"deliveryOrderId": do.id, "status": do.status.value},
            ),
            db=self.repo.db,
        )
        return do

    async def get(self, id_: str) -> DeliveryOrder:
        do = await self.repo.get_by_id(id_)
        if not do:
            raise NotFoundError("Delivery order not found")
        return do

    async def list_paged(self, params):
        return await self.repo.list_paged(params)

    async def update(self, id_: str, payload: DeliveryOrderUpdateRequest) -> DeliveryOrder:
        do = await self.get(id_)
        await self.repo.update(do, **payload.model_dump(exclude_unset=True))
        await self.repo.db.commit()
        await self.repo.db.refresh(do)
        return do

    async def delete(self, id_: str) -> None:
        do = await self.get(id_)
        await self.repo.soft_delete(do)
        await self.repo.db.commit()

    async def transition(self, id_: str, target: DeliveryStatus) -> DeliveryOrder:
        do = await self.get(id_)
        previous = do.status
        ctx = await self._build_context(do)
        assert_can_transition(ctx, target)
        do.status = target
        await self.repo.db.flush()
        await self.repo.db.commit()
        await self.repo.db.refresh(do)
        await publish(
            RealtimeEvent.now(
                type="do.status_changed",
                tenant_id=self.tenant_id,
                payload={
                    "deliveryOrderId": do.id,
                    "from": previous.value,
                    "to": target.value,
                },
            ),
            db=self.repo.db,
        )
        return do

    async def _build_context(self, do: DeliveryOrder) -> TransitionContext:
        legs_stmt = select(Leg).where(
            Leg.delivery_order_id == do.id,
            Leg.is_deleted.is_(False),
            Leg.tenant_id == self.tenant_id,
        )
        legs = list((await self.repo.db.execute(legs_stmt)).scalars().all())
        loc_ids: set[str] = set()
        for leg in legs:
            if leg.pickup_location_id:
                loc_ids.add(leg.pickup_location_id)
            if leg.delivery_location_id:
                loc_ids.add(leg.delivery_location_id)
        if do.delivery_location_id:
            loc_ids.add(do.delivery_location_id)
        if do.return_location_id:
            loc_ids.add(do.return_location_id)
        locs: dict[str, Location] = {}
        if loc_ids:
            loc_stmt = select(Location).where(
                Location.id.in_(loc_ids),
                Location.tenant_id == self.tenant_id,
                Location.is_deleted.is_(False),
            )
            for loc in (await self.repo.db.execute(loc_stmt)).scalars():
                locs[loc.id] = loc
        return TransitionContext(do=do, legs=legs, locations_by_id=locs)
