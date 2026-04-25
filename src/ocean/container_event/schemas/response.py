from __future__ import annotations
from typing import Optional
from datetime import datetime
from common.schemas.base import ResponseSchema
from location.schemas.response import LocationResponseSchema


class ContainerEventResponseSchema(ResponseSchema):
    id: int
    shipment_id: int
    container_id: int
    timestamp: Optional[datetime] = None
    location_id: Optional[int] = None
    location: Optional[LocationResponseSchema] = None
    description: Optional[str] = None
    event_type: Optional[str] = None
    event_type_code: Optional[str] = None
