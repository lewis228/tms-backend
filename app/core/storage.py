"""S3/MinIO 어댑터.

boto3 client 싱글턴 + 키 생성 + presigned URL 발급.
endpoint 는 settings.minio_endpoint, 버킷은 settings.minio_bucket.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import boto3
from botocore.client import Config

from app.config import settings

_client = None


def get_s3():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint or None,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name=settings.aws_region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
    return _client


def build_key(*, tenant_id: str, domain: str, object_id: str, filename: str) -> str:
    safe = filename.replace("/", "_").replace("\\", "_")
    yyyymm = datetime.now(timezone.utc).strftime("%Y/%m")
    return f"{tenant_id}/{domain}/{object_id}/{yyyymm}/{uuid.uuid4().hex}_{safe}"


def presign_put(key: str, content_type: str, ttl: int) -> tuple[str, dict[str, str]]:
    url = get_s3().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.minio_bucket,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=ttl,
    )
    return url, {"Content-Type": content_type}


def presign_get(key: str, ttl: int) -> str:
    return get_s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.minio_bucket, "Key": key},
        ExpiresIn=ttl,
    )


def put_object_bytes(key: str, body: bytes, content_type: str) -> int:
    """객체스토어에 직접 업로드. 모바일 driver 의 멀티파트 업로드용.

    presign 흐름과 달리 클라이언트가 한 번의 multipart 요청으로 업로드하면
    백엔드가 이를 받아 그대로 객체스토어에 put 한다. 반환값은 저장된 바이트 수.
    """
    get_s3().put_object(
        Bucket=settings.minio_bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )
    return len(body)


def head_object(key: str) -> dict | None:
    try:
        return get_s3().head_object(Bucket=settings.minio_bucket, Key=key)
    except Exception:
        return None


def delete_object(key: str) -> None:
    try:
        get_s3().delete_object(Bucket=settings.minio_bucket, Key=key)
    except Exception:
        pass
