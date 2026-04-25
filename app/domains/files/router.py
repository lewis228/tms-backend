"""Files 라우터 — 인증 사용자.

업로드 흐름: POST /presign → 클라이언트가 받은 URL 로 PUT → POST /finalize.
조회: GET /files/{id}, GET /files?domain=...&objectId=...
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DB, DBReadOnly, TenantID
from app.domains.files.repository import FileRepository
from app.domains.files.schema import (
    FileFinalizeRequest,
    FilePresignRequest,
    FilePresignResponse,
    FileResponse,
)
from app.domains.files.service import FileService

router = APIRouter(prefix="/api/v1/files", tags=["files"])


def _svc(db, *, tenant_id: str) -> FileService:
    return FileService(FileRepository(db, tenant_id=tenant_id), tenant_id)


def _to_resp(svc: FileService, f, *, include_url: bool = False) -> FileResponse:
    base = FileResponse.model_validate(f)
    if include_url:
        base = base.model_copy(update={"download_url": svc.download_url(f)})
    return base


@router.post("/presign", response_model=FilePresignResponse, status_code=201)
async def presign_upload(
    payload: FilePresignRequest, user: CurrentUser, tenant_id: TenantID, db: DB
):
    svc = _svc(db, tenant_id=tenant_id)
    f, url, headers, ttl = await svc.presign_upload(payload, uploader_id=user.user_id)
    return FilePresignResponse(
        file_id=f.id, upload_url=url, headers=headers, expires_in=ttl
    )


@router.post("/finalize", response_model=FileResponse)
async def finalize_upload(payload: FileFinalizeRequest, tenant_id: TenantID, db: DB):
    svc = _svc(db, tenant_id=tenant_id)
    f = await svc.finalize(payload)
    return _to_resp(svc, f, include_url=True)


@router.get("", response_model=list[FileResponse])
async def list_attached(
    tenant_id: TenantID,
    db: DBReadOnly,
    domain: str = Query(...),
    object_id: str = Query(..., alias="objectId"),
):
    svc = _svc(db, tenant_id=tenant_id)
    files = await svc.list_by_attach(domain, object_id)
    return [_to_resp(svc, f, include_url=True) for f in files]


@router.get("/{id}", response_model=FileResponse)
async def get_file(id: str, tenant_id: TenantID, db: DBReadOnly):
    svc = _svc(db, tenant_id=tenant_id)
    f = await svc.get(id)
    return _to_resp(svc, f, include_url=True)


@router.delete("/{id}", status_code=204)
async def delete_file(id: str, tenant_id: TenantID, db: DB):
    await _svc(db, tenant_id=tenant_id).delete(id)
