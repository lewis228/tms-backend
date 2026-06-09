# src/leg/generator.py
"""Load Type 템플릿 → Leg 자동 생성기 (재설계 1d).

container + load_type_template 선택 → 템플릿 step 청사진대로 해당 container 의 leg N개 생성.
- 템플릿 enum(LOAD/EMPTY/NONE · LIVE/DROP/NONE · TERMINAL/YARD/CUSTOMER · PPU…) → leg enum 매핑.
- 생성된 leg 는 PENDING(미배차) → D/O 자동 DISPATCHING 파생.

도메인 위치: leg(트랜잭션) 이 leg 생성의 주체. load_type_template(설정/마스터) 모델만 읽음.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, BadRequestException
from container.model import ContainerModel
from delivery_order.const.status import DeliveryStatus
from leg.model import LegModel
from leg.const.status import (
    LegStatus, MoveType, ServiceType, LegLocationType, LegMoveCode,
)
from load_type_template.model import LoadTypeTemplateModel, LoadTypeTemplateStepModel
from load_type_template.const.status import TemplateMoveType, TemplateServiceType


# 템플릿 enum → leg enum 매핑 (값 이름이 달라 명시 매핑)
_MOVE_MAP = {
    TemplateMoveType.LOAD:  MoveType.LOADED,
    TemplateMoveType.EMPTY: MoveType.EMPTY,
    TemplateMoveType.NONE:  MoveType.BOBTAIL,
}
_SVC_MAP = {
    TemplateServiceType.LIVE: ServiceType.LIVE,
    TemplateServiceType.DROP: ServiceType.DROP,
    TemplateServiceType.NONE: ServiceType.NONE,
}

# LocationType / MoveCode 는 값이 동일(TERMINAL/YARD/CUSTOMER, PPU/PRE/…) → 값으로 변환
def _loc(v) -> LegLocationType | None:
    return LegLocationType(v.value) if v is not None else None


def _code(v) -> LegMoveCode | None:
    return LegMoveCode(v.value) if v is not None else None


# 재생성 시 보호되는 leg 상태(진행/완료된 leg 는 덮어쓰지 않음)
_PROTECTED = {LegStatus.IN_TRANSIT, LegStatus.COMPLETED}


async def apply_load_type(
    db: AsyncSession,
    team_id: int,
    *,
    container_id: int,
    template_id: int,
    actor_user_id: int | None = None,
    replace_existing: bool = False,
) -> list[LegModel]:
    """container 에 template step 대로 leg 를 생성하고 파생상태를 갱신한다."""
    # 1) container (team scope)
    container = (await db.execute(select(ContainerModel).where(
        ContainerModel.team_id == team_id,
        ContainerModel.id == container_id,
        ContainerModel.is_active.is_(True),
    ))).scalar_one_or_none()
    if container is None:
        raise NotFoundException("컨테이너")

    # 2) template + steps
    template = (await db.execute(select(LoadTypeTemplateModel).where(
        LoadTypeTemplateModel.team_id == team_id,
        LoadTypeTemplateModel.id == template_id,
        LoadTypeTemplateModel.is_active.is_(True),
    ))).scalar_one_or_none()
    if template is None:
        raise NotFoundException("Load Type 템플릿")

    steps = list((await db.execute(select(LoadTypeTemplateStepModel).where(
        LoadTypeTemplateStepModel.team_id == team_id,
        LoadTypeTemplateStepModel.template_id == template_id,
        LoadTypeTemplateStepModel.is_active.is_(True),
    ).order_by(LoadTypeTemplateStepModel.seq.asc()))).scalars().all())
    if not steps:
        raise BadRequestException("템플릿에 step 이 없습니다.")

    # 3) 기존 leg 처리 (replace 면 진행 전 leg 만 soft-delete, 진행/완료 leg 있으면 차단)
    existing = list((await db.execute(select(LegModel).where(
        LegModel.team_id == team_id,
        LegModel.container_id == container_id,
        LegModel.is_active.is_(True),
    ))).scalars().all())
    if existing and not replace_existing:
        raise BadRequestException(
            "이미 leg 가 있는 컨테이너입니다. replace_existing=true 로 재생성하세요.",
        )
    if any(leg.status in _PROTECTED for leg in existing):
        raise BadRequestException("진행 중/완료된 leg 가 있어 재생성할 수 없습니다.")
    for leg in existing:
        leg.is_active = False
        if actor_user_id is not None:
            leg.updated_by_user_id = actor_user_id

    # 4) step → leg
    created: list[LegModel] = []
    for s in steps:
        row = LegModel(
            team_id=team_id,
            delivery_order_id=container.delivery_order_id,
            container_id=container_id,
            step=DeliveryStatus.PLANNING,
            move_type=_MOVE_MAP.get(s.move_type, MoveType.BOBTAIL),
            service_type=_SVC_MAP.get(s.service_type, ServiceType.NONE),
            from_location_type=_loc(s.from_location_type),
            to_location_type=_loc(s.to_location_type),
            move_code=_code(s.move_code),
            status=LegStatus.PENDING,
            note=s.note,
            created_by_user_id=actor_user_id,
        )
        db.add(row)
        created.append(row)
    await db.flush()
    for row in created:
        await db.refresh(row)

    # 5) 파생 — container work_state + D/O dispatch(미배차 → DISPATCHING)
    from container.state_derive import derive_and_save_state
    await derive_and_save_state(db, team_id, container_id)
    from delivery_order.state_derive import derive_do_dispatch_state
    await derive_do_dispatch_state(db, team_id, container.delivery_order_id)

    return created
