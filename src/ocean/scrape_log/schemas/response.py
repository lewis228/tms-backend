from __future__ import annotations
from typing import Optional, Any
from datetime import datetime
from common.schemas.base import ResponseSchema


class ScrapeLogResponseSchema(ResponseSchema):
    id: int
    shipment_id: int
    source: str
    result_json: Optional[Any] = None
    confidence: Optional[str] = None
    error_message: Optional[str] = None
    scraped_at: Optional[datetime] = None
