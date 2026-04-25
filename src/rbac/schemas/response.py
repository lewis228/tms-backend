from __future__ import annotations
from typing import List, Optional
from common.schemas.base import ResponseSchema


class PermissionGroupResponseSchema(ResponseSchema):
    id: int
    name: str
    is_admin: bool
    is_system: bool
    system_key: Optional[str] = None
    version: int = 1
    codes: List[str] = []
