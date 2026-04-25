from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class CarrierResponseSchema(BaseModel):
    """Public carrier representation. Returned by GET /carriers and also
    nested inside shipment responses when the carrier is resolved."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    scac: str
    name: str
    mbl_prefixes: Optional[List[str]] = None
    scraper_key: Optional[str] = None
    tracking_url: Optional[str] = None
    logo_url: Optional[str] = None
    display_order: int
    is_supported: bool
