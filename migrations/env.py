# migrations/env.py
from logging.config import fileConfig
import os
import sys
import asyncio
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# 이제 프로젝트 모듈 임포트 (settings, models 등)
from common.const.settings import settings
# 모든 모델이 metadata에 등록되도록 임포트 (한군데서만 몰아 임포트해도 좋음)
from common.model.models_registry import Base

config = context.config

# .ini를 덮어쓸 최종 DB URL (비동기 선호)
async_url = os.getenv("DATABASE_URL") or (
    f"mysql+aiomysql://{settings.DB_USERNAME}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_DATABASE}?charset=utf8mb4"
)

# 오프라인 모드에서 쓸 동기 URL로 변환하는 헬퍼
def to_sync_url(url: str) -> str:
    return (
        url.replace("+aiomysql", "+pymysql")
           .replace("+asyncmy", "+pymysql")
    )

# Alembic이 참조하는 sqlalchemy.url 갱신 (온라인 기준)
config.set_main_option("sqlalchemy.url", async_url)

# 로깅
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """오프라인 모드: 엔진 없이 URL만으로 스크립트 생성/적용"""
    url = to_sync_url(async_url)  # 오프라인은 동기 드라이버 사용
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=False,
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection, 
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=False,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """온라인 모드: async 엔진"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
