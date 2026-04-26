# auth/utils/cookies.py
from fastapi import Request, Response
from common.const.settings import settings
import uuid

def ensure_browser_id_cookie(request: Request, response: Response) -> str:
    name = settings.BROWSER_ID_COOKIE_NAME
    bid = request.cookies.get(name)
    if not bid:
        bid = uuid.uuid4().hex
        response.set_cookie(
            key=name,
            value=bid,
            httponly=settings.BROWSER_COOKIE_HTTPONLY,
            secure=settings.BROWSER_COOKIE_SECURE,
            samesite=settings.BROWSER_COOKIE_SAMESITE,
            max_age=60 * 60 * 24 * 365,
            path="/",
        )
    return bid

def set_refresh_token_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=settings.REFRESH_COOKIE_HTTPONLY,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        max_age=settings.REFRESH_TTL,
        path="/",
    )

def clear_refresh_token_cookie(response: Response) -> None:
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=settings.REFRESH_COOKIE_HTTPONLY,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path="/",
    )
