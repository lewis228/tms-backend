# src/chat/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal
from pydantic import Field

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema


class ChatMessageCreateRequest(RequestSchema):
    """driver / dispatcher 가 보내는 메시지."""
    content: str = Field(..., min_length=1, max_length=2000)


class PaginateChatMessageRequest(BasePaginationSchema):
    """driver 의 conversation 메시지 페이지네이션 (DESC = 최신부터)."""
    order__id: Optional[Literal["ASC", "DESC"]] = Field(default="DESC")
