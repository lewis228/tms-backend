# src/delivery_order/service.py
from __future__ import annotations
from typing import List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from delivery_order.const.status import DeliveryStatus
from delivery_order.model import DeliveryOrderModel
from delivery_order.repository import DeliveryOrderRepository
from delivery_order.state_machine import (
    TransitionContext, assert_can_transition,
)
from leg.model import LegModel
from location.model import LocationModel
from delivery_order.schemas.request import (
    DeliveryOrderCreateRequest, DeliveryOrderUpdateRequest, PaginateDeliveryOrderRequest,
    DeliveryOrderBulkCreateRequest, DeliveryOrderBulkUpdateRequest, DeliveryOrderBulkDeleteRequest,
)
from delivery_order.schemas.response import (
    DeliveryOrderResponseSchema, DeliveryOrderDeleteResponseSchema,
    DeliveryOrderBulkCreateResponseSchema, DeliveryOrderBulkUpdateResponseSchema, DeliveryOrderBulkDeleteResponseSchema,
    BulkResultItem, BulkDeleteResultItem, BulkSummary,
)


class DeliveryOrderService:
    """
    DeliveryOrder 비즈니스 로직

    삭제 정책:
    - 항상 소프트 삭제 (is_active=False)
    - Delta Sync에서 deleted_ids로 감지 가능
    - TODO [크론잡] 비활성 거래처 정리: is_active=False & 30일 경과 & FK 참조 없는 행 하드 삭제

    벌크 작업 정책:
    - 사전 검증 실패 → 전체 실패 (트랜잭션 롤백)
    - 생성/수정: 전체 성공 or 전체 실패
    """
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = DeliveryOrderRepository(db, team_id)

    # ═══════════════════════════════════════════════════════════════
    # Create (단건)
    # ═══════════════════════════════════════════════════════════════
    
    async def create(
        self,
        payload: DeliveryOrderCreateRequest,
        actor_user_id: int | None = None,
    ) -> DeliveryOrderResponseSchema:
        row = await self.repo.create(
            payload.model_dump(),
            actor_user_id=actor_user_id,
        )
        return DeliveryOrderResponseSchema.model_validate(row)

    # ═══════════════════════════════════════════════════════════════
    # Create (벌크) - 전체 성공 or 전체 실패
    # ═══════════════════════════════════════════════════════════════
    
    async def create_bulk(
        self,
        payload: DeliveryOrderBulkCreateRequest,
        actor_user_id: int | None = None,
    ) -> DeliveryOrderBulkCreateResponseSchema:
        """
        거래처 벌크 생성 - 전체 성공 or 전체 실패
        
        - 하나라도 실패하면 전체 롤백 (get_write_db 의존성에서 자동 처리)
        - 에러 발생 시 BadRequestException으로 상세 정보 전달
        """
        results: List[BulkResultItem] = []
        
        for item in payload.items:
            row = await self.repo.create(
                item.model_dump(),
                actor_user_id=actor_user_id,
            )
            delivery_order = DeliveryOrderResponseSchema.model_validate(row)
            results.append(BulkResultItem(
                id=delivery_order.id,
                success=True,
                data=delivery_order,
            ))
        
        # 여기까지 오면 전부 성공 (에러 시 예외 발생 → 전체 롤백)
        return DeliveryOrderBulkCreateResponseSchema(
            results=results,
            summary=BulkSummary(
                total=len(payload.items),
                succeeded=len(results),
                failed=0,
            ),
        )

    # ═══════════════════════════════════════════════════════════════
    # Read
    # ═══════════════════════════════════════════════════════════════
    
    async def get(self, delivery_order_id: int) -> DeliveryOrderResponseSchema:
        row = await self.repo.get(delivery_order_id)
        if not row:
            raise NotFoundException("거래처")
        return DeliveryOrderResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateDeliveryOrderRequest
    ) -> CursorPaginationResult[DeliveryOrderResponseSchema]:
        """
        커서 기반 페이지네이션:
          - meta.count / meta.hasMore / data(DeliveryOrderResponseSchema[])
        """
        result = await self.repo.get_paginated(request)
        result.data = [DeliveryOrderResponseSchema.model_validate(r) for r in result.data]
        return result

    # ═══════════════════════════════════════════════════════════════
    # Delta Sync
    # ═══════════════════════════════════════════════════════════════

    async def sync_delta(self, since_str: str):
        """
        거래처 Delta Sync

        since 이후 변경된 활성 아이템 + soft-delete된 아이템 ID 반환.
        """
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)

        result.items = [
            DeliveryOrderResponseSchema.model_validate(r)
            for r in result.items
        ]
        return result

    # ═══════════════════════════════════════════════════════════════
    # Update (단건)
    # ═══════════════════════════════════════════════════════════════
    
    async def update(
        self,
        delivery_order_id: int,
        payload: DeliveryOrderUpdateRequest,
        actor_user_id: int | None = None,
    ) -> DeliveryOrderResponseSchema:
        #  exclude_unset=True: 명시적으로 설정한 필드만 포함 (None도 포함됨)
        # - phone: null을 보내면 → {'phone': None} 포함 → DB에서 null로 업데이트
        # - phone 필드를 안 보내면 → dict에서 제외 → DB 값 유지
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(
            delivery_order_id,
            data,
            actor_user_id=actor_user_id,
        )
        if not row:
            raise NotFoundException("거래처")
        return DeliveryOrderResponseSchema.model_validate(row)

    # ═══════════════════════════════════════════════════════════════
    # Update (벌크) - 전체 성공 or 전체 실패
    # ═══════════════════════════════════════════════════════════════
    
    async def update_bulk(
        self,
        payload: DeliveryOrderBulkUpdateRequest,
        actor_user_id: int | None = None,
    ) -> DeliveryOrderBulkUpdateResponseSchema:
        """
        거래처 벌크 수정 - 전체 성공 or 전체 실패
        
        - 사전 검증: 모든 ID 존재 확인
        - 하나라도 실패하면 전체 롤백
        """
        # 1. 사전 검증: 모든 ID 존재 확인
        request_ids = [item.id for item in payload.items]
        existing_rows = await self.repo.get_many(request_ids)
        existing_ids = {row.id for row in existing_rows}
        
        missing_ids = set(request_ids) - existing_ids
        if missing_ids:
            raise NotFoundException(
                f"거래처(ID={list(missing_ids)})",
                detail={"missing_ids": list(missing_ids)},
            )
        
        # 2. 일괄 수정
        results: List[BulkResultItem] = []
        
        for item in payload.items:
            #  exclude_unset=True 사용
            data = item.model_dump(exclude_unset=True)
            data.pop('id', None)  # id는 제외
            row = await self.repo.update(
                item.id,
                data,
                actor_user_id=actor_user_id,
            )
            delivery_order = DeliveryOrderResponseSchema.model_validate(row)
            results.append(BulkResultItem(
                id=delivery_order.id,
                success=True,
                data=delivery_order,
            ))
        
        # 여기까지 오면 전부 성공
        return DeliveryOrderBulkUpdateResponseSchema(
            results=results,
            summary=BulkSummary(
                total=len(payload.items),
                succeeded=len(results),
                failed=0,
            ),
        )

    # ═══════════════════════════════════════════════════════════════
    # Delete (단건)
    # ═══════════════════════════════════════════════════════════════
    
    async def delete(
        self,
        delivery_order_id: int,
        actor_user_id: int | None = None,
    ) -> DeliveryOrderDeleteResponseSchema:
        """
        거래처 삭제 (항상 소프트 삭제)

        - Delta Sync에서 deleted_ids로 다른 클라이언트에 전파됨
        - FK 참조 여부와 관계없이 항상 소프트 삭제
        """
        row = await self.repo.get(delivery_order_id)
        if not row:
            raise NotFoundException("거래처")

        await self.repo.soft_deactivate_by_id(
            delivery_order_id,
            actor_user_id=actor_user_id,
        )
        return DeliveryOrderDeleteResponseSchema(
            id=delivery_order_id,
            deleted=True,
            soft_deleted=True,
        )

    # ═══════════════════════════════════════════════════════════════
    # Delete (벌크) - Savepoint 패턴
    # ═══════════════════════════════════════════════════════════════
    
    async def delete_bulk(
        self,
        payload: DeliveryOrderBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> DeliveryOrderBulkDeleteResponseSchema:
        """
        거래처 벌크 삭제 (항상 소프트 삭제)

        - Delta Sync에서 deleted_ids로 다른 클라이언트에 전파됨
        - FK 참조 여부와 관계없이 항상 소프트 삭제
        """
        results: List[BulkDeleteResultItem] = []

        # 1. 사전 검증: 모든 ID 존재 확인
        existing_rows = await self.repo.get_many(payload.ids)
        existing_ids = {row.id for row in existing_rows}

        missing_ids = set(payload.ids) - existing_ids
        if missing_ids:
            raise NotFoundException(
                f"거래처(ID={list(missing_ids)})",
                detail={"missing_ids": list(missing_ids)},
            )

        # 2. 전체 소프트 삭제
        for delivery_order_id in payload.ids:
            await self.repo.soft_deactivate_by_id(
                delivery_order_id,
                actor_user_id=actor_user_id,
            )
            results.append(BulkDeleteResultItem(
                id=delivery_order_id,
                success=True,
                soft_deleted=True,
            ))

        return DeliveryOrderBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(
                total=len(payload.ids),
                succeeded=len(results),
                failed=0,
            ),
        )

    # ═══════════════════════════════════════════════════════════════
    # 상태 머신 — transition + 게이트
    # ═══════════════════════════════════════════════════════════════

    async def transition(
        self,
        delivery_order_id: int,
        target: DeliveryStatus,
        *,
        actor_user_id: int | None = None,
    ) -> DeliveryOrderResponseSchema:
        """D/O 상태 전이. 게이트는 state_machine.assert_can_transition 가 검증.

        성공 시 status 변경 + Realtime publish 트리거 (do.status_changed).
        """
        # 1) D/O 조회 (raw model — repository.get 은 schema 반환)
        team_id = self.repo._require_team()
        stmt = select(DeliveryOrderModel).where(
            DeliveryOrderModel.team_id == team_id,
            DeliveryOrderModel.id == delivery_order_id,
            DeliveryOrderModel.is_active.is_(True),
        )
        do = (await self.db.execute(stmt)).scalar_one_or_none()
        if not do:
            raise NotFoundException("D/O")

        # 2) 컨텍스트 사전 로드 — legs (오래된 순), delivery/return location
        legs_stmt = (
            select(LegModel)
            .where(
                LegModel.team_id == team_id,
                LegModel.delivery_order_id == do.id,
                LegModel.is_active.is_(True),
            )
            .order_by(LegModel.id.asc())
        )
        legs = list((await self.db.execute(legs_stmt)).scalars().all())

        delivery_loc = None
        if do.delivery_location_id:
            loc_stmt = select(LocationModel).where(
                LocationModel.team_id == team_id,
                LocationModel.id == do.delivery_location_id,
            )
            delivery_loc = (await self.db.execute(loc_stmt)).scalar_one_or_none()

        return_loc = None
        if do.return_location_id:
            loc_stmt = select(LocationModel).where(
                LocationModel.team_id == team_id,
                LocationModel.id == do.return_location_id,
            )
            return_loc = (await self.db.execute(loc_stmt)).scalar_one_or_none()

        ctx = TransitionContext(
            do=do, legs=legs,
            delivery_location=delivery_loc, return_location=return_loc,
        )

        # 3) 게이트 검증
        previous = do.status
        assert_can_transition(ctx, target)

        # 4) 적용
        do.status = target
        if actor_user_id is not None:
            do.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(do)

        # 5) Realtime publish (best-effort)
        try:
            from realtime.service import publish
            from realtime.schemas.event import RealtimeEvent
            await publish(RealtimeEvent.now(
                type="do.status_changed",
                team_id=team_id,
                actor_id=actor_user_id,
                payload={
                    "deliveryOrderId": do.id,
                    "from": previous.value,
                    "to": target.value,
                },
            ), db=self.db)
        except Exception:
            pass

        return DeliveryOrderResponseSchema.model_validate(do)
