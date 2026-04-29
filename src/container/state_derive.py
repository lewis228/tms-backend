# src/container/state_derive.py
"""Container.work_state 자동 derive — leg/stop 변경 시 호출.

규칙 (v3):
  - HOLD/CANCELLED 는 수동 토글 (자동 변경 X)
  - stops 0개 → DRAFT
  - 모든 leg COMPLETED + 마지막 stop=TERMINUS 도착 → COMPLETED
  - 활성 leg.status = IN_TRANSIT → IN_TRANSIT
  - 마지막 도착 stop 의 다음 leg 미생성 → WAITING_PLAN ⚠️
  - 마지막 도착 stop 의 다음 leg 있고 PENDING → AT_STOP
  - 그 외 → PLANNED
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from container.model import ContainerModel
from container_stop.model import ContainerStopModel
from leg.model import LegModel
from leg.const.status import ContainerState, LegStatus, StopRole


async def derive_and_save_state(
    db: AsyncSession,
    team_id: int,
    container_id: int,
) -> ContainerState | None:
    """container 의 work_state 를 자동 derive 해서 저장. HOLD/CANCELLED 는 건드리지 않음.

    Returns:
        새로 저장한 state. 변경 없거나 HOLD/CANCELLED 면 None.
    """
    container = (await db.execute(
        select(ContainerModel).where(
            ContainerModel.team_id == team_id,
            ContainerModel.id == container_id,
        )
    )).scalar_one_or_none()
    if container is None:
        return None

    # HOLD / CANCELLED 는 수동 토글 — 자동 변경 X
    if container.work_state in (ContainerState.HOLD, ContainerState.CANCELLED):
        return None

    # stops 조회
    stops = (await db.execute(
        select(ContainerStopModel)
        .where(
            ContainerStopModel.team_id == team_id,
            ContainerStopModel.container_id == container_id,
            ContainerStopModel.is_active.is_(True),
        )
        .order_by(ContainerStopModel.sequence_no.asc())
    )).scalars().all()

    if len(stops) == 0:
        new_state = ContainerState.DRAFT
    else:
        # legs 조회
        legs = (await db.execute(
            select(LegModel)
            .where(
                LegModel.team_id == team_id,
                LegModel.container_id == container_id,
                LegModel.is_active.is_(True),
            )
            .order_by(LegModel.id.asc())
        )).scalars().all()

        if not legs:
            new_state = ContainerState.PLANNED
        elif all(l.status == LegStatus.COMPLETED for l in legs):
            # 모든 leg COMPLETED — 마지막 TERMINUS stop 도착 여부 확인
            last_stop = stops[-1]
            if (
                last_stop.role == StopRole.TERMINUS
                and last_stop.actual_arrival is not None
            ):
                new_state = ContainerState.COMPLETED
            else:
                # 모든 leg 완료지만 종착 미도착 — 일단 AT_STOP 처리
                new_state = ContainerState.AT_STOP
        elif any(l.status == LegStatus.IN_TRANSIT for l in legs):
            new_state = ContainerState.IN_TRANSIT
        else:
            # 모든 leg PENDING — 마지막 actual_arrival 있는 stop 의 다음 leg 미생성?
            last_actual_stop = next(
                (s for s in reversed(stops) if s.actual_arrival is not None),
                None,
            )
            if last_actual_stop is None:
                new_state = ContainerState.PLANNED
            else:
                # 다음 stop 시퀀스에 대한 leg 가 있는지 — 매우 단순화
                next_seq = last_actual_stop.sequence_no + 1
                has_next_stop = any(s.sequence_no >= next_seq for s in stops)
                if not has_next_stop:
                    new_state = ContainerState.WAITING_PLAN
                else:
                    new_state = ContainerState.AT_STOP

    if container.work_state != new_state:
        prev_state = container.work_state
        container.work_state = new_state
        await db.flush()
        # WS publish (실시간 알림)
        try:
            from realtime.v3_publish import safe_publish, EVT_CONTAINER_STATE_CHANGED
            await safe_publish(
                type=EVT_CONTAINER_STATE_CHANGED,
                team_id=team_id,
                payload={
                    "container_id": container_id,
                    "work_state": new_state.value,
                    "from": prev_state.value if prev_state else None,
                },
            )
            # v3: WAITING_PLAN 진입 시 inbox 알림 (디스패처에게 다음 stop 추가 요청).
            if (
                new_state == ContainerState.WAITING_PLAN
                and prev_state != ContainerState.WAITING_PLAN
            ):
                from realtime.service import publish
                from realtime.schemas.event import RealtimeEvent
                await publish(RealtimeEvent.now(
                    type="container.waiting_plan",
                    team_id=team_id,
                    payload={
                        "containerId": container_id,
                        "from": prev_state.value if prev_state else None,
                    },
                ))
        except Exception:  # noqa: BLE001
            pass
        return new_state
    return None
