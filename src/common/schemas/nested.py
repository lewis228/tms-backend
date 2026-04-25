from __future__ import annotations
from typing import Optional, List
from common.schemas.base import ResponseSchema


class FileNestedSchema(ResponseSchema):
    id: int
    domain: str
    object_id: int
    subdir: str
    filename: str
    size: int
    mime: str
    is_public: bool
    logical_path: str
    url: Optional[str] = None


class UserNestedSchema(ResponseSchema):
    id: int
    email: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None


class UserNestedWithFilesSchema(UserNestedSchema):
    files: List[FileNestedSchema] = []


class PermissionGroupNestedSchema(ResponseSchema):
    id: int
    name: str
