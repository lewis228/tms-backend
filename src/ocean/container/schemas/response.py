from __future__ import annotations
from typing import Optional
from datetime import datetime
from common.schemas.base import ResponseSchema
from location.schemas.response import LocationResponseSchema
from carrier.schemas.response import CarrierResponseSchema


class ContainerResponseSchema(ResponseSchema):
    id: int
    shipment_id: int
    number: str
    size_type: Optional[str] = None
    size_type_code: Optional[str] = None
    status: Optional[str] = None
    physical_status: Optional[str] = None
    terminal_location_id: Optional[int] = None
    terminal_location: Optional[LocationResponseSchema] = None
    lfd: Optional[datetime] = None


class ContainerListRowResponseSchema(ResponseSchema):
    """전역 containers 리스트용 — 부모 shipment 의 주요 필드를 nested 로 포함.

    Terminal49 Containers 페이지처럼 Shipment / MBL / Carrier / POL / POD /
    ETA 컬럼을 화면에 뿌리려면 container row 1개당 해당 정보가 필요하다.
    하지만 전체 ShipmentResponseSchema 를 nested 로 내리면 페이로드가 무거워
    지므로 필요한 최소 필드만 추려서 별도 스키마로.
    """

    id: int
    shipment_id: int
    number: str
    size_type: Optional[str] = None
    size_type_code: Optional[str] = None
    status: Optional[str] = None
    physical_status: Optional[str] = None
    terminal_location: Optional[LocationResponseSchema] = None
    lfd: Optional[datetime] = None

    # 부모 shipment 에서 파생 — 리스트 컬럼 렌더에 직접 사용.
    mbl: str
    carrier: Optional[CarrierResponseSchema] = None
    pol_location: Optional[LocationResponseSchema] = None
    pod_location: Optional[LocationResponseSchema] = None
    eta: Optional[datetime] = None
