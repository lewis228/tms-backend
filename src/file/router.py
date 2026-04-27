# src/file/route.py
"""
MinIO 기반 파일 API 라우터

주요 변경점:
- /_guard 엔드포인트 삭제 (MinIO가 직접 서명 검증)
- /temp 엔드포인트 변경: 서버 경유 업로드 → presigned URL 발급
- /signed-url 엔드포인트 단순화: MinIO presigned URL 반환

클라이언트 워크플로우:
1. POST /files/upload-urls   → presigned PUT URL 목록 받음
2. PUT {presigned_url}       → MinIO에 직접 업로드 (FastAPI 안 거침!)
3. POST /files/commit        → temp → 영구 경로 이동 + DB 저장
4. GET /files/download-url   → presigned GET URL 받음
5. GET {presigned_url}       → MinIO에서 직접 다운로드

권한 정책:
- 파일 자체에 대한 별도 권한 코드(FILE_READ/FILE_WRITE) 없음
- 파일은 항상 부모 엔티티(제품, 발주서 등)의 맥락에서 사용되므로
  부모 엔티티의 권한(PRODUCT_WRITE, PURCHASE_MANAGE 등)이 접근을 제어함
- 파일 엔드포인트는 access_token + team_scope만 확인
"""
from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from common.pagination.schemas.pagination_response import CursorPaginationResult
from team.dependencies.get_team_scope import get_team_scope
from database.dependencies import get_read_db, get_write_db
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from file.schemas.request import (
    FileCommitRequestSchema,
    PaginateFileListRequestSchema,
    UploadUrlRequestSchema,
)
from file.schemas.response import (
    UploadUrlResponseSchema,
    DownloadUrlResponseSchema,
    FileInfoResponseSchema,
    FileListResponseSchema,
)
from file.service import FileService

router = APIRouter(prefix="/api/v1/files", tags=["files"])


# ─────────────────────────────────────────────────────────
# 0) 리스트 (커서 페이지네이션) - 기존과 동일
# ─────────────────────────────────────────────────────────
@router.get("/list", response_model=CursorPaginationResult[FileInfoResponseSchema])
async def list_files(
    request: PaginateFileListRequestSchema = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    파일 목록 조회 (커서 페이지네이션)
    """
    svc = FileService(db)
    return await svc.list_paginated(team_id=team_id, request=request)


# ─────────────────────────────────────────────────────────
# 1) Presigned Upload URL 발급 (새로 추가)
# ─────────────────────────────────────────────────────────
@router.post("/upload-urls", response_model=UploadUrlResponseSchema)
async def get_upload_urls(
    body: UploadUrlRequestSchema,
    _1: None = Depends(access_token),
    _team_id: int = Depends(get_team_scope),  # team 멤버십 검증 (cross-team 차단)
    db: AsyncSession = Depends(get_read_db),
):
    """
    임시 업로드용 Presigned PUT URL 발급

    클라이언트는 반환된 upload_url로 직접 MinIO에 PUT 요청하면 됨.
    업로드 완료 후 token을 사용해 /commit 호출.

    Request Body:
        filenames: 업로드할 파일명 목록

    Response:
        token: 나중에 commit 시 사용
        files: [{filename, upload_url, key, content_type}, ...]
    """
    svc = FileService(db)

    try:
        token, files = svc.generate_upload_urls(body.filenames)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return UploadUrlResponseSchema(token=token, files=files)


# ─────────────────────────────────────────────────────────
# 2) 커밋 - 기존과 거의 동일
# ─────────────────────────────────────────────────────────
@router.post("/commit", response_model=FileListResponseSchema)
async def commit_files(
    body: FileCommitRequestSchema,
    _1: None = Depends(access_token),
    team_id_ctx: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    임시 업로드 파일을 영구 저장소로 커밋

    - add_temp_tokens: 업로드 후 받은 token 목록
    - remove_file_ids: 기존 파일 중 제거할 ID들
    """
    if body.team_id != team_id_ctx:
        raise HTTPException(status_code=403, detail="team scope mismatch")

    svc = FileService(db)
    saved = await svc.commit(
        team_id=body.team_id,
        domain=body.domain,
        object_id=body.object_id,
        subdir=body.subdir or "",
        add_temp_tokens=body.add_temp_tokens,
        remove_file_ids=body.remove_file_ids,
        actor_user_id=int(me.id),
        is_public=False,
    )

    return FileListResponseSchema(
        files=[FileInfoResponseSchema.model_validate(x) for x in saved]
    )


# ─────────────────────────────────────────────────────────
# 3) Presigned Download URL 발급 (단순화됨)
# ─────────────────────────────────────────────────────────
@router.get("/download-url", response_model=DownloadUrlResponseSchema)
async def get_download_url(
    _1: None = Depends(access_token),
    team_id_ctx: int = Depends(get_team_scope),
    path: str = Query(..., description="논리경로 e.g. private/team-123/product/45/images/a.jpg"),
    db: AsyncSession = Depends(get_read_db),
):
    """
    다운로드용 Presigned GET URL 발급

    클라이언트는 반환된 url로 직접 MinIO에서 다운로드하면 됨.
    서명 검증은 MinIO가 자동으로 처리.
    """
    # path의 team-<id>와 컨텍스트 일치 검증
    try:
        # path: "private/team-123/..." 또는 "public/team-123/..."
        seg = path.split("/", 3)
        if len(seg) < 2 or not seg[1].startswith("team-"):
            raise ValueError
        team_id_in_path = int(seg[1].split("-", 1)[1])
    except Exception:
        raise HTTPException(status_code=400, detail="bad logical path")

    if team_id_in_path != team_id_ctx:
        raise HTTPException(status_code=403, detail="team scope mismatch")

    svc = FileService(db)
    url = svc.generate_download_url(path)

    return DownloadUrlResponseSchema(url=url)


# ─────────────────────────────────────────────────────────
# 4) 파일 삭제 (선택적 - 필요 시 추가)
# ─────────────────────────────────────────────────────────
@router.delete("", response_model=dict)
async def delete_files(
    file_ids: List[int] = Query(..., description="삭제할 파일 ID 목록"),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """
    파일 삭제 (DB 메타 + MinIO 오브젝트)
    """
    svc = FileService(db)
    await svc._remove_files(team_id=team_id, file_ids=file_ids)
    return {"deleted": file_ids}
