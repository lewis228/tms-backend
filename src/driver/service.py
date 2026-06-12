# src/driver/service.py
from __future__ import annotations
import secrets
from typing import List
from datetime import datetime

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import ConflictException, NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from team.model import UserTeamModel
from user.const.roles import RolesEnum
from user.model import UserModel
from driver.repository import DriverRepository
from driver.schemas.request import (
    DriverCreateRequest, DriverUpdateRequest, PaginateDriverRequest,
    DriverBulkCreateRequest, DriverBulkUpdateRequest, DriverBulkDeleteRequest,
)
from driver.schemas.response import (
    DriverResponseSchema, DriverDeleteResponseSchema,
    DriverBulkCreateResponseSchema, DriverBulkUpdateResponseSchema, DriverBulkDeleteResponseSchema,
    BulkResultItem, BulkDeleteResultItem, BulkSummary,
)


class DriverService:
    """
    Driver 비즈니스 로직

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
        self.team_id = team_id
        self.repo = DriverRepository(db, team_id)

    # ═══════════════════════════════════════════════════════════════
    # User 연결 (email/name/phone 은 user 테이블 소유)
    # ═══════════════════════════════════════════════════════════════

    async def _get_or_create_driver_user(
        self, email: str, name: str, phone: str | None
    ) -> UserModel:
        """기사 생성 시 user 확보: 활성 이메일 유저 재사용 또는 신규 생성 + 팀 멤버십 보장.

        - 신규 user 는 role=DRIVER, 임의 비밀번호(모바일은 phone+OTP 로그인 — 비밀번호 미사용).
        - 멤버십은 permission_group_id=None (driver 는 role 가드로 제어 — 시드와 동일).
        """
        email_lower = email.lower()
        user = (await self.db.execute(
            select(UserModel).where(
                UserModel.email == email_lower,
                UserModel.is_active.is_(True),
            )
        )).scalar_one_or_none()

        if user is None:
            pw_hash = bcrypt.hashpw(secrets.token_urlsafe(24).encode(), bcrypt.gensalt()).decode()
            user = UserModel.create_email_user(email=email, password_hash=pw_hash, name=name)
            user.role = RolesEnum.DRIVER
            if phone:
                user.phone = phone
            self.db.add(user)
            await self.db.flush()
        else:
            # 기존 유저 재사용 — 비어 있는 프로필만 보충 (기존 값 덮어쓰지 않음)
            if not user.name:
                user.name = name
            if phone and not user.phone:
                user.phone = phone

        membership = (await self.db.execute(
            select(UserTeamModel).where(
                UserTeamModel.user_id == user.id,
                UserTeamModel.team_id == self.team_id,
            )
        )).scalar_one_or_none()
        if membership is None:
            self.db.add(UserTeamModel(user_id=user.id, team_id=self.team_id, permission_group_id=None))
            await self.db.flush()

        return user

    async def _create_one(
        self, payload: DriverCreateRequest, actor_user_id: int | None
    ) -> DriverResponseSchema:
        data = payload.model_dump()
        # user 소유 필드 분리 — DriverModel 컬럼이 아니라 그대로 넘기면 TypeError
        email = data.pop("email")
        name = data.pop("name")
        phone = data.pop("phone", None)

        user = await self._get_or_create_driver_user(email, name, phone)
        if await self.repo.get_active_by_user_id(user.id):
            raise ConflictException(f"이미 이 팀에 등록된 기사입니다. (email={email})")

        data["user_id"] = user.id
        row = await self.repo.create(data, actor_user_id=actor_user_id)
        out = DriverResponseSchema.model_validate(row)
        await self._enrich_user_info([out])
        return out

    # ═══════════════════════════════════════════════════════════════
    # Create (단건)
    # ═══════════════════════════════════════════════════════════════

    async def create(
        self,
        payload: DriverCreateRequest,
        actor_user_id: int | None = None,
    ) -> DriverResponseSchema:
        return await self._create_one(payload, actor_user_id)

    # ═══════════════════════════════════════════════════════════════
    # Create (벌크) - 전체 성공 or 전체 실패
    # ═══════════════════════════════════════════════════════════════

    async def create_bulk(
        self,
        payload: DriverBulkCreateRequest,
        actor_user_id: int | None = None,
    ) -> DriverBulkCreateResponseSchema:
        """
        기사 벌크 생성 - 전체 성공 or 전체 실패

        - 하나라도 실패하면 전체 롤백 (get_write_db 의존성에서 자동 처리)
        - 에러 발생 시 BadRequestException으로 상세 정보 전달
        """
        results: List[BulkResultItem] = []

        for item in payload.items:
            driver = await self._create_one(item, actor_user_id)
            results.append(BulkResultItem(
                id=driver.id,
                success=True,
                data=driver,
            ))

        # 여기까지 오면 전부 성공 (에러 시 예외 발생 → 전체 롤백)
        return DriverBulkCreateResponseSchema(
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
    
    async def _enrich_user_info(
        self, schemas: List[DriverResponseSchema]
    ) -> List[DriverResponseSchema]:
        """name/email/phone 은 driver 컬럼이 아니라 연결된 user 의 값 — 응답에 채워넣는다.

        (미적용 시 모든 기사 픽커/목록에 이름이 null 로 나옴.)
        """
        ids = [s.user_id for s in schemas if s.user_id is not None]
        if not ids:
            return schemas
        info = await self.repo.get_user_info_map(ids)
        for s in schemas:
            name, email, phone = info.get(s.user_id, (None, None, None))
            s.name = name
            s.email = email
            s.phone = phone
        return schemas

    async def _update_user_fields(self, user_id: int, fields: dict) -> None:
        """name/phone 수정은 user 테이블에 반영 — driver 에 setattr 하면 조용히 유실된다."""
        user = (await self.db.execute(
            select(UserModel).where(UserModel.id == user_id)
        )).scalar_one_or_none()
        if user is None:
            return
        for k, v in fields.items():
            setattr(user, k, v)
        await self.db.flush()

    async def get(self, driver_id: int) -> DriverResponseSchema:
        row = await self.repo.get(driver_id)
        if not row:
            raise NotFoundException("거래처")
        out = DriverResponseSchema.model_validate(row)
        await self._enrich_user_info([out])
        return out

    async def list_paginated(
        self, request: PaginateDriverRequest
    ) -> CursorPaginationResult[DriverResponseSchema]:
        """
        커서 기반 페이지네이션:
          - meta.count / meta.hasMore / data(DriverResponseSchema[])
        """
        result = await self.repo.get_paginated(request)
        # repo 가 이미 DriverResponseSchema 로 변환 — user name/email 만 enrich
        result.data = await self._enrich_user_info(list(result.data))
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

        result.items = await self._enrich_user_info([
            DriverResponseSchema.model_validate(r)
            for r in result.items
        ])
        return result

    # ═══════════════════════════════════════════════════════════════
    # Update (단건)
    # ═══════════════════════════════════════════════════════════════
    
    async def update(
        self,
        driver_id: int,
        payload: DriverUpdateRequest,
        actor_user_id: int | None = None,
    ) -> DriverResponseSchema:
        #  exclude_unset=True: 명시적으로 설정한 필드만 포함 (None도 포함됨)
        # - phone: null을 보내면 → {'phone': None} 포함 → DB에서 null로 업데이트
        # - phone 필드를 안 보내면 → dict에서 제외 → DB 값 유지
        data = payload.model_dump(exclude_unset=True)
        # name/phone 은 user 소유 — driver 컬럼이 아니라서 분리 저장해야 한다
        user_fields = {k: data.pop(k) for k in ("name", "phone") if k in data}
        row = await self.repo.update(
            driver_id,
            data,
            actor_user_id=actor_user_id,
        )
        if not row:
            raise NotFoundException("기사")
        if user_fields:
            await self._update_user_fields(row.user_id, user_fields)
        out = DriverResponseSchema.model_validate(row)
        await self._enrich_user_info([out])
        return out

    # ═══════════════════════════════════════════════════════════════
    # Update (벌크) - 전체 성공 or 전체 실패
    # ═══════════════════════════════════════════════════════════════
    
    async def update_bulk(
        self,
        payload: DriverBulkUpdateRequest,
        actor_user_id: int | None = None,
    ) -> DriverBulkUpdateResponseSchema:
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
            # name/phone 은 user 소유 — 분리 저장 (단건 update 와 동일)
            user_fields = {k: data.pop(k) for k in ("name", "phone") if k in data}
            row = await self.repo.update(
                item.id,
                data,
                actor_user_id=actor_user_id,
            )
            if user_fields:
                await self._update_user_fields(row.user_id, user_fields)
            driver = DriverResponseSchema.model_validate(row)
            await self._enrich_user_info([driver])
            results.append(BulkResultItem(
                id=driver.id,
                success=True,
                data=driver,
            ))
        
        # 여기까지 오면 전부 성공
        return DriverBulkUpdateResponseSchema(
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
        driver_id: int,
        actor_user_id: int | None = None,
    ) -> DriverDeleteResponseSchema:
        """
        거래처 삭제 (항상 소프트 삭제)

        - Delta Sync에서 deleted_ids로 다른 클라이언트에 전파됨
        - FK 참조 여부와 관계없이 항상 소프트 삭제
        """
        row = await self.repo.get(driver_id)
        if not row:
            raise NotFoundException("거래처")

        await self.repo.soft_deactivate_by_id(
            driver_id,
            actor_user_id=actor_user_id,
        )
        return DriverDeleteResponseSchema(
            id=driver_id,
            deleted=True,
            soft_deleted=True,
        )

    # ═══════════════════════════════════════════════════════════════
    # Delete (벌크) - Savepoint 패턴
    # ═══════════════════════════════════════════════════════════════
    
    async def delete_bulk(
        self,
        payload: DriverBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> DriverBulkDeleteResponseSchema:
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
        for driver_id in payload.ids:
            await self.repo.soft_deactivate_by_id(
                driver_id,
                actor_user_id=actor_user_id,
            )
            results.append(BulkDeleteResultItem(
                id=driver_id,
                success=True,
                soft_deleted=True,
            ))

        return DriverBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(
                total=len(payload.ids),
                succeeded=len(results),
                failed=0,
            ),
        )