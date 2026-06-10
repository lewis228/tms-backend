# src/leg/service.py
from __future__ import annotations
from typing import List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, BadRequestException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from leg.repository import LegRepository
from leg.schemas.request import (
    LegCreateRequest, LegUpdateRequest, PaginateLegRequest,
    LegBulkCreateRequest, LegBulkUpdateRequest, LegBulkDeleteRequest,
)
from leg.schemas.response import (
    LegResponseSchema, LegDeleteResponseSchema,
    LegBulkCreateResponseSchema, LegBulkUpdateResponseSchema, LegBulkDeleteResponseSchema,
    BulkResultItem, BulkDeleteResultItem, BulkSummary,
)


class LegService:
    """
    Leg 비즈니스 로직

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
        self.repo = LegRepository(db, team_id)

    async def _snapshot_point_types(self, data: dict) -> None:
        """from_point_id/to_point_id 가 주어지면 그 포인트의 point_type 을
        from/to_location_type 으로 스냅샷한다(읽기전용 표시·가격 무관)."""
        from sqlalchemy import select
        from container_stop.model import ContainerStopModel
        for pid_key, type_key in (
            ("from_point_id", "from_location_type"),
            ("to_point_id", "to_location_type"),
        ):
            pid = data.get(pid_key)
            if pid is None:
                continue
            pt = (await self.db.execute(
                select(ContainerStopModel.point_type).where(
                    ContainerStopModel.team_id == self.team_id,
                    ContainerStopModel.id == pid,
                )
            )).scalar_one_or_none()
            if pt is not None:
                data[type_key] = pt

    async def _autofill_dest_from_point(self, data: dict) -> None:
        """to_point 마스터(terminal/location/customer)의 zip_id → zip_code 조회 →
        dest_zip/city/state 자동 스냅샷. 명시 입력값(override)은 안 덮는다.
        도착지 마스터에 zip 없으면 폴백(수동). 정산(ZONE/CITY)의 dest 입력."""
        if any(data.get(k) for k in ("dest_zip", "dest_city", "dest_state")):
            return  # override 우선
        to_pid = data.get("to_point_id")
        if to_pid is None:
            return
        from sqlalchemy import select
        from container_stop.model import ContainerStopModel
        from leg.const.status import PointType
        from zip_code.model import ZipCodeModel

        stop = (await self.db.execute(select(ContainerStopModel).where(
            ContainerStopModel.team_id == self.team_id,
            ContainerStopModel.id == to_pid,
        ))).scalar_one_or_none()
        if stop is None:
            return

        zip_id = None
        if stop.point_type == PointType.TERMINAL and stop.terminal_id:
            from terminal.model import TerminalModel
            zip_id = (await self.db.execute(select(TerminalModel.zip_id).where(
                TerminalModel.team_id == self.team_id, TerminalModel.id == stop.terminal_id,
            ))).scalar_one_or_none()
        elif stop.point_type == PointType.YARD and stop.location_id:
            from location.model import LocationModel
            zip_id = (await self.db.execute(select(LocationModel.zip_id).where(
                LocationModel.team_id == self.team_id, LocationModel.id == stop.location_id,
            ))).scalar_one_or_none()
        elif stop.point_type == PointType.CUSTOMER and stop.customer_id:
            from customer.model import CustomerModel
            zip_id = (await self.db.execute(select(CustomerModel.zip_id).where(
                CustomerModel.team_id == self.team_id, CustomerModel.id == stop.customer_id,
            ))).scalar_one_or_none()
        if not zip_id:
            return

        zc = (await self.db.execute(select(ZipCodeModel).where(ZipCodeModel.id == zip_id))).scalar_one_or_none()
        if zc is not None:
            data["dest_zip"] = zc.zip
            data["dest_city"] = zc.city
            data["dest_state"] = zc.state

    # ═══════════════════════════════════════════════════════════════
    # Create (단건)
    # ═══════════════════════════════════════════════════════════════

    async def create(
        self,
        payload: LegCreateRequest,
        actor_user_id: int | None = None,
    ) -> LegResponseSchema:
        data = payload.model_dump()
        await self._snapshot_point_types(data)
        await self._autofill_dest_from_point(data)
        row = await self.repo.create(
            data,
            actor_user_id=actor_user_id,
        )
        # 자동 hook (best-effort) — 실패 시 rollback 으로 세션 invalid 회피.
        # leg 별 요율/원가는 정산 시점에 payroll(RateResolver) 가 해석한다.
        try:
            if row.container_id is not None:
                from container.state_derive import derive_and_save_state
                await derive_and_save_state(self.db, self.team_id, row.container_id)
            # 재설계: 새 leg(미배차) → D/O DISPATCHING 자동 파생
            from delivery_order.state_derive import derive_do_dispatch_state
            await derive_do_dispatch_state(self.db, self.team_id, row.delivery_order_id)
        except Exception:  # noqa: BLE001
            try:
                await self.db.rollback()
            except Exception:  # noqa: BLE001
                pass
            raise
        return LegResponseSchema.model_validate(row)

    # ═══════════════════════════════════════════════════════════════
    # Create (벌크) - 전체 성공 or 전체 실패
    # ═══════════════════════════════════════════════════════════════
    
    async def create_bulk(
        self,
        payload: LegBulkCreateRequest,
        actor_user_id: int | None = None,
    ) -> LegBulkCreateResponseSchema:
        """
        거래처 벌크 생성 - 전체 성공 or 전체 실패
        
        - 하나라도 실패하면 전체 롤백 (get_write_db 의존성에서 자동 처리)
        - 에러 발생 시 BadRequestException으로 상세 정보 전달
        """
        results: List[BulkResultItem] = []
        
        for item in payload.items:
            data = item.model_dump()
            await self._snapshot_point_types(data)
            await self._autofill_dest_from_point(data)
            row = await self.repo.create(
                data,
                actor_user_id=actor_user_id,
            )
            leg = LegResponseSchema.model_validate(row)
            results.append(BulkResultItem(
                id=leg.id,
                success=True,
                data=leg,
            ))
        
        # 여기까지 오면 전부 성공 (에러 시 예외 발생 → 전체 롤백)
        return LegBulkCreateResponseSchema(
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
    
    async def get(self, leg_id: int) -> LegResponseSchema:
        row = await self.repo.get(leg_id)
        if not row:
            raise NotFoundException("거래처")
        return LegResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateLegRequest
    ) -> CursorPaginationResult[LegResponseSchema]:
        """
        커서 기반 페이지네이션:
          - meta.count / meta.hasMore / data(LegResponseSchema[])
        """
        result = await self.repo.get_paginated(request)
        result.data = [LegResponseSchema.model_validate(r) for r in result.data]
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
            LegResponseSchema.model_validate(r)
            for r in result.items
        ]
        return result

    # ═══════════════════════════════════════════════════════════════
    # Update (단건)
    # ═══════════════════════════════════════════════════════════════
    
    async def update(
        self,
        leg_id: int,
        payload: LegUpdateRequest,
        actor_user_id: int | None = None,
    ) -> LegResponseSchema:
        #  exclude_unset=True: 명시적으로 설정한 필드만 포함 (None도 포함됨)
        # - phone: null을 보내면 → {'phone': None} 포함 → DB에서 null로 업데이트
        # - phone 필드를 안 보내면 → dict에서 제외 → DB 값 유지
        data = payload.model_dump(exclude_unset=True)
        await self._snapshot_point_types(data)
        # to_point_id 가 바뀌면 dest 도 자동 갱신(명시 dest override 우선).
        # helper 는 data 에 to_point_id 가 있을 때만 동작 → 다른 필드만 수정 시 무영향.
        await self._autofill_dest_from_point(data)
        row = await self.repo.update(
            leg_id,
            data,
            actor_user_id=actor_user_id,
        )
        if not row:
            raise NotFoundException("거래처")
        # v3: container.work_state 자동 derive (status 변경 등).
        if row.container_id is not None:
            try:
                from container.state_derive import derive_and_save_state
                await derive_and_save_state(self.db, self.team_id, row.container_id)
            except Exception:  # noqa: BLE001
                try:
                    await self.db.rollback()
                except Exception:  # noqa: BLE001
                    pass
                raise
        return LegResponseSchema.model_validate(row)

    # ═══════════════════════════════════════════════════════════════
    # 배차 (Assign / Unassign) — 재설계: 드라이버 배차 시 PENDING→ASSIGNED
    # ═══════════════════════════════════════════════════════════════

    async def _fetch_active_leg(self, leg_id: int):
        from sqlalchemy import select
        from leg.model import LegModel
        team_id = self.repo._require_team()
        leg = (await self.db.execute(select(LegModel).where(
            LegModel.team_id == team_id, LegModel.id == leg_id, LegModel.is_active.is_(True),
        ))).scalar_one_or_none()
        if not leg:
            raise NotFoundException("Leg")
        return leg

    async def _derive_container_after(self, container_id: int | None) -> None:
        """배차/상태 변경 후 container.work_state 재파생 (commit 이후, 실패해도 안전)."""
        if container_id is None:
            return
        try:
            from container.state_derive import derive_and_save_state
            await derive_and_save_state(self.db, self.team_id, container_id)
            await self.db.commit()
        except Exception:  # noqa: BLE001
            try:
                await self.db.rollback()
            except Exception:  # noqa: BLE001
                pass

    async def _derive_do_dispatch_after(self, do_id: int | None) -> None:
        """배차/leg CRUD 후 D/O dispatch-phase(PLANNING/DISPATCHING/DISPATCHED) 자동 파생."""
        if do_id is None:
            return
        try:
            from delivery_order.state_derive import derive_do_dispatch_state
            await derive_do_dispatch_state(self.db, self.team_id, do_id)
            await self.db.commit()
        except Exception:  # noqa: BLE001
            try:
                await self.db.rollback()
            except Exception:  # noqa: BLE001
                pass

    async def assign_driver(
        self, leg_id: int, driver_id: int, *,
        truck_id: int | None = None, chassis_id: int | None = None,
        actor_user_id: int | None = None,
    ) -> LegResponseSchema:
        """드라이버 배차. PENDING 이면 ASSIGNED 로 전이(+assigned_at). 이미 운행중이면 status 유지(재배차)."""
        from datetime import datetime, timezone
        from leg.const.status import LegStatus
        leg = await self._fetch_active_leg(leg_id)
        now = datetime.now(timezone.utc)
        leg.driver_id = driver_id
        if truck_id is not None:
            leg.truck_id = truck_id
        if chassis_id is not None:
            leg.chassis_id = chassis_id
        leg.offered_at = now  # mobile 호환: 드라이버에 offered
        if leg.status == LegStatus.PENDING:
            leg.status = LegStatus.ASSIGNED
            leg.assigned_at = now
        if actor_user_id is not None:
            leg.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(leg)
        await self._derive_container_after(leg.container_id)
        await self._derive_do_dispatch_after(leg.delivery_order_id)
        return LegResponseSchema.model_validate(leg)

    async def unassign_driver(self, leg_id: int, *, actor_user_id: int | None = None) -> LegResponseSchema:
        """배차 취소. ASSIGNED 이면 PENDING 으로 되돌림. 운행 시작 후엔 driver 만 비움."""
        from leg.const.status import LegStatus
        leg = await self._fetch_active_leg(leg_id)
        leg.driver_id = None
        leg.offered_at = None
        leg.accepted_at = None
        leg.rejected_at = None
        if leg.status == LegStatus.ASSIGNED:
            leg.status = LegStatus.PENDING
            leg.assigned_at = None
        if actor_user_id is not None:
            leg.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(leg)
        await self._derive_container_after(leg.container_id)
        await self._derive_do_dispatch_after(leg.delivery_order_id)
        return LegResponseSchema.model_validate(leg)

    # ═══════════════════════════════════════════════════════════════
    # Load Type 템플릿 → leg 자동 생성 (재설계 1d)
    # ═══════════════════════════════════════════════════════════════

    async def apply_load_type(
        self,
        container_id: int,
        template_id: int,
        *,
        replace_existing: bool = False,
        actor_user_id: int | None = None,
    ) -> List[LegResponseSchema]:
        """container 에 Load Type 템플릿 step 대로 leg 들을 생성한다."""
        from leg.generator import apply_load_type as _apply
        rows = await _apply(
            self.db, self.team_id,
            container_id=container_id, template_id=template_id,
            actor_user_id=actor_user_id, replace_existing=replace_existing,
        )
        return [LegResponseSchema.model_validate(r) for r in rows]

    # ═══════════════════════════════════════════════════════════════
    # Dry Run 재발급 (빠꾸 → 원본 DRY_RUN + 새 leg 발급)
    # ═══════════════════════════════════════════════════════════════

    async def reissue_dry_run(
        self,
        leg_id: int,
        *,
        reason: str | None = None,
        actor_user_id: int | None = None,
    ) -> LegResponseSchema:
        """현장 도착했으나 작업 불가(빠꾸) → 원본 leg 를 DRY_RUN 으로 종료하고
        동일 구간의 새 leg(PENDING, 미배차)를 발급한다."""
        from leg.const.status import LegStatus
        from leg.model import LegModel
        orig = await self._fetch_active_leg(leg_id)
        if orig.status not in (LegStatus.ASSIGNED, LegStatus.IN_TRANSIT):
            raise BadRequestException("ASSIGNED/IN_TRANSIT leg 만 Dry Run 재발급 가능")

        # 원본 → DRY_RUN 종료
        orig.status = LegStatus.DRY_RUN
        orig.failure_reason = reason
        if actor_user_id is not None:
            orig.updated_by_user_id = actor_user_id

        # 새 leg — 구간/요율 입력 복사, 미배차 PENDING
        new = LegModel(
            team_id=self.team_id,
            delivery_order_id=orig.delivery_order_id,
            container_id=orig.container_id,
            step=orig.step,
            move_type=orig.move_type,
            service_type=orig.service_type,
            move_code=orig.move_code,
            from_point_id=orig.from_point_id,
            to_point_id=orig.to_point_id,
            from_location_type=orig.from_location_type,
            to_location_type=orig.to_location_type,
            rate_point_id=orig.rate_point_id,
            dest_zip=orig.dest_zip, dest_city=orig.dest_city, dest_state=orig.dest_state,
            rate_miles=orig.rate_miles, rate_hours=orig.rate_hours,
            status=LegStatus.PENDING,
            reissued_from_leg_id=orig.id,
            created_by_user_id=actor_user_id,
        )
        self.db.add(new)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(new)
        await self._derive_container_after(new.container_id)
        await self._derive_do_dispatch_after(new.delivery_order_id)
        return LegResponseSchema.model_validate(new)

    # ═══════════════════════════════════════════════════════════════
    # Update (벌크) - 전체 성공 or 전체 실패
    # ═══════════════════════════════════════════════════════════════
    
    async def update_bulk(
        self,
        payload: LegBulkUpdateRequest,
        actor_user_id: int | None = None,
    ) -> LegBulkUpdateResponseSchema:
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
            leg = LegResponseSchema.model_validate(row)
            results.append(BulkResultItem(
                id=leg.id,
                success=True,
                data=leg,
            ))
        
        # 여기까지 오면 전부 성공
        return LegBulkUpdateResponseSchema(
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
        leg_id: int,
        actor_user_id: int | None = None,
    ) -> LegDeleteResponseSchema:
        """
        거래처 삭제 (항상 소프트 삭제)

        - Delta Sync에서 deleted_ids로 다른 클라이언트에 전파됨
        - FK 참조 여부와 관계없이 항상 소프트 삭제
        """
        row = await self.repo.get(leg_id)
        if not row:
            raise NotFoundException("거래처")

        do_id = row.delivery_order_id
        container_id = row.container_id
        await self.repo.soft_deactivate_by_id(
            leg_id,
            actor_user_id=actor_user_id,
        )
        # 재설계: leg 삭제 후 container.work_state + D/O dispatch-phase 재계산
        try:
            if container_id is not None:
                from container.state_derive import derive_and_save_state
                await derive_and_save_state(self.db, self.team_id, container_id)
            from delivery_order.state_derive import derive_do_dispatch_state
            await derive_do_dispatch_state(self.db, self.team_id, do_id)
        except Exception:  # noqa: BLE001
            pass
        return LegDeleteResponseSchema(
            id=leg_id,
            deleted=True,
            soft_deleted=True,
        )

    # ═══════════════════════════════════════════════════════════════
    # Delete (벌크) - Savepoint 패턴
    # ═══════════════════════════════════════════════════════════════
    
    async def delete_bulk(
        self,
        payload: LegBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> LegBulkDeleteResponseSchema:
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
        for leg_id in payload.ids:
            await self.repo.soft_deactivate_by_id(
                leg_id,
                actor_user_id=actor_user_id,
            )
            results.append(BulkDeleteResultItem(
                id=leg_id,
                success=True,
                soft_deleted=True,
            ))

        return LegBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(
                total=len(payload.ids),
                succeeded=len(results),
                failed=0,
            ),
        )

    # ═══════════════════════════════════════════════════════════════
    # 상태 머신 — transition
    # ═══════════════════════════════════════════════════════════════

    async def transition(
        self,
        leg_id: int,
        target,                 # LegStatus (string 가능)
        *,
        failure_reason: str | None = None,
        actor_user_id: int | None = None,
    ):
        """Leg 상태 전이.

        규칙:
        - PENDING → IN_TRANSIT: started_at 자동 기록
        - IN_TRANSIT → COMPLETED: completed_at + arrived_at(없으면) 자동 기록 → Container.work_state 파생
        - IN_TRANSIT → FAILED: failure_reason 필수
        - 전이 그래프는 leg/state_machine.py 가 단일 진실.
        """
        from datetime import datetime, timezone
        from sqlalchemy import select
        from leg.model import LegModel
        from leg.const.status import LegStatus
        from leg.state_machine import assert_can_transition

        target_enum = target if isinstance(target, LegStatus) else LegStatus(target)
        team_id = self.repo._require_team()
        stmt = select(LegModel).where(
            LegModel.team_id == team_id,
            LegModel.id == leg_id,
            LegModel.is_active.is_(True),
        )
        leg = (await self.db.execute(stmt)).scalar_one_or_none()
        if not leg:
            raise NotFoundException("Leg")

        previous = leg.status
        assert_can_transition(previous, target_enum)
        if target_enum == LegStatus.FAILED and not failure_reason:
            raise BadRequestException("failure_reason required for FAILED")

        now = datetime.now(timezone.utc)
        if target_enum == LegStatus.ASSIGNED:
            leg.assigned_at = now
        elif target_enum == LegStatus.IN_TRANSIT:
            leg.started_at = now
        elif target_enum == LegStatus.COMPLETED:
            leg.completed_at = now
            leg.arrived_at = leg.arrived_at or now
        elif target_enum == LegStatus.FAILED:
            leg.failure_reason = failure_reason
        leg.status = target_enum
        if actor_user_id is not None:
            leg.updated_by_user_id = actor_user_id

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(leg)

        # ── 자동 hook: commit 이후 별도 트랜잭션. 실패해도 메인 transition 안전 ──
        if target_enum == LegStatus.COMPLETED:
            # Container.work_state derive
            if leg.container_id is not None:
                try:
                    from container.state_derive import derive_and_save_state
                    await derive_and_save_state(self.db, self.team_id, leg.container_id)
                    await self.db.commit()
                except Exception:  # noqa: BLE001
                    try:
                        await self.db.rollback()
                    except Exception:  # noqa: BLE001
                        pass

        # Realtime publish
        try:
            from realtime.service import publish
            from realtime.schemas.event import RealtimeEvent
            await publish(RealtimeEvent.now(
                type="leg.status_changed",
                team_id=team_id,
                actor_id=actor_user_id,
                payload={
                    "legId": leg.id,
                    "deliveryOrderId": leg.delivery_order_id,
                    "driverId": leg.driver_id,
                    "from": previous.value,
                    "to": target_enum.value,
                },
            ), db=self.db)
        except Exception:
            pass

        return LegResponseSchema.model_validate(leg)
