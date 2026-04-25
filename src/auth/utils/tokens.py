import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from common.const.settings import settings, JWT_ALGORITHM
from user.schemas.response import TokenPayloadResponseSchema
from common.exceptions.base import UnauthorizedException


def decode_jwt_token(token: str) -> TokenPayloadResponseSchema:
    if not token:
        raise UnauthorizedException("토큰이 없습니다.")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
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
    )
