from __future__ import annotations

from datetime import datetime
from typing import Optional

from common.schemas.base import ResponseSchema


class VesselPositionResponseSchema(ResponseSchema):
    latitude: float
    longitude: float
    speed_knots: Optional[float] = None
    heading_degrees: Optional[float] = None
    navigation_status: Optional[str] = None
    reported_at: Optional[datetime] = None


class VesselResponseSchema(ResponseSchema):
    id: int
    mmsi: Optional[str] = None
    imo_number: Optional[str] = None
    name: str
    flag: Optional[str] = None
    call_sign: Optional[str] = None
    length_m: Optional[int] = None
    breadth_m: Optional[int] = None
    gross_tonnage: Optional[int] = None
    vessel_type_code: Optional[int] = None
    year_built: Optional[int] = None
    owner: Optional[str] = None
    position: Optional[VesselPositionResponseSchema] = None
