# scripts/seed_local.py
"""로컬 개발용 시드 스크립트.

생성하는 것:
  - Tenant 1개 (TMS Demo)
  - SUPER_ADMIN user 1명 (admin@tms.dev / Password!1)
  - ADMIN user 1명 + 위 tenant 멤버십 (owner@tms.dev / Password!1)
  - DISPATCHER user 1명 + 위 tenant 멤버십 (dispatch@tms.dev / Password!1)
  - DRIVER user 1명 + Driver row + 위 tenant 멤버십 (driver@tms.dev / Password!1)

사용:
  PYTHONPATH=src python scripts/seed_local.py

이미 같은 email 의 활성 사용자가 있으면 skip (idempotent — 여러 번 돌려도 안전).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# src 를 path 에 추가 (alembic env.py 와 동일 패턴)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import common.model.models_registry  # noqa: F401  (모델 metadata 등록)

from passlib.hash import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from auth.const.providers import AuthProviderEnum
from common.const.settings import settings
from database.mysql_connection import write_engine
from driver.model import DriverModel
from rbac.model import PermissionGroupModel
from tenant.model import TenantModel, UserTenantModel
from user.const.roles import RolesEnum
from user.model import UserModel


PASSWORD = "Password!1"
TENANT_NAME = "TMS Demo"
# (email, name, role, is_tenant_member, password_override)
USERS = [
    ("admin@tms.dev",   "Super Admin", RolesEnum.SUPER_ADMIN, False, None),  # tenant 멤버 X
    ("owner@tms.dev",   "Tenant Owner", RolesEnum.ADMIN,      True,  None),
    ("dispatch@tms.dev", "Dispatcher",  RolesEnum.DISPATCHER, True,  None),
    ("driver@tms.dev",  "Driver",      RolesEnum.DRIVER,      True,  None),
    ("test@test.com",   "Test Super",  RolesEnum.SUPER_ADMIN, True,  "1234"),
]


async def get_or_create_tenant(db) -> TenantModel:
    existing = (await db.execute(
        select(TenantModel).where(TenantModel.name == TENANT_NAME)
    )).scalar_one_or_none()
    if existing:
        print(f"[skip] tenant '{TENANT_NAME}' (id={existing.id})")
        return existing
    t = TenantModel(name=TENANT_NAME)
    db.add(t)
    await db.flush()
    print(f"[new]  tenant '{TENANT_NAME}' (id={t.id})")
    return t


async def get_or_create_user(
    db, email: str, name: str, role: RolesEnum, password: str | None = None,
) -> UserModel:
    existing = (await db.execute(
        select(UserModel).where(UserModel.email == email)
    )).scalar_one_or_none()
    if existing:
        print(f"[skip] user {email} (id={existing.id}, role={existing.role})")
        return existing
    pw_hash = bcrypt.using(rounds=settings.BCRYPT_ROUNDS).hash(password or PASSWORD)
    u = UserModel(
        email=email,
        password=pw_hash,
        auth_provider=AuthProviderEnum.EMAIL.value,
        role=role,
        name=name,
    )
    db.add(u)
    await db.flush()
    print(f"[new]  user {email} (id={u.id}, role={role})")
    return u


async def get_or_create_admin_group(db, tenant: TenantModel) -> PermissionGroupModel:
    existing = (await db.execute(
        select(PermissionGroupModel).where(
            PermissionGroupModel.tenant_id == tenant.id,
            PermissionGroupModel.system_key == "ADMIN",
        )
    )).scalar_one_or_none()
    if existing:
        print(f"[skip] admin perm group (gid={existing.id})")
        return existing
    g = PermissionGroupModel(
        tenant_id=tenant.id,
        name="Admin",
        is_admin=True,
        is_system=True,
        system_key="ADMIN",
    )
    db.add(g)
    await db.flush()
    print(f"[new]  admin perm group (gid={g.id})")
    return g


async def get_or_create_membership(
    db, user: UserModel, tenant: TenantModel,
    permission_group_id: int | None = None,
) -> None:
    existing = (await db.execute(
        select(UserTenantModel).where(
            UserTenantModel.user_id == user.id,
            UserTenantModel.tenant_id == tenant.id,
        )
    )).scalar_one_or_none()
    if existing:
        # permission_group 없는 기존 row 면 채워줌 (idempotent 보강)
        if permission_group_id and not existing.permission_group_id:
            existing.permission_group_id = permission_group_id
            await db.flush()
            print(f"[upd]  membership {user.email} -> {tenant.name} (gid={permission_group_id})")
        else:
            print(f"[skip] membership {user.email} -> {tenant.name}")
        return
    db.add(UserTenantModel(
        user_id=user.id, tenant_id=tenant.id,
        permission_group_id=permission_group_id,
    ))
    await db.flush()
    print(f"[new]  membership {user.email} -> {tenant.name} (gid={permission_group_id})")


async def get_or_create_driver(db, user: UserModel, tenant: TenantModel) -> None:
    existing = (await db.execute(
        select(DriverModel).where(
            DriverModel.tenant_id == tenant.id,
            DriverModel.user_id == user.id,
        )
    )).scalar_one_or_none()
    if existing:
        print(f"[skip] driver row for {user.email}")
        return
    db.add(DriverModel(tenant_id=tenant.id, user_id=user.id))
    await db.flush()
    print(f"[new]  driver row for {user.email}")


async def main() -> None:
    Session = async_sessionmaker(write_engine, expire_on_commit=False)
    async with Session() as db:
        tenant = await get_or_create_tenant(db)
        admin_group = await get_or_create_admin_group(db, tenant)

        for email, name, role, is_member, pw in USERS:
            user = await get_or_create_user(db, email, name, role, password=pw)
            if is_member:
                # ADMIN/DISPATCHER → admin perm group, DRIVER → null (모바일 라우트는 role 가드)
                pg = admin_group.id if role != RolesEnum.DRIVER else None
                await get_or_create_membership(db, user, tenant, permission_group_id=pg)
                if role == RolesEnum.DRIVER:
                    await get_or_create_driver(db, user, tenant)

        await db.commit()

    print("\n=== Seed 완료 ===")
    print(f"공통 비밀번호: {PASSWORD} (override 없는 경우)")
    for email, _, role, _, pw in USERS:
        suffix = f"  pw={pw}" if pw else ""
        print(f"  - {email:25} ({role.value}){suffix}")


if __name__ == "__main__":
    asyncio.run(main())
