# src/driver_mobile/service_v3.py
"""v3 driver_mobile — 컨테이너/Stop 단위 모바일 API."""
from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, BadRequestException
from container.model import ContainerModel
from container.state_derive import derive_and_save_state
from container_stop.model import ContainerStopModel
from customer.model import CustomerModel
from delivery_order.model import DeliveryOrderModel
from driver.model import DriverModel
from leg.const.status import LegStatus
from leg.model import LegModel
from leg_driver_segment.model import LegDriverSegmentModel
from location.model import LocationModel


async def _resolve_driver(db: AsyncSession, team_id: int, user_id: int) -> int:
    """user_id → driver_id (v3 기사 식별)."""
    row = (await db.execute(
        select(DriverModel.id).where(
            DriverModel.team_id == team_id,
            DriverModel.user_id == user_id,
            DriverModel.is_active.is_(True),
        )
    )).first()
    if row is None:
        raise NotFoundException("Driver")
    return row[0]


async def get_today_containers_for_driver(
    db: AsyncSession, team_id: int, user_id: int,
) -> dict:
    """driver 가 활성으로 배정된 leg 의 컨테이너 + stop 시퀀스."""
    driver_id = await _resolve_driver(db, team_id, user_id)

    # 활성 segment 또는 leg.driver_id 가 본인인 leg 의 container_id 수집
    segs = (await db.execute(
        select(LegDriverSegmentModel.leg_id).where(
            LegDriverSegmentModel.team_id == team_id,
            LegDriverSegmentModel.driver_id == driver_id,
            LegDriverSegmentModel.is_active.is_(True),
        )
    )).scalars().all()
    legs_seg = set(segs)
    legs_direct = (await db.execute(
        select(LegModel.id, LegModel.container_id).where(
            LegModel.team_id == team_id,
            LegModel.driver_id == driver_id,
            LegModel.is_active.is_(True),
            LegModel.status.in_([LegStatus.PENDING, LegStatus.IN_TRANSIT, LegStatus.COMPLETED]),
        )
    )).all()

    # legs_seg + legs_direct 의 container_id 집합
    leg_ids: set[int] = set(legs_seg)
    container_ids: set[int] = set()
    for l_id, c_id in legs_direct:
        leg_ids.add(l_id)
        if c_id is not None:
            container_ids.add(c_id)

    # legs_seg 의 leg 에서 container_id 추가 fetch
    if legs_seg:
        more = (await db.execute(
            select(LegModel.container_id).where(
                LegModel.id.in_(legs_seg),
                LegModel.container_id.is_not(None),
            )
        )).scalars().all()
        container_ids.update(c for c in more if c is not None)

    if not container_ids:
        return {"containers": []}

    # 컨테이너 + 소속 D/O 메타
    rows = (await db.execute(
        select(
            ContainerModel,
            DeliveryOrderModel.bl_number,
            DeliveryOrderModel.direction,
            CustomerModel.name.label("customer_name"),
        )
        .outerjoin(DeliveryOrderModel, DeliveryOrderModel.id == ContainerModel.delivery_order_id)
        .outerjoin(CustomerModel, CustomerModel.id == DeliveryOrderModel.customer_id)
        .where(
            ContainerModel.team_id == team_id,
            ContainerModel.id.in_(container_ids),
            ContainerModel.is_active.is_(True),
        )
        .order_by(ContainerModel.id.asc())
    )).all()

    # leg 진행률
    leg_count_q = (await db.execute(
        select(LegModel.container_id, LegModel.status).where(
            LegModel.team_id == team_id,
            LegModel.container_id.in_(container_ids),
            LegModel.is_active.is_(True),
        )
    )).all()
    counts: dict[int, dict] = {}
    for cid, st in leg_count_q:
        if cid is None:
            continue
        d = counts.setdefault(cid, {"total": 0, "done": 0})
        d["total"] += 1
        if st == LegStatus.COMPLETED:
            d["done"] += 1

    # stops + location
    stop_rows = (await db.execute(
        select(ContainerStopModel, LocationModel.name, LocationModel.address)
        .outerjoin(LocationModel, LocationModel.id == ContainerStopModel.location_id)
        .where(
            ContainerStopModel.team_id == team_id,
            ContainerStopModel.container_id.in_(container_ids),
            ContainerStopModel.is_active.is_(True),
        )
        .order_by(ContainerStopModel.container_id.asc(), ContainerStopModel.sequence_no.asc())
    )).all()
    stops_by_container: dict[int, list[dict]] = {}
    for s, loc_name, loc_addr in stop_rows:
        stops_by_container.setdefault(s.container_id, []).append({
            "id": s.id,
            "container_id": s.container_id,
            "sequence_no": s.sequence_no,
            "role": s.role.value if hasattr(s.role, "value") else str(s.role),
            "location_id": s.location_id,
            "location_name": loc_name,
            "location_address": loc_addr,
            "planned_arrival": s.planned_arrival,
            "actual_arrival": s.actual_arrival,
            "actual_departure": s.actual_departure,
        })

    out: list[dict] = []
    for c, bl, direction, customer in rows:
        stops = stops_by_container.get(c.id, [])
        next_stop = next((st for st in stops if st["actual_arrival"] is None), None)
        out.append({
            "container_id": c.id,
            "container_number": c.container_number,
            "size": c.size.value if c.size else None,
            "bl_number": bl,
            "customer_name": customer,
            "direction": direction.value if direction and hasattr(direction, "value") else direction,
            "work_state": (
                c.work_state.value
                if c.work_state and hasattr(c.work_state, "value")
                else (c.work_state if c.work_state else None)
            ),
            "legs_total": counts.get(c.id, {}).get("total", 0),
            "legs_completed": counts.get(c.id, {}).get("done", 0),
            "next_stop": next_stop,
            "stops": stops,
        })
    return {"containers": out}


async def report_stop_arrive(
    db: AsyncSession, team_id: int, user_id: int,
    stop_id: int, *, occurred_at: datetime | None = None,
) -> dict:
    """stop 도착 보고 — actual_arrival 채우고 work_state derive."""
    driver_id = await _resolve_driver(db, team_id, user_id)
    stop = (await db.execute(
        select(ContainerStopModel).where(
            ContainerStopModel.team_id == team_id,
            ContainerStopModel.id == stop_id,
            ContainerStopModel.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if stop is None:
        raise NotFoundException("Stop")

    # 권한 체크 — 이 컨테이너에 활성 leg 가 본인 driver_id 인지
    has_active = (await db.execute(
        select(LegModel.id).where(
            LegModel.team_id == team_id,
            LegModel.container_id == stop.container_id,
            LegModel.driver_id == driver_id,
            LegModel.is_active.is_(True),
        ).limit(1)
    )).first()
    if has_active is None:
        raise BadRequestException("이 컨테이너에 배정된 기사가 아닙니다")

    when = occurred_at or datetime.now(timezone.utc)
    if stop.actual_arrival is None:
        stop.actual_arrival = when
        await db.flush()
    await derive_and_save_state(db, team_id, stop.container_id)
    return {"ok": True, "stop_id": stop_id, "actual_arrival": stop.actual_arrival.isoformat()}


async def report_stop_depart(
    db: AsyncSession, team_id: int, user_id: int,
    stop_id: int, *, occurred_at: datetime | None = None,
) -> dict:
    """stop 출발 보고 — actual_departure 채우고 work_state derive."""
    driver_id = await _resolve_driver(db, team_id, user_id)
    stop = (await db.execute(
        select(ContainerStopModel).where(
            ContainerStopModel.team_id == team_id,
            ContainerStopModel.id == stop_id,
            ContainerStopModel.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if stop is None:
        raise NotFoundException("Stop")

    has_active = (await db.execute(
        select(LegModel.id).where(
            LegModel.team_id == team_id,
            LegModel.container_id == stop.container_id,
            LegModel.driver_id == driver_id,
            LegModel.is_active.is_(True),
        ).limit(1)
    )).first()
    if has_active is None:
        raise BadRequestException("이 컨테이너에 배정된 기사가 아닙니다")

    when = occurred_at or datetime.now(timezone.utc)
    if stop.actual_arrival is None:
        # 도착 누락 — 함께 채움
        stop.actual_arrival = when
    if stop.actual_departure is None:
        stop.actual_departure = when
    await db.flush()
    await derive_and_save_state(db, team_id, stop.container_id)
    return {
        "ok": True, "stop_id": stop_id,
        "actual_arrival": stop.actual_arrival.isoformat() if stop.actual_arrival else None,
        "actual_departure": stop.actual_departure.isoformat() if stop.actual_departure else None,
    }
