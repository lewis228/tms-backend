from __future__ import annotations
from typing import Optional, List
from pydantic import Field
from common.schemas.base import RequestSchema


class CreatePermissionGroupRequest(RequestSchema):
    name: str = Field(min_length=1, max_length=255)
    codes: List[str] = Field(default_factory=list)
