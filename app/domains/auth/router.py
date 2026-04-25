"""Auth 라우터 — /login, /refresh. 공개."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.dependencies import DB
from app.domains.auth.schema import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenPair,
)
from app.domains.auth.service import AuthService
from app.domains.users.repository import UserRepository

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: DB):
    svc = AuthService(UserRepository(db))
    user = await svc.authenticate(payload.email, payload.password)
    access, refresh = svc.issue_tokens(user)
    return LoginResponse(
        access_token=access,
        refresh_token=refresh,
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        must_change_password=user.must_change_password,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DB):
    svc = AuthService(UserRepository(db))
    _user, access, new_refresh = await svc.refresh(payload.refresh_token)
    return TokenPair(access_token=access, refresh_token=new_refresh)
