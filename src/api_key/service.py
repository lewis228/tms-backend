# src/api_key/service.py
from __future__ import annotations
import secrets
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from api_key.model import ApiKeyModel
from api_key.repository import ApiKeyRepository
from api_key.schemas.response import (
    ApiKeyListItemResponseSchema,
    ApiKeyCreatedResponseSchema,
)


# "tms_" + 43 url-safe chars ≈ 256 bits of entropy; matches Stripe-style keys.
KEY_PREFIX_LITERAL = "tms_"
# Number of leading characters exposed in list views (full prefix incl. literal).
PREFIX_DISPLAY_LEN = 12


def _generate_key() -> tuple[str, str]:
    """Return (full_key, prefix). Prefix is the leading slice users see
    after the first reveal so they can visually distinguish keys."""
    token = secrets.token_urlsafe(32)
    full = f"{KEY_PREFIX_LITERAL}{token}"
    prefix = full[:PREFIX_DISPLAY_LEN]
    return full, prefix


class ApiKeyService:
    """team scoped API Key 서비스. 생성자에서 ``team_id`` 를 받는다."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = ApiKeyRepository(db, team_id)

    async def create(
        self,
        *,
        name: str,
        description: str | None,
        expires_in_days: int | None,
        created_by_user_id: int,
    ) -> ApiKeyCreatedResponseSchema:
        full_key, prefix = _generate_key()
        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        row = ApiKeyModel(
            name=name,
            description=description,
            key=full_key,
            prefix=prefix,
            expires_at=expires_at,
            created_by_user_id=created_by_user_id,
        )
        row = await self.repo.create(row)
        return ApiKeyCreatedResponseSchema.model_validate(row)

    async def list_by_team(self) -> Sequence[ApiKeyListItemResponseSchema]:
        rows = await self.repo.list_by_team()
        return [ApiKeyListItemResponseSchema.model_validate(r) for r in rows]

    async def get(self, api_key_id: int) -> ApiKeyListItemResponseSchema:
        row = await self._load_active(api_key_id)
        return ApiKeyListItemResponseSchema.model_validate(row)

    async def update(
        self,
        api_key_id: int,
        *,
        name: str | None,
        description: str | None,
        actor_user_id: int | None = None,
    ) -> ApiKeyListItemResponseSchema:
        """활성 키의 name/description 수정. **회수된(비활성) 키는 수정 불가**.
        ``updated_at`` 이 회수 시점의 의미를 유지하도록 하기 위함."""
        row = await self._load_active(api_key_id)
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return ApiKeyListItemResponseSchema.model_validate(row)

    async def revoke(self, api_key_id: int, actor_user_id: int | None = None) -> None:
        """키 회수 (soft-delete). ``is_active=False`` 로 표시하고 ``updated_at`` 자동 갱신.
        이미 회수된 키에 대한 호출은 404 — 멱등성은 클라이언트가 조회로 확인."""
        row = await self._load_active(api_key_id)
        row.is_active = False
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()

    async def _load_active(self, api_key_id: int) -> ApiKeyModel:
        """활성 키만 반환. 회수된 키는 NotFound 로 응답 (존재 여부 누출 방지)."""
        row = await self.repo.get_by_id(api_key_id)
        if row is None:
            raise NotFoundException("ApiKey")
        return row
