# src/notification/schemas/response.py
from __future__ import annotations
from datetime import datetime
from typing import Literal, List, Optional, Any
from common.schemas.base import ResponseSchema
from notification.const.channel import NotificationChannel, NotificationStatus


class NotificationResponseSchema(ResponseSchema):
    id: int
    user_id: int | None = None
    channel: NotificationChannel
    status: NotificationStatus
    event_type: str
    title: str
    body: str | None = None
    payload: dict[str, Any] | None = None
    is_read: bool
    read_at: datetime | None = None
    sent_at: datetime | None = None
    is_active: bool


class NotificationDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["notification"] = "notification"
    deleted: bool = True
    soft_deleted: bool = False


class UnreadCountResponseSchema(ResponseSchema):
    count: int


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[NotificationResponseSchema] = None
    error: Optional[str] = None


class BulkDeleteResultItem(ResponseSchema):
    id: int
    success: bool
    soft_deleted: bool = False
    error: Optional[str] = None


class BulkSummary(ResponseSchema):
    total: int
    succeeded: int
    failed: int


class NotificationBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class NotificationBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class NotificationBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
