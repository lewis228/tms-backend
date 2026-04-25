from __future__ import annotations
from typing import List, Optional
from common.schemas.base import ResponseSchema


class UploadFileInfo(ResponseSchema):
    filename: str
    upload_url: str
    key: str


class UploadUrlResponseSchema(ResponseSchema):
    token: str
    files: List[UploadFileInfo]


class DownloadUrlResponseSchema(ResponseSchema):
    url: str
