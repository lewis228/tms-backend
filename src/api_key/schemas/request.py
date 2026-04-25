from __future__ import annotations
from typing import Optional
from pydantic import Field
from common.schemas.base import RequestSchema


class CreateApiKeyRequestSchema(RequestSchema):
    name: str = Field(min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=500)
    # Dropdown values from the frontend: 7 / 30 / 90 / 365 / null (never).
    # Server converts to ``expires_at = now + N days`` when non-null.
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=3650)


class UpdateApiKeyRequestSchema(RequestSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    description: Optional[str] = Field(None, max_length=500)
