# src/delivery_order/service.py
from __future__ import annotations
from typing import List
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, delete

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from delivery_order.const.status import DeliveryStatus
from delivery_order.model import DeliveryOrderModel, DeliveryOrderAddonModel
from delivery_order.repository import DeliveryOrderRepository
from delivery_order.state_machine import (
    TransitionContext, assert_can_transition,
)
from leg.model import LegModel
from leg_layer.charge import resolve_addon_amount
from container.repository import ContainerRepository
from delivery_order.schemas.request import (
    DeliveryOrderCreateRequest, DeliveryOrderUpdateRequest, PaginateDeliveryOrderRequest,
    DeliveryOrderBulkCreateRequest, DeliveryOrderBulkUpdateRequest, DeliveryOrderBulkDeleteRequest,
    DoAddonCreateRequest, DoAddonUpdateRequest,
)
from delivery_order.schemas.response import (
    DeliveryOrderResponseSchema, DeliveryOrderDetailResponseSchema, DeliveryOrderDeleteResponseSchema,
    DeliveryOrderBulkCreateResponseSchema, DeliveryOrderBulkUpdateResponseSchema, DeliveryOrderBulkDeleteResponseSchema,
    BulkResultItem, BulkDeleteResultItem, BulkSummary,
    DoAddonResponseSchema, DoAddonDeleteResponseSchema,
)
from container.schemas.response import ContainerResponseSchema


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
        self.team_id = team_id
        self.repo = DeliveryOrderRepository(db, team_id)
        self.container_repo = ContainerRepository(db, team_id)

    # ═══════════════════════════════════════════════════════════════
    # D/O 단위 Add-on (고객 청구용) — addon 마스터 인스턴스, D/O 당 N행
    # ═══════════════════════════════════════════════════════════════

    async def list_addons(self, do_id: int) -> List[DoAddonResponseSchema]:
        q = select(DeliveryOrderAddonModel).where(
            DeliveryOrderAddonModel.team_id == self.team_id,
            DeliveryOrderAddonModel.delivery_order_id == do_id,
            DeliveryOrderAddonModel.is_active.is_(True),
        ).order_by(DeliveryOrderAddonModel.id.asc())
        return [DoAddonResponseSchema.model_validate(r) for r in (await self.db.execute(q)).scalars().all()]

    async def add_addon(self, payload: DoAddonCreateRequest, actor_user_id: int | None = None) -> DoAddonResponseSchema:
        from addon.model import AddonModel
        addon = (await self.db.execute(select(AddonModel).where(
            AddonModel.team_id == self.team_id, AddonModel.id == payload.addon_id,
        ))).scalar_one_or_none()
        if addon is None:
            raise NotFoundException("Add-on type")
        data = payload.model_dump()
        data["code"] = addon.code  # 스냅샷
        data["is_payable_to_driver"] = addon.is_payable_to_driver
        data["is_billable_to_customer"] = addon.is_billable_to_customer
        if data.get("amount") in (None, Decimal("0")):
            filled = await resolve_addon_amount(self.db, self.team_id, addon.code)  # D/O = driver 없음 → 팀 기본
            if filled is not None:
                data["amount"], data["unit_amount"], data["quantity"] = filled
        if data.get("amount") is None:
            data["amount"] = Decimal("0")
        data["team_id"] = self.team_id
        if actor_user_id is not None:
            data["created_by_user_id"] = actor_user_id
        row = DeliveryOrderAddonModel(**data)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return DoAddonResponseSchema.model_validate(row)

    async def _get_addon(self, addon_id: int) -> DeliveryOrderAddonModel | None:
        q = select(DeliveryOrderAddonModel).where(
            DeliveryOrderAddonModel.team_id == self.team_id,
            DeliveryOrderAddonModel.id == addon_id,
            DeliveryOrderAddonModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def update_addon(self, addon_id: int, payload: DoAddonUpdateRequest, actor_user_id: int | None = None) -> DoAddonResponseSchema:
        row = await self._get_addon(addon_id)
        if not row:
            raise NotFoundException("D/O Add-on")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return DoAddonResponseSchema.model_validate(row)

    async def delete_addon(self, addon_id: int) -> DoAddonDeleteResponseSchema:
        if not await self._get_addon(addon_id):
            raise NotFoundException("D/O Add-on")
        await self.db.execute(delete(DeliveryOrderAddonModel).where(
            DeliveryOrderAddonModel.team_id == self.team_id,
            DeliveryOrderAddonModel.id == addon_id,
        ))
        await self.db.flush()
        return DoAddonDeleteResponseSchema(id=addon_id)

    # ═══════════════════════════════════════════════════════════════
    # Create (단건)
    # ═══════════════════════════════════════════════════════════════
    
    async def create(
        self,
        payload: DeliveryOrderCreateRequest,
        actor_user_id: int | None = None,
    ) -> DeliveryOrderDetailResponseSchema:
        # nested 컨테이너 분리
        data = payload.model_dump()
        containers_data = data.pop("containers", []) or []

        row = await self.repo.create(data, actor_user_id=actor_user_id)

        created_containers: list[ContainerResponseSchema] = []
        for idx, c in enumerate(containers_data, start=1):
            if c.get("sequence_no") is None:
                c["sequence_no"] = idx
            c["delivery_order_id"] = row.id
            # v3: stops 는 ContainerCreateInner 의 추가 필드. ContainerModel 에 없으므로 분리.
            stops_data = c.pop("stops", []) or []
            container_row = await self.container_repo.create(c, actor_user_id=actor_user_id)
            created_containers.append(ContainerResponseSchema.model_validate(container_row))
            # v3: AI Intake 가 추출한 stop 시퀀스를 ContainerStop row 로 자동 생성.
            # 실패 시 rollback 으로 세션 invalid 회피 — 그 결과 D/O/컨테이너도 같이
            # 롤백되어 일관된 상태 유지.
            if stops_data:
                try:
                    await self._create_stops_from_payload(
                        container_id=container_row.id,
                        stops=stops_data,
                        actor_user_id=actor_user_id,
                    )
                except Exception:  # noqa: BLE001
                    try:
                        await self.db.rollback()
                    except Exception:  # noqa: BLE001
                        pass
                    raise

        await self._audit(row.id, "created", summary=row.bl_number or row.booking_number,
                          actor_user_id=actor_user_id)
        do_dict = DeliveryOrderResponseSchema.model_validate(row).model_dump()
        return DeliveryOrderDetailResponseSchema(**do_dict, containers=created_containers)

    async def _create_stops_from_payload(
        self,
        *,
        container_id: int,
        stops: list[dict],
        actor_user_id: int | None,
    ) -> None:
        """v3: ContainerCreateInner.stops 를 ContainerStop row 로 변환.

        location_id 가 None 이면 location_name 으로 fuzzy 매칭 (case-insensitive contains).
        매칭 실패 시 location_id null 로 stop 생성 (사용자가 후보 선택할 수 있도록).
        """
        from sqlalchemy import select, func as _func
        from container_stop.model import ContainerStopModel
        from leg.const.status import PointType
        from location.model import LocationModel
        from container.state_derive import derive_and_save_state

        # 한 번만 location 캐시
        all_locs = (await self.db.execute(
            select(LocationModel.id, LocationModel.name).where(
                LocationModel.team_id == self.team_id,
                LocationModel.is_active.is_(True),
            )
        )).all()

        def fuzzy_lookup(name: str | None) -> int | None:
            if not name:
                return None
            target = name.strip().lower()
            # 1) exact case-insensitive
            for lid, lname in all_locs:
                if lname and lname.strip().lower() == target:
                    return lid
            # 2) substring contains (양방향)
            for lid, lname in all_locs:
                if not lname:
                    continue
                ln = lname.strip().lower()
                if target in ln or ln in target:
                    return lid
            return None

        for idx, s in enumerate(stops, start=1):
            terminal_id = s.get("terminal_id")
            customer_id = s.get("customer_id")
            location_id = s.get("location_id")
            # point_type 결정: 명시값 우선 → 채워진 FK 로 추론 → 기본 YARD
            pt_raw = (s.get("point_type") or "").upper()
            try:
                point_type = PointType(pt_raw)
            except Exception:  # noqa: BLE001
                if terminal_id:
                    point_type = PointType.TERMINAL
                elif customer_id:
                    point_type = PointType.CUSTOMER
                else:
                    point_type = PointType.YARD
            # YARD 이고 location 미지정이면 이름으로 fuzzy 매칭
            if point_type == PointType.YARD and location_id is None:
                location_id = fuzzy_lookup(s.get("location_name"))
            seq = s.get("sequence_no") if s.get("sequence_no") else idx
            self.db.add(ContainerStopModel(
                team_id=self.team_id,
                container_id=container_id,
                sequence_no=seq,
                point_type=point_type,
                terminal_id=terminal_id,
                location_id=location_id,
                customer_id=customer_id,
                planned_arrival=s.get("planned_arrival"),
                planned_departure=s.get("planned_departure"),
                note=s.get("note"),
                created_by_user_id=actor_user_id,
            ))
        await self.db.flush()
        # work_state 자동 derive (DRAFT → PLANNED 가능)
        await derive_and_save_state(self.db, self.team_id, container_id)

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
    
    async def get(self, delivery_order_id: int) -> DeliveryOrderDetailResponseSchema:
        row = await self.repo.get(delivery_order_id)
        if not row:
            raise NotFoundException("D/O")
        containers = await self.container_repo.list_by_delivery_order(delivery_order_id)
        do_dict = DeliveryOrderResponseSchema.model_validate(row).model_dump()
        return DeliveryOrderDetailResponseSchema(
            **do_dict,
            containers=[ContainerResponseSchema.model_validate(c) for c in containers],
        )

    async def list_paginated(
        self, request: PaginateDeliveryOrderRequest
    ) -> CursorPaginationResult[DeliveryOrderResponseSchema]:
        """
        커서 기반 페이지네이션 + H-10 enrich:
          - container_count / container_completed_count
          - margin_preview (재설계: 매출 invoice 청구 − 지급 payroll base)
          - eta_status (OVERDUE / URGENT / OK / NONE)
        """
        result = await self.repo.get_paginated(request)
        rows = list(result.data)
        ids = [r.id for r in rows]

        derived = await self._compute_list_derived(ids) if ids else {}
        out = []
        for r in rows:
            schema = DeliveryOrderResponseSchema.model_validate(r).model_copy(
                update=derived.get(r.id, {}),
            )
            out.append(schema)
        result.data = out
        return result

    async def _compute_list_derived(self, ids: list[int]) -> dict[int, dict]:
        """List 페이지 단위로 파생 필드 일괄 계산. team_id 스코프."""
        from datetime import timezone, timedelta
        from decimal import Decimal as _Decimal
        from sqlalchemy import func, case, and_ as _and
        from container.model import ContainerModel
        from payroll.model import PayrollLineModel, PayrollSettlementModel
        from payroll.const.status import PayrollStatus
        from invoice.model import InvoiceModel
        from invoice.const.status import InvoiceStatus
        from delivery_order.schemas.response import EtaStatus

        # 1) 컨테이너 카운트 (전체 / 도착완료)
        c_total = func.count(ContainerModel.id).label("c_total")
        c_done = func.sum(case(
            (ContainerModel.status == DeliveryStatus.COMPLETED, 1), else_=0,
        )).label("c_done")
        next_eta = func.min(case(
            (ContainerModel.status != DeliveryStatus.COMPLETED,
             ContainerModel.delivery_appointment),
        )).label("next_eta")
        cq = (
            select(
                ContainerModel.delivery_order_id, c_total, c_done, next_eta,
            )
            .where(
                ContainerModel.team_id == self.team_id,
                ContainerModel.is_active.is_(True),
                ContainerModel.delivery_order_id.in_(ids),
            )
            .group_by(ContainerModel.delivery_order_id)
        )
        cmap: dict[int, dict] = {}
        for r in (await self.db.execute(cq)).all():
            cmap[r.delivery_order_id] = {
                "c_total": int(r.c_total or 0),
                "c_done": int(r.c_done or 0),
                "next_eta": r.next_eta,
            }

        # 2) margin_preview (재설계): 매출(invoice 청구) - 지급(payroll base) per D/O
        # 지급 — payroll base by leg.delivery_order_id (비-VOID 정산)
        payq = (
            select(LegModel.delivery_order_id, func.coalesce(func.sum(PayrollLineModel.base_amount), 0).label("pay"))
            .select_from(PayrollLineModel)
            .join(LegModel, LegModel.id == PayrollLineModel.leg_id)
            .join(PayrollSettlementModel, _and(
                PayrollSettlementModel.team_id == PayrollLineModel.team_id,
                PayrollSettlementModel.id == PayrollLineModel.settlement_id,
            ))
            .where(
                PayrollLineModel.team_id == self.team_id,
                PayrollSettlementModel.status != PayrollStatus.VOID,
                LegModel.delivery_order_id.in_(ids),
            )
            .group_by(LegModel.delivery_order_id)
        )
        # 매출 — invoice 청구액 by invoice.delivery_order_id (비-VOID)
        revq = (
            select(InvoiceModel.delivery_order_id, func.coalesce(func.sum(InvoiceModel.charge_total), 0).label("rev"))
            .where(
                InvoiceModel.team_id == self.team_id,
                InvoiceModel.is_active.is_(True),
                InvoiceModel.status != InvoiceStatus.VOID,
                InvoiceModel.delivery_order_id.in_(ids),
            )
            .group_by(InvoiceModel.delivery_order_id)
        )
        mmap: dict[int, _Decimal] = {}
        for r in (await self.db.execute(payq)).all():
            mmap[r.delivery_order_id] = mmap.get(r.delivery_order_id, _Decimal(0)) - _Decimal(r.pay or 0)
        for r in (await self.db.execute(revq)).all():
            mmap[r.delivery_order_id] = mmap.get(r.delivery_order_id, _Decimal(0)) + _Decimal(r.rev or 0)

        # 3) ETA status — DB 의 naive datetime 과 비교를 위해 양쪽 다 naive 로
        now = datetime.utcnow()
        urgent_cutoff = now + timedelta(hours=24)

        def _naive(d):
            if d is None:
                return None
            return d.replace(tzinfo=None) if d.tzinfo is not None else d

        out: dict[int, dict] = {}
        for do_id in ids:
            c = cmap.get(do_id, {"c_total": 0, "c_done": 0, "next_eta": None})
            eta = _naive(c["next_eta"])
            if eta is None:
                eta_status = EtaStatus.NONE
            elif eta < now:
                eta_status = EtaStatus.OVERDUE
            elif eta < urgent_cutoff:
                eta_status = EtaStatus.URGENT
            else:
                eta_status = EtaStatus.OK
            out[do_id] = {
                "container_count": c["c_total"],
                "container_completed_count": c["c_done"],
                "margin_preview": mmap.get(do_id, _Decimal(0)),
                "eta_status": eta_status,
            }
        return out

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

        # 2) 컨텍스트 사전 로드 — legs (오래된 순). H-1 후 location 검증은 컨테이너 단위로 이동
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
        ctx = TransitionContext(do=do, legs=legs)

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

        # 6) 활동 타임라인 기록 (best-effort)
        await self._audit(
            do.id, "status_changed",
            summary=f"{previous.value} → {target.value}",
            before={"status": previous.value}, after={"status": target.value},
            actor_user_id=actor_user_id,
        )
        return DeliveryOrderResponseSchema.model_validate(do)

    # ── Hold / Cancel (overlay) ──────────────────────────────────
    async def _get_raw(self, do_id: int) -> "DeliveryOrderModel":
        team_id = self.repo._require_team()
        do = (await self.db.execute(select(DeliveryOrderModel).where(
            DeliveryOrderModel.team_id == team_id,
            DeliveryOrderModel.id == do_id,
            DeliveryOrderModel.is_active.is_(True),
        ))).scalar_one_or_none()
        if not do:
            raise NotFoundException("D/O")
        return do

    async def set_hold(self, do_id: int, *, on_hold: bool, reason: str | None = None,
                       actor_user_id: int | None = None) -> DeliveryOrderResponseSchema:
        do = await self._get_raw(do_id)
        if do.cancelled_at is not None:
            from common.exceptions.base import ConflictException
            raise ConflictException("취소된 D/O 는 Hold 변경 불가.")
        do.is_on_hold = on_hold
        do.hold_reason = reason if on_hold else None
        if actor_user_id is not None:
            do.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(do)
        await self._audit(
            do.id, "hold_set" if on_hold else "hold_cleared",
            summary=reason, actor_user_id=actor_user_id,
        )
        return DeliveryOrderResponseSchema.model_validate(do)

    async def cancel(self, do_id: int, *, reason: str | None = None,
                     actor_user_id: int | None = None) -> DeliveryOrderResponseSchema:
        from datetime import datetime, timezone
        do = await self._get_raw(do_id)
        if do.cancelled_at is not None:
            return DeliveryOrderResponseSchema.model_validate(do)
        do.cancelled_at = datetime.now(timezone.utc)
        do.cancel_reason = reason
        do.is_on_hold = False
        if actor_user_id is not None:
            do.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(do)
        await self._audit(do.id, "cancelled", summary=reason, actor_user_id=actor_user_id)
        return DeliveryOrderResponseSchema.model_validate(do)

    async def _audit(self, do_id: int, action: str, *, summary: str | None = None,
                     before: dict | None = None, after: dict | None = None,
                     actor_user_id: int | None = None) -> None:
        """활동 타임라인 기록 — 실패해도 메인 작업 안전(best-effort)."""
        try:
            from audit_log.service import AuditLogService
            await AuditLogService(self.db, self.repo._require_team()).record(
                entity_type="delivery_order", entity_id=do_id, action=action,
                summary=summary, before_state=before, after_state=after,
                actor_user_id=actor_user_id,
            )
            await self.db.commit()
        except Exception:  # noqa: BLE001
            try:
                await self.db.rollback()
            except Exception:  # noqa: BLE001
                pass
