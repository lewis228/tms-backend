from __future__ import annotations
from typing import List
from pydantic import Field
from common.schemas.base import RequestSchema


class UploadUrlRequestSchema(RequestSchema):
    filenames: List[str] = Field(..., min_length=1)
