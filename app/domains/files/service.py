"""File 서비스 — presigned PUT 발급 → 업로드 → finalize.

도메인 + object_id + kind 화이트리스트 검증.
"""
from __future__ import annotations

from app.core.exceptions import NotFoundError, ValidationError
from app.core.storage import (
    build_key,
    delete_object,
    head_object,
    presign_get,
    presign_put,
)
from app.domains.files.constants import (
    ATTACHABLE_DOMAINS,
    FILE_KINDS,
    PRESIGNED_GET_TTL_SECONDS,
    PRESIGNED_PUT_TTL_SECONDS,
)
from app.domains.files.models import File
from app.domains.files.repository import FileRepository
from app.domains.files.schema import (
    FileFinalizeRequest,
    FilePresignRequest,
)


class FileService:
    def __init__(self, repo: FileRepository, tenant_id: str) -> None:
        self.repo = repo
        self.tenant_id = tenant_id

    def _validate(self, payload: FilePresignRequest) -> None:
        if payload.domain not in ATTACHABLE_DOMAINS:
            raise ValidationError(f"domain '{payload.domain}' not attachable")
        if payload.kind not in FILE_KINDS:
            raise ValidationError(f"kind '{payload.kind}' invalid")

    async def presign_upload(
        self, payload: FilePresignRequest, *, uploader_id: str
    ) -> tuple[File, str, dict[str, str], int]:
        self._validate(payload)
        key = build_key(
            tenant_id=self.tenant_id,
            domain=payload.domain,
            object_id=payload.object_id,
            filename=payload.filename,
        )
        f = File(
            tenant_id=self.tenant_id,
            domain=payload.domain,
            object_id=payload.object_id,
            kind=payload.kind,
            storage_key=key,
            filename=payload.filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            uploaded_by=uploader_id,
            note=payload.note,
        )
        await self.repo.create(f)
        await self.repo.db.commit()
        await self.repo.db.refresh(f)
        url, headers = presign_put(key, payload.content_type, PRESIGNED_PUT_TTL_SECONDS)
        return f, url, headers, PRESIGNED_PUT_TTL_SECONDS

    async def finalize(self, payload: FileFinalizeRequest) -> File:
        f = await self.repo.get_by_id(payload.file_id)
        if not f:
            raise NotFoundError("File not found")
        head = head_object(f.storage_key)
        if head is None:
            raise ValidationError("Object not yet uploaded", code="ERR_FILE_NOT_UPLOADED")
        actual_size = head.get("ContentLength", 0)
        if actual_size:
            f.size_bytes = actual_size
        await self.repo.db.flush()
        await self.repo.db.commit()
        await self.repo.db.refresh(f)
        return f

    async def get(self, id_: str) -> File:
        f = await self.repo.get_by_id(id_)
        if not f:
            raise NotFoundError("File not found")
        return f

    async def list_by_attach(self, domain: str, object_id: str) -> list[File]:
        if domain not in ATTACHABLE_DOMAINS:
            raise ValidationError(f"domain '{domain}' not attachable")
        return await self.repo.list_by_attach(domain, object_id)

    def download_url(self, f: File) -> str:
        return presign_get(f.storage_key, PRESIGNED_GET_TTL_SECONDS)

    async def delete(self, id_: str) -> None:
        f = await self.get(id_)
        await self.repo.soft_delete(f)
        await self.repo.db.commit()
        delete_object(f.storage_key)
