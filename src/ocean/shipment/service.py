from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import exists, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from ocean.shipment.model import ShipmentModel
from ocean.shipment.const.status import ShipmentStatus
from ocean.shipment.repository import ShipmentRepository
from ocean.container.model import ContainerModel
from ocean.ref_number.repository import RefNumberRepository
from ocean.shipment.schemas.request import (
    CreateShipmentRequestSchema,
    PaginateShipmentRequestSchema,
    UpdateShipmentRequestSchema,
)
from ocean.shipment.schemas.response import (
    ShipmentResponseSchema,
    ShipmentDetailResponseSchema,
    TrackResponseSchema,
)
from ocean.container.schemas.response import ContainerResponseSchema
from ocean.container_event.schemas.response import ContainerEventResponseSchema
from tag.repository import TagRepository
from customer.repository import CustomerRepository
from carrier.repository import CarrierRepository
from common.exceptions.base import AppException, NotFoundException
from fastapi import status


class ShipmentService:
    """팀 scoped Shipment 서비스. 생성자에서 ``team_id`` 를 받아 하위 리포에
    전파한다. 서비스 메서드는 더 이상 ``team_id`` 를 받지 않는다."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = ShipmentRepository(db, team_id)
        # 교차 도메인 — shipment 에 붙는 분류 리소스들.
        self.tag_repo = TagRepository(db, team_id)
        self.customer_repo = CustomerRepository(db, team_id)
        self.ref_number_repo = RefNumberRepository(db, team_id)
        # 전역 carriers 테이블 조회용 (team_id 무관).
        self.carrier_repo = CarrierRepository(db)
        self.pagination = CommonService()

    async def create_shipment(
        self,
        body: CreateShipmentRequestSchema,
        *,
        creator_user_id: Optional[int] = None,
    ) -> ShipmentResponseSchema:
        # 선사는 요청 스키마에서 이미 필수 검증 (Pydantic) — 여기선 team/global
        # carriers 테이블에 실제 존재하는지만 확인.
        carrier = await self.carrier_repo.get_by_id(body.carrier_id)
        if carrier is None:
            raise AppException(
                code="CARRIER_NOT_FOUND",
                message=f"해당 선사(id={body.carrier_id})를 찾을 수 없습니다.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Customer 소유권 검증 — 팀 외 customer 참조 차단.
        if body.customer_id is not None:
            customer = await self.customer_repo.get_by_id(body.customer_id)
            if customer is None:
                raise AppException(
                    code="CUSTOMER_NOT_FOUND",
                    message=f"해당 고객(id={body.customer_id})을 찾을 수 없습니다.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        shipment = ShipmentModel(
            mbl=body.mbl,
            carrier_id=carrier.id,
            # 첫 스크래핑 결과가 오기 전까진 PENDING — tracking/awaiting_manifest/failed
            # 로의 전이는 scraping 레포의 save_tracking_result 가 담당한다.
            status=ShipmentStatus.PENDING.value,
            next_scrape_at=datetime.now(timezone.utc),
            customer_id=body.customer_id,
            created_by_user_id=creator_user_id,
            updated_by_user_id=creator_user_id,
        )
        # create() 가 team_id 를 mixin 기반으로 주입하므로 여기선 비워둔다.
        if body.tag_ids:
            shipment.tags = await self._resolve_tags(body.tag_ids)
        shipment = await self.repo.create(shipment)

        # ref_numbers 는 자식 row 로 저장 — shipment.id 가 확정된 뒤 replace.
        if body.ref_numbers:
            await self.ref_number_repo.replace_for_shipment(
                shipment.id,
                body.ref_numbers,
                actor_user_id=creator_user_id or 0,
            )

        await self._reload(shipment)
        return self._serialize(shipment)

    async def list_shipments(
        self, request: PaginateShipmentRequestSchema,
    ) -> CursorPaginationResult[ShipmentResponseSchema]:
        base_query = (
            select(ShipmentModel)
            .options(
                selectinload(ShipmentModel.tags),
                selectinload(ShipmentModel.ref_numbers),
            )
            .where(
                ShipmentModel.team_id == self.team_id,
                ShipmentModel.is_active.is_(True),
            )
        )

        # 컨테이너 물리 상태 기반 탭 필터 ("On Ship" / "Arrived") —
        # generic pagination 은 ShipmentModel 컬럼만 인식하므로 EXISTS 서브쿼리를
        # 수동 주입한다. 시맨틱: shipment 의 container 중 하나라도 physical_status
        # 가 요청된 값 집합에 속하면 포함. 빈 값 토큰은 무시.
        if request.where__any_container_physical_status__in:
            statuses = [
                s.strip()
                for s in request.where__any_container_physical_status__in.split(",")
                if s.strip()
            ]
            if statuses:
                base_query = base_query.where(
                    exists().where(
                        ContainerModel.team_id == ShipmentModel.team_id,
                        ContainerModel.shipment_id == ShipmentModel.id,
                        ContainerModel.physical_status.in_(statuses),
                        ContainerModel.is_active.is_(True),
                    )
                )

        result = await self.pagination.paginate(
            request=request,
            model=ShipmentModel,
            session=self.db,
            base_query=base_query,
            path="api/v1/shipments",
        )
        result.data = [self._serialize(s) for s in result.data]
        return result

    async def get_shipment_detail(self, shipment_id: int) -> ShipmentDetailResponseSchema:
        shipment = await self.repo.get_by_id_with_relations(shipment_id)
        if not shipment:
            raise NotFoundException("Shipment")
        base = self._serialize(shipment).model_dump()
        return ShipmentDetailResponseSchema(
            **base,
            containers=[ContainerResponseSchema.model_validate(c) for c in shipment.containers],
            events=[ContainerEventResponseSchema.model_validate(e) for e in shipment.events],
        )

    async def update_shipment(
        self,
        shipment_id: int,
        body: UpdateShipmentRequestSchema,
        *,
        updater_user_id: int,
    ) -> ShipmentResponseSchema:
        shipment = await self.repo.get_by_id(shipment_id)
        if not shipment:
            raise NotFoundException("Shipment")
        # team_id 검증은 리포가 담당 (WHERE 절). 서비스는 비즈니스 로직만.

        data = body.model_dump(exclude_unset=True)
        if "customer_id" in data:
            new_cid = data["customer_id"]
            # 0 또는 None 은 "해제" — FK 해제 허용.
            if new_cid in (None, 0):
                shipment.customer_id = None
            else:
                customer = await self.customer_repo.get_by_id(new_cid)
                if customer is None:
                    raise AppException(
                        code="CUSTOMER_NOT_FOUND",
                        message=f"해당 고객(id={new_cid})을 찾을 수 없습니다.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                shipment.customer_id = customer.id
        if "tag_ids" in data:
            ids = data["tag_ids"] or []
            shipment.tags = await self._resolve_tags(ids)
        shipment.updated_by_user_id = updater_user_id
        await self.db.flush()

        if "ref_numbers" in data:
            await self.ref_number_repo.replace_for_shipment(
                shipment.id,
                data["ref_numbers"] or [],
                actor_user_id=updater_user_id,
            )

        await self._reload(shipment)
        return self._serialize(shipment)

    async def stop_shipment(self, shipment_id: int) -> ShipmentResponseSchema:
        """사용자가 수동으로 추적을 중단. status → STOPPED, 재스크래핑 중단."""
        shipment = await self.repo.get_by_id(shipment_id)
        if not shipment:
            raise NotFoundException("Shipment")
        shipment.status = ShipmentStatus.STOPPED.value
        shipment.next_scrape_at = None
        await self.db.flush()
        await self._reload(shipment)
        return self._serialize(shipment)

    async def resubmit_shipment(self, shipment_id: int) -> ShipmentResponseSchema:
        """실패한 shipment 를 다시 추적 (같은 row 재사용 모델).

        status 가 FAILED / STOPPED / CANCELLED 중 하나여야 resubmit 가능 —
        PENDING/TRACKING/AWAITING_MANIFEST 는 이미 진행 중이므로 거부한다.
        """
        shipment = await self.repo.get_by_id(shipment_id)
        if not shipment:
            raise NotFoundException("Shipment")
        resubmittable = {
            ShipmentStatus.FAILED.value,
            ShipmentStatus.STOPPED.value,
            ShipmentStatus.CANCELLED.value,
        }
        if shipment.status not in resubmittable:
            raise AppException(
                code="SHIPMENT_NOT_RESUBMITTABLE",
                message=(
                    "이 shipment 는 이미 진행 중이라 Resubmit 할 수 없습니다."
                ),
                status_code=status.HTTP_409_CONFLICT,
            )
        shipment.status = ShipmentStatus.PENDING.value
        shipment.next_scrape_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self._reload(shipment)
        return self._serialize(shipment)

    async def track_by_mbl(self, mbl: str) -> TrackResponseSchema:
        shipment = await self.repo.get_by_mbl_with_relations(mbl)
        if not shipment:
            raise NotFoundException("Shipment")
        return TrackResponseSchema(
            shipment=self._serialize(shipment),
            containers=[ContainerResponseSchema.model_validate(c) for c in shipment.containers],
            events=[ContainerEventResponseSchema.model_validate(e) for e in shipment.events],
        )

    # ── Helpers ──────────────────────────────────────────

    async def _resolve_tags(self, tag_ids: List[int]) -> List:
        """``tag_ids`` 를 로드해 **현재 팀 소유** 만 허용. 크로스 팀 누락 감지 시
        전체 payload 를 거부한다."""
        if not tag_ids:
            return []
        unique_ids = list({int(i) for i in tag_ids})
        tags = list(await self.tag_repo.list_by_ids(unique_ids))
        if len(tags) != len(unique_ids):
            found = {t.id for t in tags}
            missing = sorted(set(unique_ids) - found)
            raise AppException(
                code="TAG_INVALID",
                message=f"유효하지 않은 태그 ID: {missing}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return tags

    async def _reload(self, shipment: ShipmentModel) -> None:
        """``lazy='raise'`` 하에서 create/update 후 관계 캐시가 비어있을 수 있으므로
        tags/ref_numbers/customer 를 재조회해 다시 붙인다.

        ``populate_existing=True`` 는 필수 — 그렇지 않으면 identity map 에 이미 올라간
        shipment 인스턴스의 ref_numbers/tags 컬렉션 캐시를 selectinload 가
        갱신하지 않는다. ``replace_for_shipment`` 가 bulk DELETE 로 session 에 있던
        RefNumberModel 인스턴스들을 ``deleted`` 상태로 만들어 두기 때문에, 캐시
        갱신 없이 ``.value`` 를 읽으면 "Instance has been deleted" 로 터진다.
        """
        stmt = (
            select(ShipmentModel)
            .options(
                selectinload(ShipmentModel.tags),
                selectinload(ShipmentModel.ref_numbers),
            )
            .execution_options(populate_existing=True)
            .where(
                ShipmentModel.team_id == self.team_id,
                ShipmentModel.id == shipment.id,
            )
        )
        refreshed = await self.db.scalar(stmt)
        if refreshed is not None:
            shipment.tags = list(refreshed.tags)
            shipment.ref_numbers = list(refreshed.ref_numbers)
            # customer / carrier 는 selectin 이라 refresh 만으로 로드됨 — 별도 복사 불필요.

    def _serialize(self, shipment: ShipmentModel) -> ShipmentResponseSchema:
        """ORM row 를 응답 스키마로 변환. ``ref_numbers`` 관계는 문자열 배열로 평탄화."""
        # ORM 의 .ref_numbers 는 RefNumberModel 리스트 — 응답 스키마의 동일 이름
        # 필드(List[str]) 와 충돌하므로 먼저 dict 로 뽑은 뒤 수동 치환한다.
        ref_values: List[str] = [rn.value for rn in (shipment.ref_numbers or [])]
        payload = {
            "id": shipment.id,
            "team_id": shipment.team_id,
            "mbl": shipment.mbl,
            "carrier_id": shipment.carrier_id,
            "carrier": shipment.carrier,
            "status": shipment.status,
            "vessel_name": shipment.vessel_name,
            "vessel_id": shipment.vessel_id,
            "voyage_number": shipment.voyage_number,
            "pol_location_id": shipment.pol_location_id,
            "pod_location_id": shipment.pod_location_id,
            "pol_location": shipment.pol_location,
            "pod_location": shipment.pod_location,
            "etd": shipment.etd,
            "eta": shipment.eta,
            "confidence": shipment.confidence,
            "tracking_frequency": shipment.tracking_frequency,
            "next_scrape_at": shipment.next_scrape_at,
            "customer_id": shipment.customer_id,
            "customer": shipment.customer,
            "ref_numbers": ref_values,
            "tags": list(shipment.tags or []),
            "created_at": shipment.created_at,
            "updated_at": shipment.updated_at,
        }
        return ShipmentResponseSchema.model_validate(payload)
