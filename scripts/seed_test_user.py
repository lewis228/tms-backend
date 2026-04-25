"""테스트 계정 시드 스크립트 — 로컬 초기 셋업용.

사용:
  cd backend_tracking-api
  PYTHONPATH=src .venv/bin/python scripts/seed_test_user.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import bcrypt

from common.const.config_bootstrap import load_env  # noqa: F401
load_env()

from sqlalchemy import select

from common.const.settings import BCRYPT_ROUNDS
from database.mysql_connection import write_session_maker
from user.model import UserModel
from team.model import TeamModel, UserTeamModel

TEST_PASSWORD = "123456789"

TEST_ACCOUNTS = [
    {"email": "test@test.com",  "name": "Test User",  "team": "Test Team"},
    {"email": "test2@test.com", "name": "Test User2", "team": "Test Team2"},
]


async def seed_account(db, email: str, name: str, team_name: str):
    existing = await db.execute(select(UserModel).where(UserModel.email == email))
    if existing.scalar_one_or_none():
        print(f"[skip] user already exists: {email}")
        return

    pw_hash = bcrypt.hashpw(
        TEST_PASSWORD.encode("utf-8"),
        bcrypt.gensalt(BCRYPT_ROUNDS),
    ).decode("utf-8")

    user = UserModel.create_email_user(
        email=email,
        password_hash=pw_hash,
        name=name,
    )
    db.add(user)
    await db.flush()

    team = TeamModel(
        name=team_name,
        plan="free",
        created_by_user_id=user.id,
    )
    db.add(team)
    await db.flush()

    membership = UserTeamModel(
        user_id=user.id,
        team_id=team.id,
        permission_group_id=None,
    )
    db.add(membership)
    await db.commit()

    print(f"[ok] user_id={user.id}  team_id={team.id}")
    print(f"     email={email}  password={TEST_PASSWORD}")


async def seed():
    async with write_session_maker() as db:
        for account in TEST_ACCOUNTS:
            await seed_account(db, account["email"], account["name"], account["team"])


if __name__ == "__main__":
    asyncio.run(seed())
