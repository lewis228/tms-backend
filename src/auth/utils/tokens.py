# auth/utils/tokens.py (새 파일)
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from common.const.settings import settings
from user.schemas.response import TokenPayloadResponseSchema
from common.exceptions.base import UnauthorizedException

def decode_jwt_token(token: str) -> TokenPayloadResponseSchema:
    if not token:
        raise UnauthorizedException("토큰이 없습니다.")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
    except ExpiredSignatureError:
        raise UnauthorizedException("토큰이 만료되었습니다.")
    except InvalidTokenError:
        raise UnauthorizedException("유효하지 않은 토큰입니다.")

    return TokenPayloadResponseSchema(
        id=int(payload["sub"]),
        sid=payload.get("sid"),
        did=payload.get("did"),
        jti=payload.get("jti"),
        type=payload.get("type", "access"),
        iat=payload.get("iat"),
        exp=payload.get("exp"),
        # access_payload 에 박힌 role / team_id claim 도 노출.
        # team_id 는 DRIVER 만 박힘 → 다른 role 은 None.
        role=payload.get("role"),
        team_id=payload.get("team_id"),
    )
