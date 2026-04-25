"""Location 스키마."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.core.schema import BaseSchema
from app.models.enums import LocationKind


class LocationCreateRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    kind: LocationKind
    address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    customer_id: str | None = None
    note: str | None = Field(default=None, max_length=500)


class LocationUpdateRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    kind: LocationKind | None = None
    address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    customer_id: str | None = None
    is_active: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class LocationResponse(BaseSchema):
    id: str
    tenant_id: str
    name: str
    kind: LocationKind
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    customer_id: str | None
    is_active: bool
    note: str | None
    created_at: datetime
    updated_at: datetime
