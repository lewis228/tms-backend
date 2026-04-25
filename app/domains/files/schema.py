"""File 스키마 + 업로드 (presigned URL 또는 멀티파트)."""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.schema import BaseSchema


class FilePresignRequest(BaseSchema):
    domain: str = Field(..., max_length=64)
    object_id: str
    kind: str = Field(..., max_length=32)
    filename: str = Field(..., max_length=255)
    content_type: str = Field(..., max_length=128)
    size_bytes: int = Field(..., ge=0)
    note: str | None = Field(default=None, max_length=500)


class FilePresignResponse(BaseSchema):
    file_id: str
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str]
    expires_in: int


class FileFinalizeRequest(BaseSchema):
    """presign 받은 후 실제 업로드 끝났음을 알리는 콜백 (옵션)."""

    file_id: str
    size_bytes: int | None = None


class FileResponse(BaseSchema):
    id: str
    tenant_id: str
    domain: str
    object_id: str
    kind: str
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by: str | None
    note: str | None
    download_url: str | None = None
    created_at: datetime
    updated_at: datetime
