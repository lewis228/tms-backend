# src/file/schemas/response.py
"""
파일 API 응답 스키마

MinIO 전환으로 변경된 스키마:
- UploadUrlResponseSchema: presigned upload URL 응답 (TempUploadResponseSchema 대체)
- DownloadUrlResponseSchema: presigned download URL 응답 (SignedUrlResponseSchema 대체)
"""
from __future__ import annotations
from datetime import datetime
from typing import List
from pydantic import BaseModel

from common.schemas.base import ResponseSchema
from file.const.domains import FileDomain


class FileInfoResponseSchema(ResponseSchema):
    """
    단일 파일 메타 정보 응답 DTO

    기존과 동일 - 변경 없음
    """
    id: int
    tenant_id: int
    domain: FileDomain
    object_id: int
    subdir: str
    filename: str
    size: int
    mime: str
    is_public: bool
    logical_path: str       # MinIO 오브젝트 키로 저장됨
    updated_at: datetime


class FileListResponseSchema(ResponseSchema):
    """
    파일 목록 응답 DTO

    기존과 동일 - 변경 없음
    """
    files: List[FileInfoResponseSchema]


# ===== MinIO 전환으로 새로 추가/변경된 스키마 =====

class UploadFileInfo(BaseModel):
    """
    개별 파일 업로드 정보
    """
    filename: str           # 원본 파일명
    upload_url: str         # MinIO presigned PUT URL
    key: str                # MinIO 오브젝트 키 (tmp/token/filename)
    content_type: str       # MIME 타입


class UploadUrlResponseSchema(ResponseSchema):
    """
    Presigned Upload URL 응답

    기존 TempUploadResponseSchema를 대체.
    클라이언트는 files[].upload_url로 직접 PUT 요청하면 됨.
    """
    token: str                      # commit 시 사용할 토큰
    files: List[UploadFileInfo]     # 각 파일별 업로드 정보


class DownloadUrlResponseSchema(ResponseSchema):
    """
    Presigned Download URL 응답

    기존 SignedUrlResponseSchema와 동일하지만 이름 변경.
    MinIO presigned URL이 직접 반환됨.
    """
    url: str    # MinIO presigned GET URL


# ===== 삭제된 스키마 (참고용) =====
#
# class TempUploadResponseSchema(ResponseSchema):
#     """기존: 서버 경유 업로드 후 토큰/파일명/미리보기 URL 응답"""
#     token: str
#     files: List[str]         # filenames
#     preview_urls: List[str]  # /uploads/tmp/{token}/{filename}
#
# → UploadUrlResponseSchema로 대체
#   - preview_urls 대신 클라이언트가 업로드 후 직접 presigned GET URL 요청
#
# class SignedUrlResponseSchema(ResponseSchema):
#     """기존: 서명된 프라이빗 파일 접근 URL 응답"""
#     url: str
#
# → DownloadUrlResponseSchema로 이름 변경 (내용은 동일)