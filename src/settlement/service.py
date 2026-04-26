# src/settlement/service.py
from __future__ import annotations
from typing import List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, BadRequestException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from settlement.repository import SettlementRepository
from settlement.schemas.request import (
    SettlementCreateRequest, SettlementUpdateRequest, PaginateSettlementRequest,
    SettlementBulkCreateRequest, SettlementBulkUpdateRequest, SettlementBulkDeleteRequest,
)
from settlement.schemas.response import (
    SettlementResponseSchema, SettlementDeleteResponseSchema,
    SettlementBulkCreateResponseSchema, SettlementBulkUpdateResponseSchema, SettlementBulkDeleteResponseSchema,
    BulkResultItem, BulkDeleteResultItem, BulkSummary,
)


class SettlementService:
    """
    Settlement 비즈니스 로직

    삭제 정책:
    - 항상 소프트 삭제 (is_active=False)
    - Delta Sync에서 deleted_ids로 감지 가능
    - TODO [크론잡] 비활성 거래처 정리: is_active=False & 30일 경과 & FK 참조 없는 행 하드 삭제

    벌크 작업 정책:
    - 사전 검증 실패 → 전체 실패 (트랜잭션 롤백)
    - 생성/수정: 전체 성공 or 전체 실패
    """
    def __init__(self, db: AsyncSession, tenant_id: int):
        self.db = db
        self.repo = SettlementRepository(db, tenant_id)

    # ═══════════════════════════════════════════════════════════════
    # Create (단건)
    # ═══════════════════════════════════════════════════════════════
    
    async def create(
        self,
        payload: SettlementCreateRequest,
        actor_user_id: int | None = None,
    ) -> SettlementResponseSchema:
        row = await self.repo.create(
            payload.model_dump(),
            actor_user_id=actor_user_id,
        )
        return SettlementResponseSchema.model_validate(row)

    # ═══════════════════════════════════════════════════════════════
    # Create (벌크) - 전체 성공 or 전체 실패
    # ═══════════════════════════════════════════════════════════════
    
    async def create_bulk(
        self,
        payload: SettlementBulkCreateRequest,
        actor_user_id: int | None = None,
    ) -> SettlementBulkCreateResponseSchema:
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
            settlement = SettlementResponseSchema.model_validate(row)
            results.append(BulkResultItem(
                id=settlement.id,
                success=True,
                data=settlement,
            ))
        
        # 여기까지 오면 전부 성공 (에러 시 예외 발생 → 전체 롤백)
        return SettlementBulkCreateResponseSchema(
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
    
    async def get(self, settlement_id: int) -> SettlementResponseSchema:
        row = await self.repo.get(settlement_id)
        if not row:
            raise NotFoundException("거래처")
        return SettlementResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateSettlementRequest
    ) -> CursorPaginationResult[SettlementResponseSchema]:
        """
        커서 기반 페이지네이션:
          - meta.count / meta.hasMore / data(SettlementResponseSchema[])
        """
        result = await self.repo.get_paginated(request)
        result.data = [SettlementResponseSchema.model_validate(r) for r in result.data]
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
            SettlementResponseSchema.model_validate(r)
            for r in result.items
        ]
        return result

    # ═══════════════════════════════════════════════════════════════
    # Update (단건)
    # ═══════════════════════════════════════════════════════════════
    
    async def update(
        self,
        settlement_id: int,
        payload: SettlementUpdateRequest,
        actor_user_id: int | None = None,
    ) -> SettlementResponseSchema:
        #  exclude_unset=True: 명시적으로 설정한 필드만 포함 (None도 포함됨)
        # - phone: null을 보내면 → {'phone': None} 포함 → DB에서 null로 업데이트
        # - phone 필드를 안 보내면 → dict에서 제외 → DB 값 유지
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(
            settlement_id,
            data,
            actor_user_id=actor_user_id,
        )
        if not row:
            raise NotFoundException("거래처")
        return SettlementResponseSchema.model_validate(row)

    # ═══════════════════════════════════════════════════════════════
    # Update (벌크) - 전체 성공 or 전체 실패
    # ═══════════════════════════════════════════════════════════════
    
    async def update_bulk(
        self,
        payload: SettlementBulkUpdateRequest,
        actor_user_id: int | None = None,
    ) -> SettlementBulkUpdateResponseSchema:
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
            settlement = SettlementResponseSchema.model_validate(row)
            results.append(BulkResultItem(
                id=settlement.id,
                success=True,
                data=settlement,
            ))
        
        # 여기까지 오면 전부 성공
        return SettlementBulkUpdateResponseSchema(
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
        settlement_id: int,
        actor_user_id: int | None = None,
    ) -> SettlementDeleteResponseSchema:
        """
        거래처 삭제 (항상 소프트 삭제)

        - Delta Sync에서 deleted_ids로 다른 클라이언트에 전파됨
        - FK 참조 여부와 관계없이 항상 소프트 삭제
        """
        row = await self.repo.get(settlement_id)
        if not row:
            raise NotFoundException("거래처")

        await self.repo.soft_deactivate_by_id(
            settlement_id,
            actor_user_id=actor_user_id,
        )
        return SettlementDeleteResponseSchema(
            id=settlement_id,
            deleted=True,
            soft_deleted=True,
        )

    # ═══════════════════════════════════════════════════════════════
    # Delete (벌크) - Savepoint 패턴
    # ═══════════════════════════════════════════════════════════════
    
    async def delete_bulk(
        self,
        payload: SettlementBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> SettlementBulkDeleteResponseSchema:
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
        for settlement_id in payload.ids:
            await self.repo.soft_deactivate_by_id(
                settlement_id,
                actor_user_id=actor_user_id,
            )
            results.append(BulkDeleteResultItem(
                id=settlement_id,
                success=True,
                soft_deleted=True,
            ))

        return SettlementBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(
                total=len(payload.ids),
                succeeded=len(results),
                failed=0,
            ),
        )