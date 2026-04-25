from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database.dependencies import get_read_db
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from auth.dependencies.rate_limit import rate_limit
from file.schemas.request import UploadUrlRequestSchema
from file.schemas.response import UploadUrlResponseSchema
from file.service import FileService

router = APIRouter(prefix="/api/v1/file", tags=["file"])


@router.post("/upload-urls", response_model=UploadUrlResponseSchema)
async def get_upload_urls(
    body: UploadUrlRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    db: AsyncSession = Depends(get_read_db),
):
    svc = FileService(db)
    token, files = svc.generate_upload_urls(body.filenames)
    return UploadUrlResponseSchema(token=token, files=files)
