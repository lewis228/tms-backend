"""AI Intake 라우터 — DISPATCHER+. PDF/이미지 → 필드 추출."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.dependencies import DB, TenantID, require_min_role
from app.domains.ai_intake.schema import IntakeExtractRequest, IntakeExtractResponse
from app.domains.ai_intake.service import DEFAULT_MODEL, AIIntakeService
from app.domains.files.repository import FileRepository

router = APIRouter(
    prefix="/api/v1/ai-intake",
    tags=["ai-intake"],
    dependencies=[require_min_role("DISPATCHER")],
)


@router.post("/extract", response_model=IntakeExtractResponse)
async def extract(
    payload: IntakeExtractRequest,
    tenant_id: TenantID,
    db: DB,
    model: str = Query(default=DEFAULT_MODEL),
):
    svc = AIIntakeService(FileRepository(db, tenant_id=tenant_id))
    return await svc.extract(payload, model=model)
