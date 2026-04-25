from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, ConfigDict


class LocationResponseSchema(BaseModel):
    """Public location representation. Embedded inside shipment / container /
    event responses when the FK is resolved."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    unlocode: Optional[str] = None
    name: str
    country_code: str
    subdivision: Optional[str] = None
    kind: str
    parent_location_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    iata: Optional[str] = None
    is_supported: bool
