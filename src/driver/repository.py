# src/driver/repository.py
from __future__ import annotations
from typing import Optional, List, Iterable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import load_only

from common.repository.tenant_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from driver.model import DriverModel
from driver.schemas.request import PaginateDriverRequest
from driver.schemas.response import DriverResponseSchema


class DriverRepository(TeamScopedRepoMixin):
    """
    Driver(거래처) 리포지토리
    - tenant 스코프 강제(_require_tenant)
    - 기본 is_active=True
    - take=-1 이면 전체 로드 (limit 없이 조회)
    """

    def __init__(self, db: AsyncSession, tenant_id: int | None):
        super().__init__(tenant_id)
        self.db = db
        self._common_service = CommonService()

    # ═══════════════════════════════════════════════════════════════
    # Create
    # ═══════════════════════════════════════════════════════════════
    
    async def create(
        self,
        payload: dict,
        actor_user_id: int | None = None,
    ) -> DriverModel:
        payload["tenant_id"] = self._require_tenant()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = DriverModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def create_many(
        self,
        payloads: List[dict],
        actor_user_id: int | None = None,
    ) -> List[DriverModel]:
        """
        벌크 생성 (단순 반복 - 개별 에러 처리는 Service에서)
        """
        tenant_id = self._require_tenant()
        rows = []
        for payload in payloads:
            payload["tenant_id"] = tenant_id
            if actor_user_id is not None:
                payload["created_by_user_id"] = actor_user_id
            row = DriverModel(**payload)
            self.db.add(row)
            rows.append(row)
        await self.db.flush()
        for row in rows:
            await self.db.refresh(row)
        return rows

    # ═══════════════════════════════════════════════════════════════
    # Read
    # ═══════════════════════════════════════════════════════════════
    
    async def get(self, driver_id: int) -> Optional[DriverModel]:
        """
        단건 조회(활성만) + 최소 컬럼 로딩
        """
        q = (
            select(DriverModel)
            .where(
                DriverModel.tenant_id == self._require_tenant(),
                DriverModel.id == driver_id,
                DriverModel.is_active.is_(True),
            )
            .options(
                load_only(
                    DriverModel.id,
                    DriverModel.name,
                    DriverModel.user_id,
                    DriverModel.note,
                    DriverModel.license_number,
                    DriverModel.license_state,
                    DriverModel.truck_number,
                    DriverModel.is_active,
                )
            )
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_many(self, driver_ids: List[int]) -> List[DriverModel]:
        """
        여러 건 조회 (활성만)
        - 순서 보장 안 됨, 없는 ID는 결과에서 제외
        """
        if not driver_ids:
            return []
        
        q = (
            select(DriverModel)
            .where(
                DriverModel.tenant_id == self._require_tenant(),
                DriverModel.id.in_(driver_ids),
                DriverModel.is_active.is_(True),
            )
            .options(
                load_only(
                    DriverModel.id,
                    DriverModel.name,
                    DriverModel.user_id,
                    DriverModel.note,
                    DriverModel.license_number,
                    DriverModel.license_state,
                    DriverModel.truck_number,
                    DriverModel.is_active,
                )
            )
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_paginated(self, request: PaginateDriverRequest) -> CursorPaginationResult[DriverResponseSchema]:
        """
        CommonService를 사용한 커서 기반 페이지네이션

         include_inactive:
        - False (기본): is_active=True만
        - True: 전체 (활성+비활성)

        필터: where__* → CommonService에서 처리
        """
        tenant_id = self._require_tenant()

        # 기본 쿼리 (tenant_id, 옵션에 따른 is_active)
        base_conditions = [DriverModel.tenant_id == tenant_id]
        if not request.include_inactive:
            base_conditions.append(DriverModel.is_active.is_(True))

        base_query = (
            select(DriverModel)
            .where(*base_conditions)
            .options(
                load_only(
                    DriverModel.id,
                    DriverModel.name,
                    DriverModel.user_id,
                    DriverModel.note,
                    DriverModel.license_number,
                    DriverModel.license_state,
                    DriverModel.truck_number,
                    DriverModel.is_active,
                )
            )
        )

        # CommonService로 페이지네이션
        result = await self._common_service.paginate(
            request=request,
            model=DriverModel,
            session=self.db,
            base_query=base_query,
        )

        # DTO 변환
        result.data = [DriverResponseSchema.model_validate(r) for r in result.data]

        return result

    # ═══════════════════════════════════════════════════════════════
    # Update
    # ═══════════════════════════════════════════════════════════════
    
    async def update(
        self,
        driver_id: int,
        payload: dict,
        actor_user_id: int | None = None,
    ) -> Optional[DriverModel]:
        """
        부분 업데이트 (보호 필드 무시)
        - ORM 방식 사용 (onupdate 자동 작동)
        - updated_by_user_id 명시적 설정
        - None 값도 setattr로 설정 (필드 삭제 처리)
        """
        if not payload:
            return await self.get(driver_id)

        q = (
            select(DriverModel)
            .where(
                DriverModel.tenant_id == self._require_tenant(),
                DriverModel.id == driver_id,
                DriverModel.is_active.is_(True),
            )
        )
        row = (await self.db.execute(q)).scalar_one_or_none()
        if not row:
            return None

        protected = {"id", "tenant_id", "is_active", "created_at", "created_by_user_id"}
        
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
    
    async def hard_delete_by_id(self, driver_id: int) -> None:
        """단건 하드 삭제"""
        await self.db.execute(
            delete(DriverModel).where(
                DriverModel.tenant_id == self._require_tenant(),
                DriverModel.id == driver_id,
            )
        )
        await self.db.flush()

    async def soft_deactivate_by_id(
        self,
        driver_id: int,
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
            update(DriverModel)
            .where(
                DriverModel.tenant_id == self._require_tenant(),
                DriverModel.id == driver_id,
                DriverModel.is_active.is_(True),
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
            select(DriverModel.id)
            .where(
                DriverModel.tenant_id == self._require_tenant(),
                DriverModel.is_active.is_(True),
                DriverModel.id.in_(id_list),
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
        tenant_id = self._require_tenant()

        base_query = (
            select(DriverModel)
            .where(DriverModel.tenant_id == tenant_id)
            .options(
                load_only(
                    DriverModel.id,
                    DriverModel.name,
                    DriverModel.user_id,
                    DriverModel.note,
                    DriverModel.license_number,
                    DriverModel.license_state,
                    DriverModel.truck_number,
                    DriverModel.is_active,
                )
            )
        )

        return await self._common_service.sync_delta(
            model=DriverModel,
            session=self.db,
            since=since,
            tenant_id=tenant_id,
            base_query=base_query,
            use_soft_delete=True,
        )