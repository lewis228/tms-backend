# src/leg_rate/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import DO_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from leg_rate.service import LegRateService
from leg_rate.schemas.request import LegRateUpdateRequest, RateCalculateRequest
from container.schemas.response import LegRateResponseSchema


router = APIRouter(prefix="/api/v1", tags=["leg-rate"])


@router.get("/legs/{leg_id}/rate", response_model=LegRateResponseSchema)
async def get_leg_rate(
    leg_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """leg_rate 조회 — 없으면 lookup 후 snapshot 박아 INSERT."""
    return await LegRateService(db, team_id).get_or_calc(leg_id, actor_user_id=int(me.id))


@router.patch("/legs/{leg_id}/rate", response_model=LegRateResponseSchema)
async def update_leg_rate(
    leg_id: int,
    body: LegRateUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """leg_rate 수동 override (base_amount / payee 입력)."""
    return await LegRateService(db, team_id).update(leg_id, body, actor_user_id=int(me.id))


@router.post("/legs/{leg_id}/rate/recalculate", response_model=LegRateResponseSchema)
async def recalculate_leg_rate(
    leg_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """⚠️ 명시적 재계산 — 마스터의 현재 값으로 snapshot 새로 박음. 정산 안전성을 위해 자동 호출 X."""
    return await LegRateService(db, team_id).recalculate(leg_id, actor_user_id=int(me.id))


@router.post("/rate/calculate")
async def calculate_rate(
    body: RateCalculateRequest,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """leg 미저장 견적 — Quote / Tariff lookup 결과만 리턴 (snapshot 박지 않음)."""
    result = await LegRateService(db, team_id).compute(body)
    # source enum 직렬화
    if hasattr(result.get("source"), "value"):
        result["source"] = result["source"].value
    return result
