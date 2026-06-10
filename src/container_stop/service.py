# src/container_stop/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, BadRequestException
from container_stop.repository import ContainerStopRepository
from container_stop.schemas.request import (
    ContainerStopCreateRequest, ContainerStopUpdateRequest,
    PaginateContainerStopRequest,
)
from container.schemas.response import StopResponseSchema
from leg.const.status import PointType


# point_type 별로 채워야 하는 마스터 FK
_TYPE_FK = {
    PointType.TERMINAL: "terminal_id",
    PointType.YARD: "location_id",
    PointType.CUSTOMER: "customer_id",
}


def assert_valid_point(point_type: PointType, terminal_id, location_id, customer_id) -> None:
    """point_type 에 맞는 마스터 FK 가 정확히 하나만 채워졌는지 검증."""
    required = _TYPE_FK[point_type]
    fks = {"terminal_id": terminal_id, "location_id": location_id, "customer_id": customer_id}
    if fks[required] is None:
        raise BadRequestException(
            f"point_type={point_type.value} 에는 {required} 가 필요합니다.",
            code="POINT_FK_REQUIRED",
        )
    extra = [k for k, v in fks.items() if k != required and v is not None]
    if extra:
        raise BadRequestException(
            f"point_type={point_type.value} 에는 {required} 만 채워야 합니다(불필요: {extra}).",
            code="POINT_FK_CONFLICT",
        )


class ContainerStopService:
    """v3 ContainerStop CRUD."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = ContainerStopRepository(db, team_id)

    async def create(
        self, payload: ContainerStopCreateRequest, actor_user_id: int | None = None,
    ) -> StopResponseSchema:
        from realtime.v3_publish import safe_publish, EVT_CONTAINER_STOP_CREATED
        from container.state_derive import derive_and_save_state
        data = payload.model_dump()
        assert_valid_point(
            payload.point_type, payload.terminal_id, payload.location_id, payload.customer_id,
        )
        if data.get("sequence_no") is None:
            data["sequence_no"] = await self.repo.next_sequence_no(data["container_id"])
        row = await self.repo.create(data, actor_user_id=actor_user_id)
        await derive_and_save_state(self.db, self.team_id, row.container_id)
        await safe_publish(
            type=EVT_CONTAINER_STOP_CREATED, team_id=self.team_id, actor_id=actor_user_id,
            payload={"stop_id": row.id, "container_id": row.container_id, "sequence_no": row.sequence_no, "point_type": row.point_type.value},
        )
        return StopResponseSchema.model_validate(row)

    async def get(self, id_: int) -> StopResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Stop")
        return StopResponseSchema.model_validate(row)

    async def list_by_container(self, container_id: int) -> List[StopResponseSchema]:
        rows = await self.repo.list_by_container(container_id)
        return [StopResponseSchema.model_validate(r) for r in rows]

    async def update(
        self, id_: int, payload: ContainerStopUpdateRequest, actor_user_id: int | None = None,
    ) -> StopResponseSchema:
        from realtime.v3_publish import safe_publish, EVT_CONTAINER_STOP_UPDATED
        from container.state_derive import derive_and_save_state
        data = payload.model_dump(exclude_unset=True)
        existing = await self.repo.get(id_)
        if not existing:
            raise NotFoundException("Stop")
        # 타입 변경 시 마스터 FK 를 payload 기준으로 전체 재지정(미지정은 None)
        if "point_type" in data:
            full = payload.model_dump()
            data["terminal_id"] = full["terminal_id"]
            data["location_id"] = full["location_id"]
            data["customer_id"] = full["customer_id"]
        merged_type = data.get("point_type", existing.point_type)
        assert_valid_point(
            merged_type,
            data.get("terminal_id", existing.terminal_id),
            data.get("location_id", existing.location_id),
            data.get("customer_id", existing.customer_id),
        )
        row = await self.repo.update(id_, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("Stop")
        await derive_and_save_state(self.db, self.team_id, row.container_id)
        await safe_publish(
            type=EVT_CONTAINER_STOP_UPDATED, team_id=self.team_id, actor_id=actor_user_id,
            payload={"stop_id": row.id, "container_id": row.container_id},
        )
        return StopResponseSchema.model_validate(row)

    async def reorder(
        self, container_id: int, items: list[dict], actor_user_id: int | None = None,
    ) -> list[StopResponseSchema]:
        """drag&drop reorder — sequence_no 일괄 갱신.

        2-step: 모든 stop 의 sequence_no 를 큰 음수로 이동 → 새 값으로 적용.
        UNIQUE(container_id, sequence_no) 충돌 방지.
        """
        from sqlalchemy import update
        from container_stop.model import ContainerStopModel
        from realtime.v3_publish import safe_publish, EVT_CONTAINER_STOP_UPDATED
        from container.state_derive import derive_and_save_state

        ids = [it["stop_id"] for it in items]
        if not ids:
            return []
        # 1) 일시적으로 음수로 이동
        for offset, it in enumerate(items):
            await self.db.execute(
                update(ContainerStopModel)
                .where(
                    ContainerStopModel.team_id == self.team_id,
                    ContainerStopModel.container_id == container_id,
                    ContainerStopModel.id == it["stop_id"],
                )
                .values(sequence_no=-(10000 + offset))
            )
        await self.db.flush()
        # 2) 실제 값으로 적용
        for it in items:
            await self.db.execute(
                update(ContainerStopModel)
                .where(
                    ContainerStopModel.team_id == self.team_id,
                    ContainerStopModel.container_id == container_id,
                    ContainerStopModel.id == it["stop_id"],
                )
                .values(
                    sequence_no=it["sequence_no"],
                    updated_by_user_id=actor_user_id,
                )
            )
        await self.db.flush()
        rows = await self.repo.list_by_container(container_id)
        await derive_and_save_state(self.db, self.team_id, container_id)
        await safe_publish(
            type=EVT_CONTAINER_STOP_UPDATED, team_id=self.team_id, actor_id=actor_user_id,
            payload={"container_id": container_id, "reordered": True},
        )
        return [StopResponseSchema.model_validate(r) for r in rows]

    async def delete(self, id_: int, actor_user_id: int | None = None) -> bool:
        from realtime.v3_publish import safe_publish, EVT_CONTAINER_STOP_DELETED
        from container.state_derive import derive_and_save_state
        row = await self.repo.get(id_)
        cid = row.container_id if row else None
        await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
        if cid is not None:
            await derive_and_save_state(self.db, self.team_id, cid)
        await safe_publish(
            type=EVT_CONTAINER_STOP_DELETED, team_id=self.team_id, actor_id=actor_user_id,
            payload={"stop_id": id_, "container_id": cid},
        )
        return True
