"""Terminal 스키마."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.core.schema import BaseSchema


class TerminalCreateRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=32)
    address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    note: str | None = Field(default=None, max_length=500)


class TerminalUpdateRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=32)
    address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    is_active: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class TerminalResponse(BaseSchema):
    id: str
    tenant_id: str
    name: str
    code: str | None
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    is_active: bool
    note: str | None
    created_at: datetime
    updated_at: datetime
