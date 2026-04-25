from __future__ import annotations
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from ocean.container.model import ContainerModel
from ocean.container.repository import ContainerRepository
from ocean.container.schemas.request import PaginateContainerRequestSchema
from ocean.container.schemas.response import (
    ContainerListRowResponseSchema,
    ContainerResponseSchema,
)
from ocean.shipment.model import ShipmentModel
from common.exceptions.base import NotFoundException


class ContainerService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = ContainerRepository(db, team_id)
        self.pagination = CommonService()

    async def get_container(self, container_id: int) -> ContainerResponseSchema:
        container = await self.repo.get_by_id(container_id)
        if not container:
            raise NotFoundException("Container")
        return ContainerResponseSchema.model_validate(container)

    async def get_by_number(self, number: str) -> ContainerResponseSchema:
        container = await self.repo.get_by_number(number)
        if not container:
            raise NotFoundException("Container")
        return ContainerResponseSchema.model_validate(container)

    async def list_by_shipment(self, shipment_id: int) -> list[ContainerResponseSchema]:
        containers = await self.repo.list_by_shipment(shipment_id)
        return [ContainerResponseSchema.model_validate(c) for c in containers]

    async def list_containers_paginated(
        self, request: PaginateContainerRequestSchema,
    ) -> CursorPaginationResult[ContainerListRowResponseSchema]:
        """팀 전역 컨테이너 목록 — Terminal49 스타일 Containers 페이지용.

        필터 전략:
            - number / mbl i_like: raw LIKE 조인. generic pagination 은
              ContainerModel 컬럼만 인식하므로 mbl 필터는 여기서 수동 주입.
            - physical_status / size_type_code / carrier_id equal: 직접 컬럼 필터.

        Shipment 조인으로 carrier / pol / pod / eta 정보까지 한 번에 로드.
        """
        base_query = self.repo.base_list_query_with_shipment()

        # mbl 은 ContainerModel 컬럼이 아니라 Shipment 조인 — 수동 주입.
        if request.where__mbl__i_like:
            pattern = f"%{request.where__mbl__i_like.strip().lower()}%"
            base_query = base_query.where(
                func.lower(ShipmentModel.mbl).like(pattern)
            )
        # carrier_id 도 shipment 쪽 컬럼이므로 수동.
        if request.where__carrier_id__equal is not None:
            base_query = base_query.where(
                ShipmentModel.carrier_id == request.where__carrier_id__equal
            )

        result = await self.pagination.paginate(
            request=request,
            model=ContainerModel,
            session=self.db,
            base_query=base_query,
            path="api/v1/ocean/containers",
        )
        # 각 container row 를 flattened nested 스키마로 변환.
        rows: list[ContainerListRowResponseSchema] = []
        for c in result.data:
            row = ContainerListRowResponseSchema.model_validate(
                {
                    "id": c.id,
                    "shipment_id": c.shipment_id,
                    "number": c.number,
                    "size_type": c.size_type,
                    "size_type_code": c.size_type_code,
                    "status": c.status,
                    "physical_status": c.physical_status,
                    "terminal_location": c.terminal_location,
                    "lfd": c.lfd,
                    "mbl": c.shipment.mbl if c.shipment else "",
                    "carrier": c.shipment.carrier if c.shipment else None,
                    "pol_location": c.shipment.pol_location if c.shipment else None,
                    "pod_location": c.shipment.pod_location if c.shipment else None,
                    "eta": c.shipment.eta if c.shipment else None,
                }
            )
            rows.append(row)
        result.data = rows
        return result
