# src/chat/repository.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from chat.const.sender import ChatSenderType
from chat.model import ChatMessageModel
from chat.schemas.request import PaginateChatMessageRequest


class ChatMessageRepository(TeamScopedRepoMixin):
    """driver 별 conversation 메시지 repository."""

    def __init__(self, db: AsyncSession, team_id: Optional[int]):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    # ── Read ─────────────────────────────────────────

    async def list_paginated_for_driver(
        self,
        request: PaginateChatMessageRequest,
        driver_user_id: int,
    ) -> CursorPaginationResult[ChatMessageModel]:
        """driver 의 conversation 메시지 페이지네이션 (최신부터 DESC)."""
        base = select(ChatMessageModel).where(
            ChatMessageModel.team_id == self._require_team(),
            ChatMessageModel.driver_user_id == driver_user_id,
            ChatMessageModel.is_active.is_(True),
        )
        return await self._common_service.paginate(
            request=request,
            model=ChatMessageModel,
            session=self.db,
            base_query=base,
            path=f"driver/chat/messages",
        )

    async def count_unread_for_driver(self, driver_user_id: int) -> int:
        """driver 의 읽지 않은 (DISPATCHER 또는 SYSTEM 발신 + read_at NULL) 메시지 수."""
        stmt = (
            select(func.count(ChatMessageModel.id))
            .where(
                ChatMessageModel.team_id == self._require_team(),
                ChatMessageModel.driver_user_id == driver_user_id,
                ChatMessageModel.is_active.is_(True),
                ChatMessageModel.sender_type != ChatSenderType.DRIVER,
                ChatMessageModel.read_at.is_(None),
            )
        )
        return int((await self.db.execute(stmt)).scalar_one() or 0)

    # ── Write ────────────────────────────────────────

    async def create(
        self,
        *,
        driver_user_id: int,
        sender_type: ChatSenderType,
        sender_user_id: Optional[int],
        content: str,
    ) -> ChatMessageModel:
        row = ChatMessageModel(
            team_id=self._require_team(),
            driver_user_id=driver_user_id,
            sender_type=sender_type,
            sender_user_id=sender_user_id,
            content=content,
            created_by_user_id=sender_user_id,
            updated_by_user_id=sender_user_id,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def mark_read_for_driver(
        self,
        driver_user_id: int,
        *,
        before_id: Optional[int] = None,
    ) -> int:
        """driver 가 읽음 처리. before_id 가 있으면 그 id 이하만, 없으면 전체."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(ChatMessageModel)
            .where(
                ChatMessageModel.team_id == self._require_team(),
                ChatMessageModel.driver_user_id == driver_user_id,
                ChatMessageModel.is_active.is_(True),
                ChatMessageModel.sender_type != ChatSenderType.DRIVER,
                ChatMessageModel.read_at.is_(None),
            )
            .values(read_at=now, updated_at=now)
        )
        if before_id is not None:
            stmt = stmt.where(ChatMessageModel.id <= before_id)
        result = await self.db.execute(stmt)
        return int(result.rowcount or 0)
