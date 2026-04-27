# src/ai_intake/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401

from auth.tokens.access_token import access_token
from rbac.const.const import DO_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from ai_intake.service import AIIntakeService
from ai_intake.schemas.response import AIIntakeExtractResponse

router = APIRouter(prefix="/api/v1/ai-intake", tags=["ai_intake"])


@router.post("/extract", response_model=AIIntakeExtractResponse)
async def extract_do(
    file: UploadFile = File(...),
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    me: UserResponseSchema = Depends(get_current_user),
):
    """PDF / 이미지 → D/O 필드 추출 (Claude API)."""
    svc = AIIntakeService()
    if not svc.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AI_INTAKE_DISABLED",
                    "message": "AI_INTAKE_PROVIDER 미설정 또는 해당 API key 가 비어있다."},
        )
    body = await file.read()
    result = await svc.extract_delivery_order(
        file_bytes=body, filename=file.filename or "document", content_type=file.content_type or "application/octet-stream",
    )
    return AIIntakeExtractResponse(
        **{k: v for k, v in result.items() if k in {"filename", "size_bytes", "fields", "confidence", "provider"}}
    )
