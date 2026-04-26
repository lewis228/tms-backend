# src/common/lifecycle/lifespan.py
from __future__ import annotations
import uuid
import structlog
from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy import text

from database.mysql_connection import async_engine, async_session_maker  # noqa: F401
from cache.redis_connection import redis
from common.lifecycle.startup import test_db_connection, test_redis_connection
from common.lifecycle.shutdown import graceful_shutdown_tasks
from common.const.settings import settings

# MinIO 버킷 초기화 + 클리어
from file.const.consts import ensure_bucket_exists, clear_bucket  # noqa: F401

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    통합 Lifespan 관리자
    
    시작 시:
    1. DB 연결 테스트
    2. Redis 연결 테스트
    3. MinIO 버킷 초기화
    4. (개발환경) 시드 데이터 로딩

    종료 시:
    1. DB 커넥션 풀 정리
    2. Redis 연결 종료
    3. Graceful shutdown 태스크 실행
    """
    # lifespan 범위에서도 추적을 위해 별도 request_id 바인딩
    structlog.contextvars.bind_contextvars(
        request_id=f"lifespan-{uuid.uuid4().hex[:8]}",
        user_id=None,
    )
    logger.info("starting_up")

    try:
        # 1) 의존성 체크 (DB/Redis)
        await test_db_connection()
        await test_redis_connection()

        # 2) MinIO 버킷 초기화
        try:
            ensure_bucket_exists()
            logger.info("minio_bucket_ready", bucket=settings.MINIO_BUCKET)
        except Exception as e:
            logger.error("minio_init_failed", error=str(e))
            # 버킷 초기화 실패해도 앱은 시작 (필요시 raise로 변경)

        # await _run_dev_seed_full_reset()

        # 3) 개발 환경일 때만: 전체 DB 하드 리셋 + 통합 시드
        # if settings.ENV == "development":
        #     await _run_dev_seed_full_reset()
        # else:
        #     logger.info("seed_skipped", env=settings.ENV)

        logger.info("all_services_connected")
    except Exception:
        logger.critical("startup_failed_service_connection_error")
        raise

    # ---- 앱 동작 구간 ----
    yield

    # ---- 종료 처리 ----
    logger.info("shutting_down")
    await async_engine.dispose()
    try:
        await redis.close()
    except Exception:
        logger.warning("redis_close_failed")
    await graceful_shutdown_tasks()
    logger.info("cleanup_done")


async def _run_dev_seed_full_reset():
    """TMS 시드 — Phase B+ 에서 도입 예정. 현재는 비어있음."""
    logger.info("seed_skipped_no_seed_defined")


async def _hard_reset_mysql_schema(db):
    """
    MySQL 전용: 현재 DB 스키마의 모든 BASE TABLE을 TRUNCATE.
    - 외래키 제약을 일시적으로 비활성화 후 순서 무시 TRUNCATE
    - 제외 목록은 필요 시 추가
    """
    schema = settings.DB_DATABASE
    exclude_tables = {
        # Alembic 버전 테이블은 유지 권장 (원하면 주석 처리하고 같이 날려도 됨)
        "alembic_version",
    }

    # 테이블 목록 조회
    result = await db.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_type = 'BASE TABLE'
            """
        ),
        {"schema": schema},
    )
    tables: list[str] = [row[0] for row in result.fetchall() if row[0] not in exclude_tables]

    # 외래키 비활성화 → TRUNCATE → 외래키 재활성화
    try:
        await db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for t in tables:
            # 백틱으로 감싸 안전하게 TRUNCATE
            await db.execute(text(f"TRUNCATE TABLE `{t}`"))
        await db.commit()
    finally:
        # 혹시라도 중간 실패 시에도 FK 복구 시도
        try:
            await db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            await db.commit()
        except Exception:
            # 로깅만 남기고 통과
            logger.warning("fk_reenable_failed")