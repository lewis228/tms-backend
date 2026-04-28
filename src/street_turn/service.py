# src/street_turn/service.py
from __future__ import annotations
from typing import List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from street_turn.repository import StreetTurnRepository
from street_turn.schemas.request import (
    StreetTurnCreateRequest, StreetTurnUpdateRequest, PaginateStreetTurnRequest,
    StreetTurnBulkCreateRequest, StreetTurnBulkUpdateRequest, StreetTurnBulkDeleteRequest,
)
from street_turn.schemas.response import (
    StreetTurnResponseSchema, StreetTurnDeleteResponseSchema,
    StreetTurnBulkCreateResponseSchema, StreetTurnBulkUpdateResponseSchema, StreetTurnBulkDeleteResponseSchema,
    BulkResultItem, BulkDeleteResultItem, BulkSummary,
)


class StreetTurnService:
    """
    StreetTurn 비즈니스 로직

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
        self.repo = StreetTurnRepository(db, team_id)

    # ═══════════════════════════════════════════════════════════════
    # Create (단건) — REQUESTED 상태로 생성 + requested_by/at 자동
    # ═══════════════════════════════════════════════════════════════

    async def create(
        self,
        payload: StreetTurnCreateRequest,
        actor_user_id: int | None = None,
    ) -> StreetTurnResponseSchema:
        from sqlalchemy import select as _select, or_
        from street_turn.const.status import StreetTurnStatus
        from street_turn.model import StreetTurnModel as _StreetTurn
        from common.exceptions.base import AppException

        # 같은 import_order_id / export_order_id 로 활성 row 가 이미 있으면 거부
        # (DB unique 제약 보강 + 친절한 에러 메시지)
        dup_q = _select(_StreetTurn.id).where(
            _StreetTurn.team_id == self.team_id,
            _StreetTurn.is_active.is_(True),
            or_(
                _StreetTurn.import_order_id == payload.import_order_id,
                _StreetTurn.export_order_id == payload.export_order_id,
            ),
        ).limit(1)
        existing = (await self.db.execute(dup_q)).scalar_one_or_none()
        if existing is not None:
            raise AppException(
                code="ERR_STREET_TURN_DUPLICATE",
                message="이미 해당 D/O 로 생성된 Street Turn 이 있습니다.",
                status_code=409,
            )

        data = payload.model_dump()
        data["status"] = StreetTurnStatus.REQUESTED
        data["requested_by"] = actor_user_id
        data["requested_at"] = datetime.utcnow()
        row = await self.repo.create(data, actor_user_id=actor_user_id)
        return StreetTurnResponseSchema.model_validate(row)

    # ═══════════════════════════════════════════════════════════════
    # 승인 / 거절 / 취소 — H-8
    # ═══════════════════════════════════════════════════════════════

    async def approve(
        self,
        id_: int,
        carrier_approval_no: str | None = None,
        actor_user_id: int | None = None,
    ) -> StreetTurnResponseSchema:
        from street_turn.const.status import StreetTurnStatus
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Street Turn")
        if row.status != StreetTurnStatus.REQUESTED:
            from common.exceptions.base import AppException
            raise AppException(
                code="ERR_STREET_TURN_INVALID_STATE",
                message=f"Cannot approve from {row.status.value}",
                status_code=422,
            )
        row.status = StreetTurnStatus.APPROVED
        row.approved_by = actor_user_id
        row.approved_at = datetime.utcnow()
        if carrier_approval_no:
            row.carrier_approval_no = carrier_approval_no
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)

        # 승인 시 container_event(STREET_TURNED) 자동 기록 (best-effort)
        if row.container_id:
            try:
                from container.model import ContainerEventModel
                from container.const.status import ContainerEventKind
                ev = ContainerEventModel(
                    team_id=self.team_id,
                    container_id=row.container_id,
                    event_kind=ContainerEventKind.STREET_TURNED,
                    occurred_at=row.approved_at,
                    note=f"Street turn approved (carrier_approval_no={row.carrier_approval_no or 'N/A'})",
                    created_by_user_id=actor_user_id,
                )
                self.db.add(ev)
                await self.db.flush()
            except Exception:
                pass
        return StreetTurnResponseSchema.model_validate(row)

    async def reject(
        self,
        id_: int,
        reason: str,
        actor_user_id: int | None = None,
    ) -> StreetTurnResponseSchema:
        from street_turn.const.status import StreetTurnStatus
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Street Turn")
        if row.status != StreetTurnStatus.REQUESTED:
            from common.exceptions.base import AppException
            raise AppException(
                code="ERR_STREET_TURN_INVALID_STATE",
                message=f"Cannot reject from {row.status.value}",
                status_code=422,
            )
        row.status = StreetTurnStatus.REJECTED
        row.rejected_reason = reason
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return StreetTurnResponseSchema.model_validate(row)

    async def cancel(
        self,
        id_: int,
        actor_user_id: int | None = None,
    ) -> StreetTurnResponseSchema:
        from street_turn.const.status import StreetTurnStatus
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Street Turn")
        row.status = StreetTurnStatus.CANCELLED
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return StreetTurnResponseSchema.model_validate(row)

    # ═══════════════════════════════════════════════════════════════
    # 추천 후보 (H-11) — 매칭 가능한 IMPORT 컨테이너 X EXPORT D/O
    # ═══════════════════════════════════════════════════════════════

    async def candidates(self, limit: int = 20):
        """
        Street Turn 후보 추천:
        - 활성/요청/거절 상태가 아닌 컨테이너의 IMPORT D/O × open EXPORT D/O
        - 같은 customer / 같은 size 우선
        """
        from decimal import Decimal as _Decimal
        from sqlalchemy import select as _select, and_, or_, not_
        from delivery_order.const.status import DeliveryStatus, ShipmentDirection
        from delivery_order.model import DeliveryOrderModel
        from container.model import ContainerModel
        from street_turn.const.status import StreetTurnStatus
        from street_turn.model import StreetTurnModel
        from street_turn.schemas.candidates import (
            StreetTurnCandidate, StreetTurnCandidatesResponse,
        )

        SAVING_PER_TURN = _Decimal("155.00")

        # unique constraint 가 status 와 무관하게 적용되므로 활성 row 면 모두 제외
        used_imp = (await self.db.execute(
            _select(StreetTurnModel.import_order_id).where(
                StreetTurnModel.team_id == self.team_id,
                StreetTurnModel.is_active.is_(True),
            )
        )).scalars().all()
        used_exp = (await self.db.execute(
            _select(StreetTurnModel.export_order_id).where(
                StreetTurnModel.team_id == self.team_id,
                StreetTurnModel.is_active.is_(True),
            )
        )).scalars().all()

        # 후보 IMPORT 컨테이너 (미완료, 기존 street_turn 에 묶이지 않은 D/O)
        imp_q = (
            _select(
                ContainerModel.id.label("container_id"),
                ContainerModel.container_number,
                ContainerModel.size,
                DeliveryOrderModel.id.label("do_id"),
                DeliveryOrderModel.customer_id,
                DeliveryOrderModel.terminal_id,
            )
            .select_from(ContainerModel)
            .join(DeliveryOrderModel,
                  DeliveryOrderModel.id == ContainerModel.delivery_order_id)
            .where(
                ContainerModel.team_id == self.team_id,
                ContainerModel.is_active.is_(True),
                ContainerModel.status != DeliveryStatus.COMPLETED,
                DeliveryOrderModel.direction == ShipmentDirection.IMPORT,
                DeliveryOrderModel.is_active.is_(True),
                not_(DeliveryOrderModel.id.in_(used_imp)) if used_imp else True,
            )
        )
        imp_rows = (await self.db.execute(imp_q)).all()

        # 후보 EXPORT D/O (open, 기존 street_turn 에 묶이지 않음)
        exp_q = (
            _select(
                DeliveryOrderModel.id,
                DeliveryOrderModel.customer_id,
                DeliveryOrderModel.terminal_id,
            )
            .where(
                DeliveryOrderModel.team_id == self.team_id,
                DeliveryOrderModel.is_active.is_(True),
                DeliveryOrderModel.direction == ShipmentDirection.EXPORT,
                DeliveryOrderModel.status != DeliveryStatus.COMPLETED,
                not_(DeliveryOrderModel.id.in_(used_exp)) if used_exp else True,
            )
        )
        exp_rows = (await self.db.execute(exp_q)).all()

        candidates: list[StreetTurnCandidate] = []
        for ir in imp_rows:
            for er in exp_rows:
                score = 0
                if ir.customer_id == er.customer_id:
                    score += 2
                if ir.terminal_id and ir.terminal_id == er.terminal_id:
                    score += 1
                # 사이즈 정보 없으면 score=0 일 수도 → 그래도 후보로 둠
                if score <= 0:
                    continue
                candidates.append(StreetTurnCandidate(
                    import_order_id=ir.do_id,
                    export_order_id=er.id,
                    container_id=ir.container_id,
                    container_number=ir.container_number,
                    customer_id=ir.customer_id,
                    container_size=ir.size.value if ir.size else None,
                    score=score,
                    estimated_saving=SAVING_PER_TURN,
                ))

        # score 내림차순 → limit
        candidates.sort(key=lambda c: c.score, reverse=True)
        truncated = candidates[: max(1, min(limit, 100))]
        return StreetTurnCandidatesResponse(
            candidates=truncated,
            total=len(candidates),
            saving_per_turn=SAVING_PER_TURN,
        )

    # ═══════════════════════════════════════════════════════════════
    # Create (벌크) - 전체 성공 or 전체 실패
    # ═══════════════════════════════════════════════════════════════
    
    async def create_bulk(
        self,
        payload: StreetTurnBulkCreateRequest,
        actor_user_id: int | None = None,
    ) -> StreetTurnBulkCreateResponseSchema:
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
            street_turn = StreetTurnResponseSchema.model_validate(row)
            results.append(BulkResultItem(
                id=street_turn.id,
                success=True,
                data=street_turn,
            ))
        
        # 여기까지 오면 전부 성공 (에러 시 예외 발생 → 전체 롤백)
        return StreetTurnBulkCreateResponseSchema(
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
    
    async def get(self, street_turn_id: int) -> StreetTurnResponseSchema:
        row = await self.repo.get(street_turn_id)
        if not row:
            raise NotFoundException("거래처")
        return StreetTurnResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateStreetTurnRequest
    ) -> CursorPaginationResult[StreetTurnResponseSchema]:
        """
        커서 기반 페이지네이션:
          - meta.count / meta.hasMore / data(StreetTurnResponseSchema[])
        """
        result = await self.repo.get_paginated(request)
        result.data = [StreetTurnResponseSchema.model_validate(r) for r in result.data]
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
            StreetTurnResponseSchema.model_validate(r)
            for r in result.items
        ]
        return result

    # ═══════════════════════════════════════════════════════════════
    # Update (단건)
    # ═══════════════════════════════════════════════════════════════
    
    async def update(
        self,
        street_turn_id: int,
        payload: StreetTurnUpdateRequest,
        actor_user_id: int | None = None,
    ) -> StreetTurnResponseSchema:
        #  exclude_unset=True: 명시적으로 설정한 필드만 포함 (None도 포함됨)
        # - phone: null을 보내면 → {'phone': None} 포함 → DB에서 null로 업데이트
        # - phone 필드를 안 보내면 → dict에서 제외 → DB 값 유지
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(
            street_turn_id,
            data,
            actor_user_id=actor_user_id,
        )
        if not row:
            raise NotFoundException("거래처")
        return StreetTurnResponseSchema.model_validate(row)

    # ═══════════════════════════════════════════════════════════════
    # Update (벌크) - 전체 성공 or 전체 실패
    # ═══════════════════════════════════════════════════════════════
    
    async def update_bulk(
        self,
        payload: StreetTurnBulkUpdateRequest,
        actor_user_id: int | None = None,
    ) -> StreetTurnBulkUpdateResponseSchema:
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
            street_turn = StreetTurnResponseSchema.model_validate(row)
            results.append(BulkResultItem(
                id=street_turn.id,
                success=True,
                data=street_turn,
            ))
        
        # 여기까지 오면 전부 성공
        return StreetTurnBulkUpdateResponseSchema(
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
        street_turn_id: int,
        actor_user_id: int | None = None,
    ) -> StreetTurnDeleteResponseSchema:
        """
        거래처 삭제 (항상 소프트 삭제)

        - Delta Sync에서 deleted_ids로 다른 클라이언트에 전파됨
        - FK 참조 여부와 관계없이 항상 소프트 삭제
        """
        row = await self.repo.get(street_turn_id)
        if not row:
            raise NotFoundException("거래처")

        await self.repo.soft_deactivate_by_id(
            street_turn_id,
            actor_user_id=actor_user_id,
        )
        return StreetTurnDeleteResponseSchema(
            id=street_turn_id,
            deleted=True,
            soft_deleted=True,
        )

    # ═══════════════════════════════════════════════════════════════
    # Delete (벌크) - Savepoint 패턴
    # ═══════════════════════════════════════════════════════════════
    
    async def delete_bulk(
        self,
        payload: StreetTurnBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> StreetTurnBulkDeleteResponseSchema:
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
        for street_turn_id in payload.ids:
            await self.repo.soft_deactivate_by_id(
                street_turn_id,
                actor_user_id=actor_user_id,
            )
            results.append(BulkDeleteResultItem(
                id=street_turn_id,
                success=True,
                soft_deleted=True,
            ))

        return StreetTurnBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(
                total=len(payload.ids),
                succeeded=len(results),
                failed=0,
            ),
        )