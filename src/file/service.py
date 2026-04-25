from __future__ import annotations
from typing import List, Optional
import mimetypes
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from file.model import FileAssetModel
from file.const.domains import FileDomain
from file.const.consts import (
    get_s3_client, MINIO_BUCKET, MINIO_TEMP_PREFIX,
    PRESIGNED_UPLOAD_TTL, PRESIGNED_DOWNLOAD_TTL,
    ObjectKeyBuilder, temp_key, rewrite_presigned_url, public_direct_url,
)
from file.schemas.response import UploadFileInfo


class FileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def generate_upload_urls(self, filenames: List[str]) -> tuple[str, List[UploadFileInfo]]:
        s3 = get_s3_client()
        token = uuid.uuid4().hex
        files = []
        for fn in filenames:
            key = temp_key(token, fn)
            url = s3.generate_presigned_url(
                "put_object", Params={"Bucket": MINIO_BUCKET, "Key": key},
                ExpiresIn=PRESIGNED_UPLOAD_TTL,
            )
            files.append(UploadFileInfo(filename=fn, upload_url=rewrite_presigned_url(url), key=key))
        return token, files

    def generate_download_url(self, logical_path: str, is_public: bool = False) -> str:
        if is_public:
            return public_direct_url(logical_path)
        s3 = get_s3_client()
        url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": MINIO_BUCKET, "Key": logical_path},
            ExpiresIn=PRESIGNED_DOWNLOAD_TTL,
        )
        return rewrite_presigned_url(url)

    def inject_file_urls(self, files) -> None:
        for f in files:
            f.url = self.generate_download_url(f.logical_path, f.is_public)

    async def commit(
        self, *, team_id: Optional[int], domain: FileDomain, object_id: int,
        subdir: str = "", add_temp_keys: List[str] = None,
        remove_file_ids: List[int] = None, actor_user_id: int, is_public: bool = False,
    ) -> None:
        s3 = get_s3_client()
        builder = ObjectKeyBuilder(team_id=team_id, domain=domain, object_id=object_id, subdir=subdir, is_public=is_public)

        if remove_file_ids:
            for fid in remove_file_ids:
                await self.db.execute(
                    update(FileAssetModel).where(FileAssetModel.id == fid).values(is_active=False, updated_by_user_id=actor_user_id)
                )

        if add_temp_keys:
            for tk in add_temp_keys:
                filename = tk.split("/")[-1] if "/" in tk else tk
                dest_key = builder.key(filename)
                try:
                    s3.copy_object(Bucket=MINIO_BUCKET, CopySource={"Bucket": MINIO_BUCKET, "Key": tk}, Key=dest_key)
                    s3.delete_object(Bucket=MINIO_BUCKET, Key=tk)
                except Exception:
                    continue
                mime, _ = mimetypes.guess_type(filename)
                try:
                    head = s3.head_object(Bucket=MINIO_BUCKET, Key=dest_key)
                    size = head.get("ContentLength", 0)
                except Exception:
                    size = 0
                asset = FileAssetModel(
                    team_id=team_id, domain=domain, object_id=object_id, subdir=subdir,
                    filename=filename, size=size, mime=mime or "application/octet-stream",
                    is_public=is_public, logical_path=dest_key,
                    created_by_user_id=actor_user_id, updated_by_user_id=actor_user_id,
                )
                self.db.add(asset)
            await self.db.flush()

    async def soft_deactivate_by_object(self, *, team_id: Optional[int], domain: FileDomain, object_id: int, actor_user_id: int) -> None:
        stmt = (
            update(FileAssetModel)
            .where(FileAssetModel.domain == domain, FileAssetModel.object_id == object_id, FileAssetModel.is_active.is_(True))
            .values(is_active=False, updated_by_user_id=actor_user_id)
        )
        if team_id is not None:
            stmt = stmt.where(FileAssetModel.team_id == team_id)
        await self.db.execute(stmt)
