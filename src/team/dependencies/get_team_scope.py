# team/dependencies/get_team_scope.py
"""
팀 스코프를 요청 경계에서 강제로 주입하는 의존성.

tracking-api 는 ``jwt_or_api_key`` 하나의 의존성으로 JWT/API Key 두 경로를
모두 인증한다. 두 경로 모두 통과 시점에는 ``AuthResult.team_id`` 가 결정되어 있다:

- **API Key 호출자** — 키 row 에 team_id 가 기록돼 있어 ``auth.team_id`` 에 채워진다.
- **JWT 호출자** — ``X-Team-Id`` 헤더를 기반으로 ``jwt_or_api_key`` 가 멤버십 검증
  후 ``auth.team_id`` 를 세팅한다 (비소속이면 거기서 403 발생).

따라서 이 dependency 는 얇은 래퍼로 충분하다. 이미 검증된 ``team_id`` 를 꺼내
``None`` 이면 400 을 던지기만 한다. 팀이 꼭 필요한 엔드포인트에 사용한다.

이 패턴 (샘플 레포의 ``get_team_scope``) 과 달리 tracking-api 는 Redis 2 차 캐시를
별도로 두지 않는다 — ``jwt_or_api_key`` 가 한 요청당 한 번만 멤버십을 확인하고
그 결과가 ``AuthResult`` 에 담기기 때문.

사용 예시::

    @router.post("/shipments", response_model=ShipmentResponseSchema)
    async def create_shipment(
        body: CreateShipmentRequestSchema,
        auth: AuthResult = Depends(jwt_or_api_key),
        _rl: None = Depends(rate_limit),
        team_id: int = Depends(get_team_scope),          # ← 반드시 함께
        db: AsyncSession = Depends(get_write_db),
    ):
        svc = ShipmentService(db, team_id)
        return await svc.create(body, ...)
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from auth.dependencies.jwt_or_api_key import AuthResult, jwt_or_api_key


async def get_team_scope(
    auth: AuthResult = Depends(jwt_or_api_key),
) -> int:
    """``AuthResult.team_id`` 를 꺼내되 없으면 400 으로 실패시킨다."""
    if auth.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "TEAM_REQUIRED",
                "message": "팀 컨텍스트가 필요합니다. JWT 호출자는 X-Team-Id 헤더를 설정하세요.",
            },
        )
    return auth.team_id


# 레거시 헬퍼 — 라우터 path param ``/team/{team_id}`` 에서 팀 ID를 꺼내고 싶을 때.
# 실제 팀 멤버십 검증 용도로는 ``get_team_scope`` 를 써라.
def extract_team_id_from_request(request: Request):
    raw = (
        request.path_params.get("team_id")
        or request.query_params.get("teamId")
        or request.headers.get("X-Team-Id")
    )
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        return None
