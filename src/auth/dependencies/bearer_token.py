from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from common.const.settings import settings, BROWSER_ID_COOKIE_NAME
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
    raise AppException(status_code=status, code=code, message=detail)

async def bearer_token(
    request: Request,
    auth_header: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    if not auth_header:
        _auth_fail("NO_TOKEN", "토큰이 없습니다.")

    raw_token = auth_header.credentials
    svc = AuthService(db, redis)

    payload = svc.verify_token(raw_token)
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

    if isinstance(did, str) and did.startswith("web:"):
        bid_in_token = did.split(":", 1)[1]
        bid_cookie = request.cookies.get(BROWSER_ID_COOKIE_NAME)
        if not bid_cookie or bid_cookie != bid_in_token:
            _auth_fail("BROWSER_ID_MISMATCH", "브라우저 식별이 일치하지 않습니다.")

    if jti:
        bl = await redis.get(f"bl:a:{jti}")
        if bl:
            _auth_fail("TOKEN_BLACKLISTED", "차단된 토큰입니다.")

    sess_raw = await redis.get(f"sess:{sid}")
    if not sess_raw:
        _auth_fail("SESSION_NOT_FOUND", "세션이 만료되었거나 교체되었습니다.")

    try:
        sess_obj = json.loads(_b2s(sess_raw))
    except Exception:
        _auth_fail("SESSION_CORRUPTED", "세션 데이터가 손상되었습니다.")

    if int(sess_obj.get("uid", -1)) != uid:
        _auth_fail("UID_MISMATCH", "세션과 토큰의 사용자 정보가 일치하지 않습니다.")

    if sess_obj.get("did") != did:
        _auth_fail("ACCOUNT_SWITCHED", "동일 브라우저/디바이스에서 계정이 교체되었습니다.")

    map_key = f"device:{did}:sid"
    mapped_sid_raw = await redis.get(map_key)
    if not mapped_sid_raw:
        _auth_fail("DEVICE_MAPPING_MISSING", "세션 매핑이 존재하지 않습니다.")
    mapped_sid = _b2s(mapped_sid_raw)
    if mapped_sid != sid:
        _auth_fail("DEVICE_SID_MISMATCH", "세션 매핑이 일치하지 않습니다.")

    user_data: UserResponseSchema | None = None
    ukey = f"user:{uid}"
    cached = await redis.get(ukey)
    if cached:
        try:
            user_data = UserResponseSchema.model_validate(json.loads(_b2s(cached)))
        except Exception:
            user_data = None

    if not user_data:
        model = await UserRepository(db).get_user_by_id(uid)
        if not model:
            _auth_fail("USER_NOT_FOUND", "사용자를 찾을 수 없습니다.", status=404)
        user_data = UserResponseSchema.model_validate(model)
        await redis.set(ukey, json.dumps(user_data.model_dump()), ex=settings.USER_CACHE_TTL)

    request.state.user = user_data
    request.state.token = raw_token
    request.state.token_type = token_type
    request.state.payload = payload
    logger.debug("bearer_token ok", extra={"uid": uid, "sid": sid, "did": did, "type": token_type})
