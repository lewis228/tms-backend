# src/api_key/repository.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.repository.tenant_scoped import TenantScopedRepoMixin
from api_key.model import ApiKeyModel


class ApiKeyRepository(TenantScopedRepoMixin):
    """tenant scoped API Key 레포.

    단 ``get_active_by_key`` 는 인증 진입점으로 호출 당시에는 tenant_id 를 모르므로,
    mixin 초기화 때 ``tenant_id=None`` 으로 생성한 뒤 **오직 이 한 메서드만** 사용한다.
    다른 메서드는 ``_require_tenant()`` 에서 실패시켜 오용을 막는다.
    """

    def __init__(self, db: AsyncSession, tenant_id: Optional[int]):
        super().__init__(tenant_id)
        self.db = db

    async def get_by_id(self, api_key_id: int) -> Optional[ApiKeyModel]:
        stmt = select(ApiKeyModel).where(
            ApiKeyModel.tenant_id == self._require_tenant(),
            ApiKeyModel.id == api_key_id,
            ApiKeyModel.is_active.is_(True),
        )
        return await self.db.scalar(stmt)

    async def get_active_by_key(self, key: str) -> Optional[ApiKeyModel]:
        """인증 핫 패스 — tenant_id 를 **모르는 시점**에 키 문자열만으로 조회.
        생성 시 ``tenant_id=None`` 을 넘긴 리포 인스턴스에서만 사용 가능. 키가
        유효하면 해당 row 의 ``tenant_id`` 로 상위 인증 결과를 채운다.

        활성 조건: ``is_active=True`` + ``expires_at`` 미경과.
        """
        now = datetime.now(timezone.utc)
        stmt = select(ApiKeyModel).where(
            ApiKeyModel.key == key,
            ApiKeyModel.is_active.is_(True),
        )
        row = await self.db.scalar(stmt)
        if row is None:
            return None
        if row.expires_at is not None and row.expires_at <= now:
            return None
        return row

    async def list_by_tenant(self) -> Sequence[ApiKeyModel]:
        """목록 — 현재 활성 키만.

        회수된 키 이력이 필요하면 별도 ``list_revoked`` 메서드 추가.
        """
        stmt = (
            select(ApiKeyModel)
            .where(
                ApiKeyModel.tenant_id == self._require_tenant(),
                ApiKeyModel.is_active.is_(True),
            )
            .order_by(ApiKeyModel.id.desc())
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def create(self, api_key: ApiKeyModel) -> ApiKeyModel:
        api_key.tenant_id = self._require_tenant()
        self.db.add(api_key)
        await self.db.flush()
        await self.db.refresh(api_key)
        return api_key

    async def touch_last_used(self, api_key_id: int) -> None:
        """회수된 키여도 단순 기록. tenant 체크는 이미 auth 단계에서 완료된 후라 생략."""
        await self.db.execute(
            update(ApiKeyModel)
            .where(ApiKeyModel.id == api_key_id)
            .values(last_used_at=datetime.now(timezone.utc))
        )
