# src/container/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from container.repository import ContainerRepository
from container.schemas.request import (
    ContainerCreateRequest, ContainerUpdateRequest,
    PaginateContainerRequest,
    ContainerEventCreateRequest, PaginateContainerEventRequest,
    ContainerBulkDeleteRequest,
)
from container.schemas.response import (
    ContainerResponseSchema, ContainerDeleteResponseSchema,
    ContainerEventResponseSchema,
    ContainerBulkDeleteResponseSchema, BulkDeleteResultItem, BulkSummary,
)


class ContainerService:
    """Container 비즈니스 로직."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = ContainerRepository(db, team_id)

    # ── Create ──

    async def create(
        self,
        payload: ContainerCreateRequest,
        actor_user_id: int | None = None,
    ) -> ContainerResponseSchema:
        data = payload.model_dump()
        if data.get("sequence_no") is None:
            data["sequence_no"] = await self.repo.next_sequence_no(data["delivery_order_id"])
        row = await self.repo.create(data, actor_user_id=actor_user_id)
        return ContainerResponseSchema.model_validate(row)

    # ── Read ──

    async def get(self, container_id: int) -> ContainerResponseSchema:
        row = await self.repo.get(container_id)
        if not row:
            raise NotFoundException("컨테이너")
        return ContainerResponseSchema.model_validate(row)

    async def list_by_delivery_order(self, delivery_order_id: int) -> List[ContainerResponseSchema]:
        rows = await self.repo.list_by_delivery_order(delivery_order_id)
        return [ContainerResponseSchema.model_validate(r) for r in rows]

    async def list_paginated(
        self, request: PaginateContainerRequest,
    ) -> CursorPaginationResult[ContainerResponseSchema]:
        result = await self.repo.get_paginated(request)
        rows = list(result.data)
        if not rows:
            result.data = []
            return result

        # ── v3 enrich: D/O 메타 + leg 진행률 + 현재 driver ──
        from sqlalchemy import select, func, case
        from delivery_order.model import DeliveryOrderModel
        from customer.model import CustomerModel
        from leg.model import LegModel
        from leg.const.status import LegStatus
        from driver.model import DriverModel
        from user.model import UserModel
        from container_stop.model import ContainerStopModel

        ids = [r.id for r in rows]
        do_ids = list({r.delivery_order_id for r in rows})

        # D/O 메타 + customer 이름
        dos = (await self.db.execute(
            select(
                DeliveryOrderModel.id,
                DeliveryOrderModel.bl_number,
                DeliveryOrderModel.booking_number,
                DeliveryOrderModel.customer_id,
                DeliveryOrderModel.direction,
                CustomerModel.name.label("customer_name"),
            )
            .outerjoin(CustomerModel, CustomerModel.id == DeliveryOrderModel.customer_id)
            .where(DeliveryOrderModel.team_id == self.repo.team_id, DeliveryOrderModel.id.in_(do_ids))
        )).all()
        do_map = {d.id: d for d in dos}

        # leg 진행률 + 활성 leg 의 driver
        legs_total_q = (await self.db.execute(
            select(
                LegModel.container_id,
                func.count(LegModel.id).label("total"),
                func.sum(case((LegModel.status == LegStatus.COMPLETED, 1), else_=0)).label("done"),
            )
            .where(
                LegModel.team_id == self.repo.team_id,
                LegModel.container_id.in_(ids),
                LegModel.is_active.is_(True),
            )
            .group_by(LegModel.container_id)
        )).all()
        leg_count_map = {r.container_id: (int(r.total or 0), int(r.done or 0)) for r in legs_total_q}

        # 활성 leg → 현재 driver
        active_q = (await self.db.execute(
            select(LegModel.container_id, LegModel.driver_id)
            .where(
                LegModel.team_id == self.repo.team_id,
                LegModel.container_id.in_(ids),
                LegModel.is_active.is_(True),
                LegModel.status.in_([LegStatus.IN_TRANSIT, LegStatus.PENDING]),
            )
            .order_by(LegModel.id.asc())
        )).all()
        first_active_driver: dict[int, int | None] = {}
        for cid, did in active_q:
            if cid not in first_active_driver:
                first_active_driver[cid] = did

        # driver 이름 조회
        driver_ids = [d for d in first_active_driver.values() if d]
        driver_name_map: dict[int, str] = {}
        if driver_ids:
            for did, name in (await self.db.execute(
                select(DriverModel.id, func.coalesce(UserModel.name, UserModel.email))
                .outerjoin(UserModel, UserModel.id == DriverModel.user_id)
                .where(DriverModel.id.in_(driver_ids))
            )).all():
                driver_name_map[did] = name or ""

        # next stop = 가장 작은 sequence_no 의 stop with actual_arrival is null
        next_stop_q = (await self.db.execute(
            select(
                ContainerStopModel.container_id,
                func.min(ContainerStopModel.id).label("sid"),
            )
            .where(
                ContainerStopModel.team_id == self.repo.team_id,
                ContainerStopModel.container_id.in_(ids),
                ContainerStopModel.is_active.is_(True),
                ContainerStopModel.actual_arrival.is_(None),
            )
            .group_by(ContainerStopModel.container_id)
        )).all()
        next_stop_map = {r.container_id: r.sid for r in next_stop_q}

        out = []
        for r in rows:
            schema = ContainerResponseSchema.model_validate(r)
            do = do_map.get(r.delivery_order_id)
            total, done = leg_count_map.get(r.id, (0, 0))
            driver_id = first_active_driver.get(r.id)
            schema = schema.model_copy(update={
                "bl_number":         do.bl_number if do else None,
                "booking_number":    do.booking_number if do else None,
                "customer_id":       do.customer_id if do else None,
                "customer_name":     do.customer_name if do else None,
                "direction":         (do.direction.value if do and hasattr(do.direction, "value") else (do.direction if do else None)),
                "next_stop_id":      next_stop_map.get(r.id),
                "current_driver_id":   driver_id,
                "current_driver_name": driver_name_map.get(driver_id) if driver_id else None,
                "legs_total":     total,
                "legs_completed": done,
            })
            out.append(schema)

        result.data = out
        return result

    # ── v3 Container 상세 (full) ──

    async def get_full(self, container_id: int):
        from container.schemas.response import (
            ContainerFullResponseSchema, StopResponseSchema, LegFullSchema,
            DriverSegmentResponseSchema,
        )
        from sqlalchemy import select
        from delivery_order.model import DeliveryOrderModel
        from customer.model import CustomerModel
        from terminal.model import TerminalModel
        from vessel.model import VesselModel
        from location.model import LocationModel
        from leg.model import LegModel
        from leg_driver_segment.model import LegDriverSegmentModel
        from container_stop.model import ContainerStopModel
        from container.model import ContainerEventModel
        from driver.model import DriverModel
        from user.model import UserModel
        from sqlalchemy import func

        row = await self.repo.get(container_id)
        if not row:
            raise NotFoundException("컨테이너")
        container = ContainerResponseSchema.model_validate(row)

        # D/O + 마스터 메타
        do_meta = (await self.db.execute(
            select(
                DeliveryOrderModel.id,
                DeliveryOrderModel.bl_number,
                DeliveryOrderModel.booking_number,
                DeliveryOrderModel.reference,
                DeliveryOrderModel.customer_id,
                CustomerModel.name.label("customer_name"),
                DeliveryOrderModel.direction,
                DeliveryOrderModel.eta,
                DeliveryOrderModel.terminal_id,
                TerminalModel.name.label("terminal_name"),
                DeliveryOrderModel.vessel_id,
                VesselModel.name.label("vessel_name"),
                DeliveryOrderModel.bl_released,
            )
            .outerjoin(CustomerModel, CustomerModel.id == DeliveryOrderModel.customer_id)
            .outerjoin(TerminalModel, TerminalModel.id == DeliveryOrderModel.terminal_id)
            .outerjoin(VesselModel,   VesselModel.id   == DeliveryOrderModel.vessel_id)
            .where(DeliveryOrderModel.id == row.delivery_order_id)
        )).first()
        do_dict = {
            "id": do_meta.id if do_meta else None,
            "bl_number": do_meta.bl_number if do_meta else None,
            "booking_number": do_meta.booking_number if do_meta else None,
            "reference": do_meta.reference if do_meta else None,
            "customer_id": do_meta.customer_id if do_meta else None,
            "customer_name": do_meta.customer_name if do_meta else None,
            "direction": (do_meta.direction.value if do_meta and hasattr(do_meta.direction, "value") else (do_meta.direction if do_meta else None)),
            "eta": do_meta.eta.isoformat() if do_meta and do_meta.eta else None,
            "terminal_id": do_meta.terminal_id if do_meta else None,
            "terminal_name": do_meta.terminal_name if do_meta else None,
            "vessel_id": do_meta.vessel_id if do_meta else None,
            "vessel_name": do_meta.vessel_name if do_meta else None,
            "bl_released": bool(do_meta.bl_released) if do_meta else False,
        } if do_meta else {}

        # Stops(=Points) + 타입별 마스터 이름 enrich
        stop_rows = (await self.db.execute(
            select(
                ContainerStopModel,
                LocationModel.name.label("loc_name"),
                TerminalModel.name.label("term_name"),
                CustomerModel.name.label("cust_name"),
            )
            .outerjoin(LocationModel, LocationModel.id == ContainerStopModel.location_id)
            .outerjoin(TerminalModel, TerminalModel.id == ContainerStopModel.terminal_id)
            .outerjoin(CustomerModel, CustomerModel.id == ContainerStopModel.customer_id)
            .where(
                ContainerStopModel.team_id == self.repo.team_id,
                ContainerStopModel.container_id == container_id,
                ContainerStopModel.is_active.is_(True),
            )
            .order_by(ContainerStopModel.sequence_no.asc())
        )).all()
        stops = []
        for s, loc_name, term_name, cust_name in stop_rows:
            point_name = term_name or loc_name or cust_name
            stops.append(StopResponseSchema.model_validate(s).model_copy(
                update={"location_name": loc_name, "point_name": point_name},
            ))

        # Legs (active 만)
        legs_rows = (await self.db.execute(
            select(LegModel)
            .where(
                LegModel.team_id == self.repo.team_id,
                LegModel.container_id == container_id,
                LegModel.is_active.is_(True),
            )
            .order_by(LegModel.id.asc())
        )).scalars().all()
        leg_ids = [l.id for l in legs_rows]

        # leg → segments
        seg_map: dict[int, list] = {}
        if leg_ids:
            seg_rows = (await self.db.execute(
                select(LegDriverSegmentModel, func.coalesce(UserModel.name, UserModel.email).label("dn"))
                .outerjoin(DriverModel, DriverModel.id == LegDriverSegmentModel.driver_id)
                .outerjoin(UserModel,   UserModel.id   == DriverModel.user_id)
                .where(
                    LegDriverSegmentModel.team_id == self.repo.team_id,
                    LegDriverSegmentModel.leg_id.in_(leg_ids),
                    LegDriverSegmentModel.is_active.is_(True),
                )
                .order_by(LegDriverSegmentModel.leg_id.asc(), LegDriverSegmentModel.sequence_no.asc())
            )).all()
            for s, dn in seg_rows:
                seg_map.setdefault(s.leg_id, []).append(
                    DriverSegmentResponseSchema.model_validate(s).model_copy(update={"driver_name": dn})
                )

        # leg 별 요율/원가는 정산 시점에 payroll(RateResolver) 가, 고객 청구는
        # invoice 가 담당한다. 컨테이너 상세 응답엔 금액을 싣지 않는다.

        # leg driver name (current segment driver_id 기반)
        driver_names: dict[int, str] = {}
        leg_driver_ids = list({l.driver_id for l in legs_rows if l.driver_id})
        if leg_driver_ids:
            for did, name in (await self.db.execute(
                select(DriverModel.id, func.coalesce(UserModel.name, UserModel.email))
                .outerjoin(UserModel, UserModel.id == DriverModel.user_id)
                .where(DriverModel.id.in_(leg_driver_ids))
            )).all():
                driver_names[did] = name or ""

        legs_full: list[LegFullSchema] = []
        for l in legs_rows:
            legs_full.append(LegFullSchema(
                id=l.id,
                delivery_order_id=l.delivery_order_id,
                container_id=l.container_id,
                move_type=l.move_type,
                service_type=l.service_type,
                from_point_id=l.from_point_id,
                to_point_id=l.to_point_id,
                from_location_type=l.from_location_type,
                to_location_type=l.to_location_type,
                move_code=l.move_code,
                status=l.status,
                driver_id=l.driver_id,
                driver_name=driver_names.get(l.driver_id) if l.driver_id else None,
                started_at=l.started_at,
                arrived_at=l.arrived_at,
                completed_at=l.completed_at,
                failure_reason=l.failure_reason,
                reissued_from_leg_id=l.reissued_from_leg_id,
                note=l.note,
                is_active=l.is_active,
                segments=seg_map.get(l.id, []),
            ))

        # Events
        events_rows = (await self.db.execute(
            select(ContainerEventModel)
            .where(
                ContainerEventModel.team_id == self.repo.team_id,
                ContainerEventModel.container_id == container_id,
                ContainerEventModel.is_active.is_(True),
            )
            .order_by(ContainerEventModel.occurred_at.desc())
        )).scalars().all()
        events = [ContainerEventResponseSchema.model_validate(e) for e in events_rows]

        return ContainerFullResponseSchema(
            container=container,
            delivery_order=do_dict,
            stops=stops,
            legs=legs_full,
            events=events,
        )

    # ── Update ──

    async def update(
        self,
        container_id: int,
        payload: ContainerUpdateRequest,
        actor_user_id: int | None = None,
    ) -> ContainerResponseSchema:
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(container_id, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("컨테이너")
        return ContainerResponseSchema.model_validate(row)

    # ── Delete ──

    async def delete(
        self,
        container_id: int,
        actor_user_id: int | None = None,
    ) -> ContainerDeleteResponseSchema:
        row = await self.repo.get(container_id)
        if not row:
            raise NotFoundException("컨테이너")
        await self.repo.soft_deactivate_by_id(container_id, actor_user_id=actor_user_id)
        return ContainerDeleteResponseSchema(id=container_id, deleted=True, soft_deleted=True)

    async def delete_bulk(
        self,
        payload: ContainerBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> ContainerBulkDeleteResponseSchema:
        existing_rows = await self.repo.get_many(payload.ids)
        existing_ids = {row.id for row in existing_rows}
        missing_ids = set(payload.ids) - existing_ids
        if missing_ids:
            raise NotFoundException(
                f"컨테이너(ID={list(missing_ids)})",
                detail={"missing_ids": list(missing_ids)},
            )
        results: List[BulkDeleteResultItem] = []
        for cid in payload.ids:
            await self.repo.soft_deactivate_by_id(cid, actor_user_id=actor_user_id)
            results.append(BulkDeleteResultItem(id=cid, success=True, soft_deleted=True))
        return ContainerBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.ids), succeeded=len(results), failed=0),
        )

    # ═══════════════════════════════════════════════════════════════
    # Container Events
    # ═══════════════════════════════════════════════════════════════

    async def create_event(
        self,
        container_id: int,
        payload: ContainerEventCreateRequest,
        actor_user_id: int | None = None,
    ) -> ContainerEventResponseSchema:
        # 컨테이너 존재 검증
        container = await self.repo.get(container_id)
        if not container:
            raise NotFoundException("컨테이너")
        data = payload.model_dump()
        data["container_id"] = container_id
        row = await self.repo.create_event(data, actor_user_id=actor_user_id)
        return ContainerEventResponseSchema.model_validate(row)

    async def list_events_by_container(self, container_id: int) -> List[ContainerEventResponseSchema]:
        return [
            ContainerEventResponseSchema.model_validate(r)
            for r in await self.repo.list_events_by_container(container_id)
        ]

    async def list_events_paginated(
        self, request: PaginateContainerEventRequest,
    ) -> CursorPaginationResult[ContainerEventResponseSchema]:
        result = await self.repo.get_events_paginated(request)
        result.data = [ContainerEventResponseSchema.model_validate(r) for r in result.data]
        return result
