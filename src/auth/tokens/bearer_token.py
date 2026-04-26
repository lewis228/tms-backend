# auth/tokens/bearer_token.py
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from common.const.settings import settings
from common.exceptions.base import AppException
from database.dependencies import get_db
from cache.dependencies import get_redis
from auth.service import AuthService
from user.repository import UserRepository
from user.schemas.response import UserResponseSchema
import json
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()

def _b2s(v):
    return v.decode() if isinstance(v, (bytes, bytearray)) else v

def _auth_fail(code: str, detail: str, status: int = 401):
    """
    클라이언트가 케이스별로 구분 처리할 수 있도록 항상 code를 내려줍니다.
    예: {"code":"BROWSER_ID_MISMATCH","message":"브라우저 식별이 일치하지 않습니다."}
    """
    raise AppException(status_code=status, code=code, message=detail)

async def bearer_token(
    request: Request,
    auth_header: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    # ─────────────────────────────────────────────────────────────────────────────
    # 0) Authorization 헤더 존재 확인
    # ─────────────────────────────────────────────────────────────────────────────
    if not auth_header:
        _auth_fail("NO_TOKEN", "토큰이 없습니다.")

    raw_token = auth_header.credentials
    svc = AuthService(db, redis)

    # ─────────────────────────────────────────────────────────────────────────────
    # 1) JWT 디코드 & 필수 클레임 추출
    # ─────────────────────────────────────────────────────────────────────────────
    payload = svc.verify_token(raw_token)  # 실패 시 UnauthorizedException → FastAPI가 401 처리
    token_type = payload.get("type", "unknown")
    sid = payload.get("sid")
    jti = payload.get("jti")
    sub = payload.get("sub")
    did = payload.get("did")

    if not sub:
        _auth_fail("NO_USER_IN_TOKEN", "토큰에 사용자 ID가 없습니다.")
    if not sid:
        _auth_fail("NO_SESSION_IN_TOKEN", "세션 정보가 유효하지 않습니다.")
    if not did:
        _auth_fail("NO_DEVICE_IN_TOKEN", "디바이스 정보가 유효하지 않습니다.")

    uid = int(sub)

    # ─────────────────────────────────────────────────────────────────────────────
    # 1-β) (웹 한정) 브라우저 ID 바인딩 검증
    #  - 토큰의 did가 'web:<browser_id>' 형태이면, 요청 쿠키의 BROWSER_ID와 일치해야 통과
    #  - 이렇게 하면 크롬에서 탈취한 토큰을 엣지에 붙여넣어도 쿠키가 없어 바로 차단
    # ─────────────────────────────────────────────────────────────────────────────
    if isinstance(did, str) and did.startswith("web:"):
        bid_in_token = did.split(":", 1)[1]  # 'web:<bid>' → <bid>
        bid_cookie = request.cookies.get(settings.BROWSER_ID_COOKIE_NAME)
        if not bid_cookie or bid_cookie != bid_in_token:
            _auth_fail("BROWSER_ID_MISMATCH", "브라우저 식별이 일치하지 않습니다.")

    # ─────────────────────────────────────────────────────────────────────────────
    # 2) 블랙리스트(로그아웃/세션교체 즉시 차단)
    # ─────────────────────────────────────────────────────────────────────────────
    if jti:
        bl = await redis.get(f"bl:a:{jti}")
        if bl:
            _auth_fail("TOKEN_BLACKLISTED", "차단된 토큰입니다.")

    # ─────────────────────────────────────────────────────────────────────────────
    # 3) 세션 존재 확인
    # ─────────────────────────────────────────────────────────────────────────────
    sess_raw = await redis.get(f"sess:{sid}")
    if not sess_raw:
        _auth_fail("SESSION_NOT_FOUND", "세션이 만료되었거나 교체되었습니다.")

    try:
        sess_obj = json.loads(_b2s(sess_raw))  # e.g. {"uid": 2, "did": "web:xxxx", "jti": "...", "exp": 123456}
    except Exception:
        _auth_fail("SESSION_CORRUPTED", "세션 데이터가 손상되었습니다.")

    # ─────────────────────────────────────────────────────────────────────────────
    # 4) uid/sid 교차 검증
    # ─────────────────────────────────────────────────────────────────────────────
    if int(sess_obj.get("uid", -1)) != uid:
        _auth_fail("UID_MISMATCH", "세션과 토큰의 사용자 정보가 일치하지 않습니다.")

    # ─────────────────────────────────────────────────────────────────────────────
    # 5) did 일치 검증 (세션에 기록된 did == 토큰의 did)
    #  - 같은 브라우저(혹은 기기)에서 계정 교체 시 여기서 막힘
    # ─────────────────────────────────────────────────────────────────────────────
    if sess_obj.get("did") != did:
        _auth_fail("ACCOUNT_SWITCHED", "동일 브라우저/디바이스에서 계정이 교체되었습니다.")

    # ─────────────────────────────────────────────────────────────────────────────
    # 6) 기기 → 세션 매핑 역검증
    # ─────────────────────────────────────────────────────────────────────────────
    map_key = f"device:{did}:sid"
    mapped_sid_raw = await redis.get(map_key)
    if not mapped_sid_raw:
        _auth_fail("DEVICE_MAPPING_MISSING", "세션 매핑이 존재하지 않습니다.")
    mapped_sid = _b2s(mapped_sid_raw)
    if mapped_sid != sid:
        _auth_fail("DEVICE_SID_MISMATCH", "세션 매핑이 일치하지 않습니다.")

    # ─────────────────────────────────────────────────────────────────────────────
    # 7) 유저 로딩 (캐시 → DB)
    # ─────────────────────────────────────────────────────────────────────────────
    user_data: UserResponseSchema | None = None
    ukey = f"user:{uid}"
    cached = await redis.get(ukey)
    if cached:
        try:
            user_data = UserResponseSchema.model_validate(json.loads(_b2s(cached)))
        except Exception:
            user_data = None  # 손상 시 무시하고 DB 폴백

    if not user_data:
        model = await UserRepository(db).get_user_by_id(uid)
        if not model:
            _auth_fail("USER_NOT_FOUND", "사용자를 찾을 수 없습니다.", status=404)
        user_data = UserResponseSchema.model_validate(model)
        await redis.set(ukey, json.dumps(user_data.model_dump()), ex=settings.USER_CACHE_TTL)

    # ─────────────────────────────────────────────────────────────────────────────
    # 8) 요청 컨텍스트 주입
    # ─────────────────────────────────────────────────────────────────────────────
    request.state.user = user_data
    request.state.token = raw_token
    request.state.token_type = token_type
    request.state.payload = payload

    # (선택) 디버깅 로그
    logger.debug("bearer_token ok", extra={"uid": uid, "sid": sid, "did": did, "type": token_type})
