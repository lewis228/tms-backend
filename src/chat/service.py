# src/chat/service.py
"""채팅 service — driver / dispatcher 메시지 + 자동 응답 시뮬레이션 (데모용)."""
from __future__ import annotations
import asyncio
import random
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from common.pagination.schemas.pagination_response import CursorPaginationResult
from chat.const.sender import ChatSenderType
from chat.repository import ChatMessageRepository
from chat.schemas.request import (
    ChatMessageCreateRequest,
    PaginateChatMessageRequest,
)
from chat.schemas.response import ChatMessageResponseSchema


# 데모용 자동 응답 풀 (관제사 톤)
_AUTO_REPLIES = [
    "확인했습니다.",
    "네, 알겠습니다. 안전 운행 부탁드립니다.",
    "지금 확인해드릴게요. 잠시만요.",
    "수고 많으십니다. 도착하시면 다시 한 번 알려주세요.",
    "네, 다음 배차 준비 중입니다.",
    "확인했습니다. 주의해서 운행해 주세요.",
]


class ChatService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = ChatMessageRepository(db, team_id)

    # ── Read ─────────────────────────────────────────

    async def list_paginated_for_driver(
        self,
        request: PaginateChatMessageRequest,
        driver_user_id: int,
    ) -> CursorPaginationResult[ChatMessageResponseSchema]:
        result = await self.repo.list_paginated_for_driver(request, driver_user_id)
        result.data = [ChatMessageResponseSchema.model_validate(m) for m in result.data]
        return result

    async def unread_count_for_driver(self, driver_user_id: int) -> int:
        return await self.repo.count_unread_for_driver(driver_user_id)

    # ── Write — driver 가 보낸 메시지 ────────────────

    async def send_from_driver(
        self,
        body: ChatMessageCreateRequest,
        *,
        driver_user_id: int,
    ) -> ChatMessageResponseSchema:
        """driver 가 메시지 전송 + 1.5초 후 자동 응답 (데모용 시뮬레이션)."""
        msg = await self.repo.create(
            driver_user_id=driver_user_id,
            sender_type=ChatSenderType.DRIVER,
            sender_user_id=driver_user_id,
            content=body.content,
        )
        result = ChatMessageResponseSchema.model_validate(msg)

        # 자동 응답 (fire-and-forget) — 데모 시연 시 실시간 느낌
        # 실제 운영은 dispatcher 가 web 에서 직접 답장.
        asyncio.create_task(
            self._enqueue_auto_reply(driver_user_id=driver_user_id),
        )
        return result

    # ── Write — dispatcher / system 발신 ─────────────

    async def send_from_dispatcher(
        self,
        body: ChatMessageCreateRequest,
        *,
        driver_user_id: int,
        dispatcher_user_id: int,
    ) -> ChatMessageResponseSchema:
        msg = await self.repo.create(
            driver_user_id=driver_user_id,
            sender_type=ChatSenderType.DISPATCHER,
            sender_user_id=dispatcher_user_id,
            content=body.content,
        )
        return ChatMessageResponseSchema.model_validate(msg)

    async def send_system_message(
        self,
        *,
        driver_user_id: int,
        content: str,
    ) -> ChatMessageResponseSchema:
        msg = await self.repo.create(
            driver_user_id=driver_user_id,
            sender_type=ChatSenderType.SYSTEM,
            sender_user_id=None,
            content=content,
        )
        return ChatMessageResponseSchema.model_validate(msg)

    # ── Mark read ────────────────────────────────────

    async def mark_read(
        self,
        driver_user_id: int,
        *,
        before_id: Optional[int] = None,
    ) -> int:
        return await self.repo.mark_read_for_driver(driver_user_id, before_id=before_id)

    # ── 자동 응답 시뮬레이션 (private) ───────────────

    async def _enqueue_auto_reply(self, *, driver_user_id: int) -> None:
        """1.5초 후 자동 응답 INSERT.

        ⚠️ 데모용. 별도 Session 에서 실행되므로 새 session 필요.
        실제 운영에선 제거.
        """
        try:
            await asyncio.sleep(1.5)
            # 별도 session — 원래 session 은 이미 commit/close 되었을 수 있음
            from database.mysql_connection import write_session_maker
            async with write_session_maker() as new_db:
                repo = ChatMessageRepository(new_db, self.team_id)
                await repo.create(
                    driver_user_id=driver_user_id,
                    sender_type=ChatSenderType.DISPATCHER,
                    sender_user_id=None,
                    content=random.choice(_AUTO_REPLIES),
                )
                await new_db.commit()
        except Exception:
            # 데모용이라 silent fail
            pass
