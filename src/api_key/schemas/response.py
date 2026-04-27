# src/api_key/schemas/response.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal

from common.schemas.base import ResponseSchema


class ApiKeyListItemResponseSchema(ResponseSchema):
    """Standard list/detail payload. The full ``key`` is intentionally
    omitted — only the prefix is safe to display after creation.

    회수된 키는 is_active=False. 회수 시점은 updated_at 으로 추적.
    """

    id: int
    tenant_id: int
    name: str
    description: Optional[str] = None
    prefix: str
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None


class ApiKeyCreatedResponseSchema(ApiKeyListItemResponseSchema):
    """Returned ONLY from POST /api-keys. Includes the full ``key`` so
    the caller can copy it once; subsequent fetches will never expose it."""

    key: str


class ApiKeyDeleteResponseSchema(ResponseSchema):
    """회수(소프트 삭제) 응답."""
    id: int
    object: Literal["api_key"] = "api_key"
    revoked: bool = True
