"""Vessel 스키마."""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.schema import BaseSchema


class VesselCreateRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    imo_number: str | None = Field(default=None, max_length=16)
    line: str | None = None
    note: str | None = Field(default=None, max_length=500)


class VesselUpdateRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    imo_number: str | None = Field(default=None, max_length=16)
    line: str | None = None
    is_active: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class VesselResponse(BaseSchema):
    id: str
    tenant_id: str
    name: str
    imo_number: str | None
    line: str | None
    is_active: bool
    note: str | None
    created_at: datetime
    updated_at: datetime
