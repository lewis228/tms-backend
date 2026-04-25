"""Fleet (vessel) 조회 API.

================================================================================
엔드포인트
================================================================================
GET /api/v1/fleet/vessels
    현재 팀이 추적 중인 선박 리스트 + 각 선박의 최신 위치 (있으면).
    Live Map 첫 로드 시 호출. 이후 업데이트는 WebSocket 이벤트로 받음.

⚠️ 권한: 기본 팀 scoped. `Depends(get_team_scope)` 로 team_id 주입.
⚠️ 정합성: vessel 자체는 전역이지만 이 리스트는 repository.list_vessels_for_team
   을 거쳐 ocean_shipments 와 join 된 결과만 반환하도록 해야 한다
   (지금은 placeholder 로 전체 반환 — vessel_id FK 추가 후 수정).
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies.jwt_or_api_key import AuthResult, jwt_or_api_key
from auth.dependencies.rate_limit import rate_limit
from database.dependencies import get_read_db
from team.dependencies.get_team_scope import get_team_scope
from vessel.repository import VesselRepository
from vessel.schemas.response import VesselResponseSchema

router = APIRouter(prefix="/api/v1/fleet", tags=["fleet"])


@router.get("/vessels", response_model=List[VesselResponseSchema])
async def list_fleet_vessels(
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """팀 scoped 선박 리스트 + 각 선박 최신 위치."""
    repo = VesselRepository(db)
    vessels = await repo.list_vessels_for_team(team_id)
    return [VesselResponseSchema.model_validate(v) for v in vessels]
