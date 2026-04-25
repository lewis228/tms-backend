from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from common.const.settings import (
    settings, MINIO_REGION, MINIO_TEMP_PREFIX,
    MINIO_PRESIGNED_UPLOAD_TTL, MINIO_PRESIGNED_DOWNLOAD_TTL,
)
from file.const.domains import FileDomain


@lru_cache(maxsize=1)
def get_s3_client():
    kwargs: dict = {
        "config": Config(signature_version="s3v4"),
        "region_name": settings.AWS_REGION or MINIO_REGION,
    }
    # endpoint_url이 비어 있으면 AWS S3 기본 엔드포인트 사용 (EC2).
    if settings.MINIO_ENDPOINT:
        kwargs["endpoint_url"] = settings.MINIO_ENDPOINT
    # access key가 비어 있으면 boto3 default credential chain(IAM Role) 사용.
    if settings.MINIO_ACCESS_KEY and settings.MINIO_SECRET_KEY:
        kwargs["aws_access_key_id"] = settings.MINIO_ACCESS_KEY
        kwargs["aws_secret_access_key"] = settings.MINIO_SECRET_KEY
    return boto3.client("s3", **kwargs)


MINIO_BUCKET = settings.MINIO_BUCKET
PRESIGNED_UPLOAD_TTL = MINIO_PRESIGNED_UPLOAD_TTL
PRESIGNED_DOWNLOAD_TTL = MINIO_PRESIGNED_DOWNLOAD_TTL


def rewrite_presigned_url(url: str) -> str:
    public_url = settings.MINIO_PUBLIC_URL
    if not public_url or not settings.MINIO_ENDPOINT:
        return url
    return url.replace(settings.MINIO_ENDPOINT.rstrip("/"), public_url.rstrip("/"), 1)


def public_direct_url(logical_path: str) -> str:
    endpoint = settings.MINIO_PUBLIC_URL or settings.MINIO_ENDPOINT
    if not endpoint:
        # EC2 → AWS S3 가상 호스티드 URL
        region = settings.AWS_REGION or MINIO_REGION
        return f"https://{MINIO_BUCKET}.s3.{region}.amazonaws.com/{logical_path}"
    return f"{endpoint.rstrip('/')}/{MINIO_BUCKET}/{logical_path}"


def ensure_bucket_exists() -> None:
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=MINIO_BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=MINIO_BUCKET)


def clear_bucket() -> int:
    s3 = get_s3_client()
    deleted_count = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=MINIO_BUCKET):
        contents = page.get("Contents", [])
        if not contents:
            continue
        objects = [{"Key": obj["Key"]} for obj in contents]
        s3.delete_objects(Bucket=MINIO_BUCKET, Delete={"Objects": objects})
        deleted_count += len(objects)
    return deleted_count


@dataclass
class ObjectKeyBuilder:
    team_id: Optional[int]
    domain: FileDomain
    object_id: int
    subdir: str = ""
    is_public: bool = False

    @property
    def visibility(self) -> str:
        return "public" if self.is_public else "private"

    def key_prefix(self) -> str:
        if self.team_id is not None:
            base = f"{self.visibility}/team-{self.team_id}/{self.domain.value}/{self.object_id}"
        else:
            base = f"{self.visibility}/{self.domain.value}/{self.object_id}"
        if self.subdir:
            return f"{base}/{self.subdir}"
        return base

    def key(self, filename: str) -> str:
        prefix = self.key_prefix()
        return f"{prefix}/{filename}" if filename else prefix


def temp_key(token: str, filename: str) -> str:
    return f"{MINIO_TEMP_PREFIX}/{token}/{filename}"


def temp_prefix(token: str) -> str:
    return f"{MINIO_TEMP_PREFIX}/{token}/"
