# src/customer/service.py
from __future__ import annotations
from typing import List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from customer.repository import CustomerRepository
from customer.schemas.request import (
    CustomerCreateRequest, CustomerUpdateRequest, PaginateCustomerRequest,
    CustomerBulkCreateRequest, CustomerBulkUpdateRequest, CustomerBulkDeleteRequest,
)
from customer.schemas.response import (
    CustomerResponseSchema, CustomerDeleteResponseSchema,
    CustomerBulkCreateResponseSchema, CustomerBulkUpdateResponseSchema, CustomerBulkDeleteResponseSchema,
    BulkResultItem, BulkDeleteResultItem, BulkSummary,
)


class CustomerService:
    """
    Customer 비즈니스 로직

    삭제 정책:
    - 항상 소프트 삭제 (is_active=False)
    - Delta Sync에서 deleted_ids로 감지 가능
    - TODO [크론잡] 비활성 고객사 정리: is_active=False & 30일 경과 & FK 참조 없는 행 하드 삭제

    벌크 작업 정책:
    - 사전 검증 실패 → 전체 실패 (트랜잭션 롤백)
    - 생성/수정: 전체 성공 or 전체 실패
    """
    def __init__(self, db: AsyncSession, tenant_id: int):
        self.db = db
        self.repo = CustomerRepository(db, tenant_id)

    # ═══════════════════════════════════════════════════════════════
    # Create (단건)
    # ═══════════════════════════════════════════════════════════════
    
    async def create(
        self,
        payload: CustomerCreateRequest,
        actor_user_id: int | None = None,
    ) -> CustomerResponseSchema:
        row = await self.repo.create(
            payload.model_dump(),
            actor_user_id=actor_user_id,
        )
        return CustomerResponseSchema.model_validate(row)

    # ═══════════════════════════════════════════════════════════════
    # Create (벌크) - 전체 성공 or 전체 실패
    # ═══════════════════════════════════════════════════════════════
    
    async def create_bulk(
        self,
        payload: CustomerBulkCreateRequest,
        actor_user_id: int | None = None,
    ) -> CustomerBulkCreateResponseSchema:
        """
        고객사 벌크 생성 - 전체 성공 or 전체 실패
        
        - 하나라도 실패하면 전체 롤백 (get_write_db 의존성에서 자동 처리)
        - 에러 발생 시 BadRequestException으로 상세 정보 전달
        """
        results: List[BulkResultItem] = []
        
        for item in payload.items:
            row = await self.repo.create(
                item.model_dump(),
                actor_user_id=actor_user_id,
            )
            customer = CustomerResponseSchema.model_validate(row)
            results.append(BulkResultItem(
                id=customer.id,
                success=True,
                data=customer,
            ))
        
        # 여기까지 오면 전부 성공 (에러 시 예외 발생 → 전체 롤백)
        return CustomerBulkCreateResponseSchema(
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
    
    async def get(self, customer_id: int) -> CustomerResponseSchema:
        row = await self.repo.get(customer_id)
        if not row:
            raise NotFoundException("고객사")
        return CustomerResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateCustomerRequest
    ) -> CursorPaginationResult[CustomerResponseSchema]:
        """
        커서 기반 페이지네이션:
          - meta.count / meta.hasMore / data(CustomerResponseSchema[])
        """
        result = await self.repo.get_paginated(request)
        result.data = [CustomerResponseSchema.model_validate(r) for r in result.data]
        return result

    # ═══════════════════════════════════════════════════════════════
    # Delta Sync
    # ═══════════════════════════════════════════════════════════════

    async def sync_delta(self, since_str: str):
        """
        고객사 Delta Sync

        since 이후 변경된 활성 아이템 + soft-delete된 아이템 ID 반환.
        """
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)

        result.items = [
            CustomerResponseSchema.model_validate(r)
            for r in result.items
        ]
        return result

    # ═══════════════════════════════════════════════════════════════
    # Update (단건)
    # ═══════════════════════════════════════════════════════════════
    
    async def update(
        self,
        customer_id: int,
        payload: CustomerUpdateRequest,
        actor_user_id: int | None = None,
    ) -> CustomerResponseSchema:
        #  exclude_unset=True: 명시적으로 설정한 필드만 포함 (None도 포함됨)
        # - phone: null을 보내면 → {'phone': None} 포함 → DB에서 null로 업데이트
        # - phone 필드를 안 보내면 → dict에서 제외 → DB 값 유지
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(
            customer_id,
            data,
            actor_user_id=actor_user_id,
        )
        if not row:
            raise NotFoundException("고객사")
        return CustomerResponseSchema.model_validate(row)

    # ═══════════════════════════════════════════════════════════════
    # Update (벌크) - 전체 성공 or 전체 실패
    # ═══════════════════════════════════════════════════════════════
    
    async def update_bulk(
        self,
        payload: CustomerBulkUpdateRequest,
        actor_user_id: int | None = None,
    ) -> CustomerBulkUpdateResponseSchema:
        """
        고객사 벌크 수정 - 전체 성공 or 전체 실패
        
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
                f"고객사(ID={list(missing_ids)})",
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
            customer = CustomerResponseSchema.model_validate(row)
            results.append(BulkResultItem(
                id=customer.id,
                success=True,
                data=customer,
            ))
        
        # 여기까지 오면 전부 성공
        return CustomerBulkUpdateResponseSchema(
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
        customer_id: int,
        actor_user_id: int | None = None,
    ) -> CustomerDeleteResponseSchema:
        """
        고객사 삭제 (항상 소프트 삭제)

        - Delta Sync에서 deleted_ids로 다른 클라이언트에 전파됨
        - FK 참조 여부와 관계없이 항상 소프트 삭제
        """
        row = await self.repo.get(customer_id)
        if not row:
            raise NotFoundException("고객사")

        await self.repo.soft_deactivate_by_id(
            customer_id,
            actor_user_id=actor_user_id,
        )
        return CustomerDeleteResponseSchema(
            id=customer_id,
            deleted=True,
            soft_deleted=True,
        )

    # ═══════════════════════════════════════════════════════════════
    # Delete (벌크) - Savepoint 패턴
    # ═══════════════════════════════════════════════════════════════
    
    async def delete_bulk(
        self,
        payload: CustomerBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> CustomerBulkDeleteResponseSchema:
        """
        고객사 벌크 삭제 (항상 소프트 삭제)

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
                f"고객사(ID={list(missing_ids)})",
                detail={"missing_ids": list(missing_ids)},
            )

        # 2. 전체 소프트 삭제
        for customer_id in payload.ids:
            await self.repo.soft_deactivate_by_id(
                customer_id,
                actor_user_id=actor_user_id,
            )
            results.append(BulkDeleteResultItem(
                id=customer_id,
                success=True,
                soft_deleted=True,
            ))

        return CustomerBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(
                total=len(payload.ids),
                succeeded=len(results),
                failed=0,
            ),
        )