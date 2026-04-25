from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import Field
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema


class CreateShipmentRequestSchema(RequestSchema):
    mbl: str = Field(min_length=1, max_length=50)
    # 선사는 **필수** — 프론트 Quick Entry 에서 SCAC prefix 로 자동 선택을 돕지만,
    # 최종 제출 시 ``carrier_id`` 가 반드시 실제 carrier 를 가리켜야 한다.
    # 서비스 레이어가 "해당 id 의 carrier 가 실제로 존재하는지" 추가 검증한다.
    carrier_id: int = Field(..., gt=0)
    # Phase B user metadata — set at creation time, editable later via PATCH.
    # customer_id 와 tag_ids 는 같은 team 소유 여부를 서비스가 검증한다.
    customer_id: Optional[int] = Field(default=None, gt=0)
    ref_numbers: Optional[List[str]] = Field(default=None)
    tag_ids: Optional[List[int]] = Field(default=None)


class UpdateShipmentRequestSchema(RequestSchema):
    """Partial update for user-editable metadata. Scraping-owned fields
    (status, vessel_name, eta, etc.) are intentionally excluded — those
    flow from the scraper's upsert path, not from user PATCH requests."""

    customer_id: Optional[int] = Field(default=None, ge=0)  # 0 또는 null → 해제
    ref_numbers: Optional[List[str]] = Field(default=None)
    tag_ids: Optional[List[int]] = Field(default=None)


class PaginateShipmentRequestSchema(BasePaginationSchema):
    where__status__equal: Optional[str] = Field(default=None, description="상태 필터")
    where__carrier_id__equal: Optional[int] = Field(default=None, description="선사 ID 필터")
    where__customer_id__equal: Optional[int] = Field(default=None, description="고객 ID 필터")
    # 최근 N일 이내 등록된 shipment — "Recently Added" 탭용.
    # generic pagination filter 가 created_at 컬럼을 직접 지원.
    where__created_at__more_than_or_equal: Optional[str] = Field(
        default=None,
        description="이 시각 이후 생성된 shipment (ISO-8601 UTC)",
    )
    # 컨테이너 물리 상태 기반 필터 — "On Ship" / "Arrived" 탭.
    # 값: ContainerPhysicalStatus Enum 값 콤마 구분. 예: "on_ship,loaded".
    # generic pagination 은 ShipmentModel 컬럼만 지원하므로 서비스 레이어에서
    # EXISTS 서브쿼리로 base_query 에 주입. 시맨틱: "하나라도 매칭"
    where__any_container_physical_status__in: Optional[str] = Field(
        default=None,
        description="컨테이너 물리 상태 (콤마 구분) — 하나라도 매칭되는 shipment 반환",
    )
    order__id: Optional[Literal["ASC", "DESC"]] = Field(default="DESC")
