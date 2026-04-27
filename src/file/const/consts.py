# src/file/const/consts.py
"""
MinIO 기반 파일 저장소 설정 및 유틸리티

기존 로컬 파일시스템 기반 코드를 MinIO(S3 호환) 기반으로 전환.
- boto3 클라이언트로 MinIO 접근
- Presigned URL로 업로드/다운로드
- 로컬 경로 대신 오브젝트 키(key) 사용

 team_id=None 지원:
- User 도메인은 팀과 무관하므로 team_id=NULL
- 경로: private/{domain}/{object_id}/... (team- prefix 없음)
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from common.const.settings import settings
from file.const.domains import FileDomain


# ===== MinIO 클라이언트 (싱글톤) =====
@lru_cache(maxsize=1)
def get_s3_client():
    """
    MinIO S3 호환 클라이언트 생성 (앱 전체에서 하나만 사용)
    
    - endpoint_url: MinIO 서버 주소
    - signature_version: S3v4 (MinIO 필수)
    - region_name: MinIO는 아무 값이나 OK
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name=settings.MINIO_REGION,
    )


# ===== 설정값 참조 =====
MINIO_BUCKET = settings.MINIO_BUCKET
MINIO_TEMP_PREFIX = settings.MINIO_TEMP_PREFIX
PRESIGNED_UPLOAD_TTL = settings.MINIO_PRESIGNED_UPLOAD_TTL
PRESIGNED_DOWNLOAD_TTL = settings.MINIO_PRESIGNED_DOWNLOAD_TTL


def rewrite_presigned_url(url: str) -> str:
    """
    Presigned URL의 내부 endpoint를 외부 URL로 변환

    MINIO_PUBLIC_URL이 설정되어 있으면:
    - http://minio:9000/bucket/key?sig=...
    → https://www.binflow.io/minio/bucket/key?sig=...

    설정되지 않으면 원본 URL 그대로 반환
    """
    public_url = settings.MINIO_PUBLIC_URL
    if not public_url:
        return url

    # 내부 endpoint를 외부 URL로 치환
    internal_endpoint = settings.MINIO_ENDPOINT.rstrip("/")
    public_endpoint = public_url.rstrip("/")

    return url.replace(internal_endpoint, public_endpoint, 1)


def public_direct_url(logical_path: str) -> str:
    """
    public/ prefix 파일의 직접 URL 생성 (서명 없음, 만료 없음)

    개발: http://localhost:9000/binflow/public/branding/logo.png
    운영: https://cdn.binflow.com/binflow/public/branding/logo.png
         (MINIO_PUBLIC_URL 설정 시 자동 변환)
    """
    endpoint = settings.MINIO_PUBLIC_URL or settings.MINIO_ENDPOINT
    return f"{endpoint.rstrip('/')}/{MINIO_BUCKET}/{logical_path}"


# ===== 버킷 초기화 (앱 시작 시 호출) =====
def ensure_bucket_exists() -> None:
    """
    버킷이 없으면 생성. 앱 시작(lifespan)에서 호출 권장.
    """
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=MINIO_BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=MINIO_BUCKET)


def clear_bucket() -> int:
    """
    버킷의 모든 오브젝트 삭제 (개발 환경용)
    
    Returns:
        삭제된 오브젝트 수
    """
    s3 = get_s3_client()
    deleted_count = 0
    
    # 페이지네이터로 모든 오브젝트 순회
    paginator = s3.get_paginator("list_objects_v2")
    
    for page in paginator.paginate(Bucket=MINIO_BUCKET):
        contents = page.get("Contents", [])
        if not contents:
            continue
        
        # 한번에 1000개까지 삭제 가능
        objects = [{"Key": obj["Key"]} for obj in contents]
        s3.delete_objects(
            Bucket=MINIO_BUCKET,
            Delete={"Objects": objects},
        )
        deleted_count += len(objects)
    
    return deleted_count


# ===== 오브젝트 키 생성 유틸리티 =====
@dataclass
class ObjectKeyBuilder:
    """
    MinIO 오브젝트 키(경로) 생성기
    
     team_id 유무에 따른 경로 구조:
    
    team_id 있음 (Product, Partner 등):
        {visibility}/team-{team_id}/{domain}/{object_id}/{subdir}/{filename}
        예: private/team-7/product/123/images/photo.jpg
    
    team_id=None (User):
        {visibility}/{domain}/{object_id}/{subdir}/{filename}
        예: private/user/456/profile/photo.jpg
    """
    team_id: Optional[int]  #  None 허용
    domain: FileDomain
    object_id: int
    subdir: str = ""
    is_public: bool = False

    @property
    def visibility(self) -> str:
        """public 또는 private"""
        return "public" if self.is_public else "private"

    def key_prefix(self) -> str:
        """
        디렉터리(prefix) 수준의 키 (파일명 제외)
        
        예 (team_id 있음): "private/team-7/product/123/images"
        예 (team_id=None): "private/user/456/profile"
        """
        #  team_id 유무에 따라 경로 분기
        if self.team_id is not None:
            # Product, Partner 등 (팀 소속)
            base = f"{self.visibility}/team-{self.team_id}/{self.domain.value}/{self.object_id}"
        else:
            # User (플랫폼 전역) - team- prefix 없음
            base = f"{self.visibility}/{self.domain.value}/{self.object_id}"
        
        if self.subdir:
            return f"{base}/{self.subdir}"
        return base

    def key(self, filename: str) -> str:
        """
        전체 오브젝트 키 (파일명 포함)
        
        예 (team_id 있음): "private/team-7/product/123/images/photo.jpg"
        예 (team_id=None): "private/user/456/profile/photo.jpg"
        """
        prefix = self.key_prefix()
        return f"{prefix}/{filename}" if filename else prefix


def temp_key(token: str, filename: str) -> str:
    """
    임시 업로드용 오브젝트 키 생성
    예: "tmp/abc123token/photo.jpg"
    """
    return f"{MINIO_TEMP_PREFIX}/{token}/{filename}"


def temp_prefix(token: str) -> str:
    """
    임시 업로드 토큰의 prefix
    예: "tmp/abc123token/"
    """
    return f"{MINIO_TEMP_PREFIX}/{token}/"