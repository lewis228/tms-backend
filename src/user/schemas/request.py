from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import Field
from common.pagination.schemas.pagination_request import BasePaginationSchema
from common.schemas.base import RequestSchema


class PaginateUserRequestSchema(BasePaginationSchema):
    order__email: Optional[Literal["ASC", "DESC"]] = None
    order__created_at: Optional[Literal["ASC", "DESC"]] = None
    where__email__i_like: Optional[str] = Field(default=None)
    where__role__equal: Optional[str] = Field(default=None)


class UserProfileUpdateRequest(RequestSchema):
    name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    event_notification_enabled: Optional[bool] = None
    language: Optional[str] = Field(None, max_length=10)
    temp_keys: List[str] = Field(default_factory=list)
    remove_file_ids: List[int] = Field(default_factory=list)
