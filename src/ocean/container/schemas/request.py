from __future__ import annotations
from typing import Optional, Literal
from pydantic import Field
from common.pagination.schemas.pagination_request import BasePaginationSchema


class PaginateContainerRequestSchema(BasePaginationSchema):
    """팀 전역 컨테이너 목록 필터.

    이 스키마는 `GET /api/v1/ocean/containers` (전역 리스트, Terminal49 스타일
    "Containers" 페이지) 에서 사용. shipment 서브리소스 엔드포인트
    `/api/v1/ocean/shipments/{id}/containers` 는 페이지네이션 없이
    List[ContainerResponseSchema] 반환.
    """

    # 컨테이너 번호 / 부모 MBL 부분 매칭 (대소문자 무시).
    where__number__i_like: Optional[str] = Field(default=None, description="컨테이너 번호 검색")
    where__mbl__i_like: Optional[str] = Field(default=None, description="부모 MBL 검색")

    # 정규화된 필터 — 프론트 탭 / 드롭다운에서 사용.
    where__physical_status__equal: Optional[str] = Field(
        default=None, description="ContainerPhysicalStatus 필터",
    )
    where__size_type_code__equal: Optional[str] = Field(
        default=None, description="ContainerSizeType 필터",
    )

    # 선사 — shipment 조인을 통해 간접 필터링.
    where__carrier_id__equal: Optional[int] = Field(
        default=None, description="부모 shipment.carrier_id 필터",
    )

    order__id: Optional[Literal["ASC", "DESC"]] = Field(default="DESC")
