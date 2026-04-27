# src/customer/repository.py
from __future__ import annotations
from typing import Optional, List, Iterable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import load_only

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from customer.model import CustomerModel
from customer.schemas.request import PaginateCustomerRequest
from customer.schemas.response import CustomerResponseSchema


class CustomerRepository(TeamScopedRepoMixin):
    """
    Customer(고객사) 리포지토리
    - team 스코프 강제(_require_team)
    - 기본 is_active=True
    - take=-1 이면 전체 로드 (limit 없이 조회)
    """

    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    # ═══════════════════════════════════════════════════════════════
    # Create
    # ═══════════════════════════════════════════════════════════════
    
    async def create(
        self,
        payload: dict,
        actor_user_id: int | None = None,
    ) -> CustomerModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = CustomerModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def create_many(
        self,
        payloads: List[dict],
        actor_user_id: int | None = None,
    ) -> List[CustomerModel]:
        """
        벌크 생성 (단순 반복 - 개별 에러 처리는 Service에서)
        """
        team_id = self._require_team()
        rows = []
        for payload in payloads:
            payload["team_id"] = team_id
            if actor_user_id is not None:
                payload["created_by_user_id"] = actor_user_id
            row = CustomerModel(**payload)
            self.db.add(row)
            rows.append(row)
        await self.db.flush()
        for row in rows:
            await self.db.refresh(row)
        return rows

    # ═══════════════════════════════════════════════════════════════
    # Read
    # ═══════════════════════════════════════════════════════════════
    
    async def get(self, customer_id: int) -> Optional[CustomerModel]:
        """
        단건 조회(활성만) + 최소 컬럼 로딩
        """
        q = (
            select(CustomerModel)
            .where(
                CustomerModel.team_id == self._require_team(),
                CustomerModel.id == customer_id,
                CustomerModel.is_active.is_(True),
            )
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_many(self, customer_ids: List[int]) -> List[CustomerModel]:
        """
        여러 건 조회 (활성만)
        - 순서 보장 안 됨, 없는 ID는 결과에서 제외
        """
        if not customer_ids:
            return []
        
        q = (
            select(CustomerModel)
            .where(
                CustomerModel.team_id == self._require_team(),
                CustomerModel.id.in_(customer_ids),
                CustomerModel.is_active.is_(True),
            )
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_paginated(self, request: PaginateCustomerRequest) -> CursorPaginationResult[CustomerResponseSchema]:
        """
        CommonService를 사용한 커서 기반 페이지네이션

         include_inactive:
        - False (기본): is_active=True만
        - True: 전체 (활성+비활성)

        필터: where__* → CommonService에서 처리
        """
        team_id = self._require_team()

        # 기본 쿼리 (team_id, 옵션에 따른 is_active)
        base_conditions = [CustomerModel.team_id == team_id]
        if not request.include_inactive:
            base_conditions.append(CustomerModel.is_active.is_(True))

        base_query = (
            select(CustomerModel)
            .where(*base_conditions)
        )

        # CommonService로 페이지네이션
        result = await self._common_service.paginate(
            request=request,
            model=CustomerModel,
            session=self.db,
            base_query=base_query,
        )

        # DTO 변환
        result.data = [CustomerResponseSchema.model_validate(r) for r in result.data]

        return result

    # ═══════════════════════════════════════════════════════════════
    # Update
    # ═══════════════════════════════════════════════════════════════
    
    async def update(
        self,
        customer_id: int,
        payload: dict,
        actor_user_id: int | None = None,
    ) -> Optional[CustomerModel]:
        """
        부분 업데이트 (보호 필드 무시)
        - ORM 방식 사용 (onupdate 자동 작동)
        - updated_by_user_id 명시적 설정
        - None 값도 setattr로 설정 (필드 삭제 처리)
        """
        if not payload:
            return await self.get(customer_id)

        q = (
            select(CustomerModel)
            .where(
                CustomerModel.team_id == self._require_team(),
                CustomerModel.id == customer_id,
                CustomerModel.is_active.is_(True),
            )
        )
        row = (await self.db.execute(q)).scalar_one_or_none()
        if not row:
            return None

        protected = {"id", "team_id", "is_active", "created_at", "created_by_user_id"}
        
        for k, v in payload.items():
            if k in protected:
                continue
            setattr(row, k, v)
        
        #  updated_by_user_id 명시적 설정
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id

        await self.db.flush()
        await self.db.refresh(row)
        return row

    # ═══════════════════════════════════════════════════════════════
    # Delete
    # ═══════════════════════════════════════════════════════════════
    
    async def hard_delete_by_id(self, customer_id: int) -> None:
        """단건 하드 삭제"""
        await self.db.execute(
            delete(CustomerModel).where(
                CustomerModel.team_id == self._require_team(),
                CustomerModel.id == customer_id,
            )
        )
        await self.db.flush()

    async def soft_deactivate_by_id(
        self,
        customer_id: int,
        actor_user_id: int | None = None,
    ) -> None:
        """
        단건 소프트 삭제 (Core SQL)
        - updated_at, updated_by_user_id 명시적 설정 (Core SQL은 onupdate 안 탐)
        """
        values = {
            "is_active": False,
            "updated_at": func.utc_timestamp(),
        }
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        
        await self.db.execute(
            update(CustomerModel)
            .where(
                CustomerModel.team_id == self._require_team(),
                CustomerModel.id == customer_id,
                CustomerModel.is_active.is_(True),
            )
            .values(**values)
        )
        await self.db.flush()

    # ═══════════════════════════════════════════════════════════════
    # 존재 검증용
    # ═══════════════════════════════════════════════════════════════

    async def get_existing_active_ids(self, ids: Iterable[int]) -> set[int]:
        """주어진 ID 목록 중 실제로 존재하고 활성인 ID 집합 반환"""
        id_list = list(ids)
        if not id_list:
            return set()

        stmt = (
            select(CustomerModel.id)
            .where(
                CustomerModel.team_id == self._require_team(),
                CustomerModel.is_active.is_(True),
                CustomerModel.id.in_(id_list),
            )
        )
        result = await self.db.execute(stmt)
        return set(result.scalars().all())

    # ═══════════════════════════════════════════════════════════════
    # Delta Sync
    # ═══════════════════════════════════════════════════════════════

    async def sync_delta(self, since):
        """
        since 이후 변경된 활성/삭제 아이템 (soft-delete 도메인)

        - items: is_active=True & updated_at >= since
        - deleted_ids: is_active=False & updated_at >= since
        """
        team_id = self._require_team()

        base_query = (
            select(CustomerModel)
            .where(CustomerModel.team_id == team_id)
        )

        return await self._common_service.sync_delta(
            model=CustomerModel,
            session=self.db,
            since=since,
            team_id=team_id,
            base_query=base_query,
            use_soft_delete=True,
        )