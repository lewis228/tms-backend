"""StreetTurn 스키마."""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.schema import BaseSchema
from app.models.enums import StreetTurnLinkType


class StreetTurnCreateRequest(BaseSchema):
    import_order_id: str
    export_order_id: str
    link_type: StreetTurnLinkType = StreetTurnLinkType.MANUAL
    note: str | None = Field(default=None, max_length=500)


class StreetTurnResponse(BaseSchema):
    id: str
    tenant_id: str
    import_order_id: str
    export_order_id: str
    container_number: str
    link_type: StreetTurnLinkType
    note: str | None
    created_at: datetime
    updated_at: datetime
