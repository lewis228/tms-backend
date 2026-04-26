# src/notification/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal, List, Any
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from notification.const.channel import NotificationChannel, NotificationStatus


class NotificationCreateRequest(RequestSchema):
    user_id: int | None = None
    channel: NotificationChannel = NotificationChannel.PUSH
    event_type: str = Field(..., max_length=64)
    title: str = Field(..., max_length=255)
    body: str | None = None
    payload: dict[str, Any] | None = None


class NotificationUpdateRequest(RequestSchema):
    is_read: bool | None = None
    title: str | None = Field(default=None, max_length=255)
    body: str | None = None


class PaginateNotificationRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__user_id__equal: Optional[int] = None
    where__is_read__equal: Optional[bool] = None
    where__event_type__i_like: Optional[str] = None
    where__channel__equal: Optional[NotificationChannel] = None
    where__status__equal: Optional[NotificationStatus] = None


class NotificationBulkCreateRequest(RequestSchema):
    items: List[NotificationCreateRequest] = Field(..., min_length=1, max_length=100)


class NotificationBulkUpdateItem(NotificationUpdateRequest):
    id: int


class NotificationBulkUpdateRequest(RequestSchema):
    items: List[NotificationBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class NotificationBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
