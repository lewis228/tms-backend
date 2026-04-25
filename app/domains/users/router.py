"""Users 라우터 — ADMIN+ CRUD, 본인 GET /me, 비밀번호 변경."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import CurrentUser, DB, DBReadOnly, TenantID, require_min_role
from app.core.pagination import PageParams, PagedResponse, page_params
from app.domains.users.repository import UserRepository
from app.domains.users.schema import (
    PasswordChangeRequest,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.domains.users.service import UserService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _svc(db, *, tenant_id: str | None, actor: CurrentUser | None = None) -> UserService:
    role = actor.role if actor else None
    return UserService(
        UserRepository(db, tenant_id=tenant_id),
        actor_role=role,
        actor_tenant_id=actor.tenant_id if actor else None,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: CurrentUser, db: DBReadOnly):
    svc = _svc(db, tenant_id=None)
    me = await svc.get(user.user_id)
    return UserResponse.model_validate(me)


@router.patch("/me/password", response_model=UserResponse)
async def change_my_password(
    payload: PasswordChangeRequest, user: CurrentUser, db: DB
):
    svc = _svc(db, tenant_id=None)
    me = await svc.get(user.user_id)
    updated = await svc.change_password(me, payload)
    return UserResponse.model_validate(updated)


@router.get(
    "",
    response_model=PagedResponse[UserResponse],
    dependencies=[require_min_role("ADMIN")],
)
async def list_users(
    db: DBReadOnly,
    tenant_id: TenantID,
    params: Annotated[PageParams, Depends(page_params)],
):
    svc = _svc(db, tenant_id=tenant_id)
    items, total = await svc.list_paged(params)
    return PagedResponse.of(
        [UserResponse.model_validate(u) for u in items], total, params
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=201,
    dependencies=[require_min_role("ADMIN")],
)
async def create_user(
    payload: UserCreateRequest, user: CurrentUser, tenant_id: TenantID, db: DB
):
    svc = _svc(db, tenant_id=tenant_id, actor=user)
    created = await svc.create(payload, tenant_id=tenant_id)
    return UserResponse.model_validate(created)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[require_min_role("ADMIN")],
)
async def get_user(user_id: str, tenant_id: TenantID, db: DBReadOnly):
    svc = _svc(db, tenant_id=tenant_id)
    return UserResponse.model_validate(await svc.get(user_id))


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[require_min_role("ADMIN")],
)
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    user: CurrentUser,
    tenant_id: TenantID,
    db: DB,
):
    svc = _svc(db, tenant_id=tenant_id, actor=user)
    return UserResponse.model_validate(await svc.update(user_id, payload))


@router.delete(
    "/{user_id}",
    status_code=204,
    dependencies=[require_min_role("ADMIN")],
)
async def delete_user(user_id: str, tenant_id: TenantID, db: DB):
    svc = _svc(db, tenant_id=tenant_id)
    await svc.delete(user_id)
