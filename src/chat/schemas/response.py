# src/chat/schemas/response.py
from __future__ import annotations
from datetime import datetime
from typing import Optional

from common.schemas.base import ResponseSchema
from chat.const.sender import ChatSenderType


class ChatMessageResponseSchema(ResponseSchema):
    id: int
    driver_user_id: int
    sender_type: ChatSenderType
    sender_user_id: Optional[int] = None
    content: str
    read_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
