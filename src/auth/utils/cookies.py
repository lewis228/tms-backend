from fastapi import Request, Response
from common.const.settings import settings, BROWSER_ID_COOKIE_NAME, REFRESH_TOKEN_COOKIE_NAME
import uuid


def ensure_browser_id_cookie(request: Request, response: Response) -> str:
    bid = request.cookies.get(BROWSER_ID_COOKIE_NAME)
    if not bid:
        bid = uuid.uuid4().hex
        response.set_cookie(
            key=BROWSER_ID_COOKIE_NAME,
            value=bid,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            max_age=60 * 60 * 24 * 365,
            path="/",
        )
    return bid


def set_refresh_token_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.REFRESH_TTL,
        path="/",
    )


def clear_refresh_token_cookie(response: Response) -> None:
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
