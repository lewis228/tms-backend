from fastapi import Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from database.dependencies import get_db
from cache.dependencies import get_redis
from auth.service import AuthService
from common.exceptions import UnauthorizedException
from user.schemas.response import UserResponseSchema

security = HTTPBasic()


async def basic_token(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> UserResponseSchema:
    if not credentials:
        raise UnauthorizedException("Basic 인증 정보가 제공되지 않았습니다.")
    email = credentials.username
    password = credentials.password
    auth_service = AuthService(db, redis)
    user = await auth_service.authenticate_with_email(email=email, password=password)
    await db.rollback()
    request.state.user = user
    return user
