# src/file/schemas/request.py
"""
파일 API 요청 스키마

MinIO 전환으로 추가된 스키마:
- UploadUrlRequestSchema: presigned upload URL 발급 요청
"""
from __future__ import annotations
from typing import Literal, Optional, List
from common.pagination.schemas.pagination_request import BasePaginationSchema
from common.schemas.base import RequestSchema
from file.const.domains import FileDomain


class UploadUrlRequestSchema(RequestSchema):
    """
    Presigned Upload URL 발급 요청

    클라이언트가 업로드할 파일명 목록을 보내면,
    각 파일에 대한 presigned PUT URL을 발급받음.
    """
    filenames: List[str]  # 업로드할 파일명 목록 (예: ["image1.jpg", "image2.png"])


class FileCommitRequestSchema(RequestSchema):
    """
    TEMP 업로드 파일을 영구 저장소로 커밋/기존 메타 제거 요청 바디

    기존과 동일 - 변경 없음
    """
    tenant_id: int
    domain: FileDomain
    object_id: int
    subdir: Optional[str] = ""
    add_temp_tokens: List[str] = []    # 업로드 후 받은 token 목록
    remove_file_ids: List[int] = []    # 기존 파일 중 제거할 ID들


class PaginateFileListRequestSchema(BasePaginationSchema):
    """
    파일 목록 커서 페이지네이션 요청

    기존과 동일 - 변경 없음
    """
    domain: FileDomain
    object_id: int
    subdir: Optional[str] = None

    # 검색/정렬 옵션
    where__filename__i_like: Optional[str] = None
    order__updated_at: Optional[Literal["ASC", "DESC"]] = None