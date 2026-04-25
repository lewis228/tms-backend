from __future__ import annotations
import asyncio
import uuid
import structlog
from fastapi import FastAPI
from contextlib import asynccontextmanager

from database.mysql_connection import async_engine
from cache.redis_connection import redis, read_redis
from common.events.connection_manager import connection_manager
from common.events.listener import TeamEventsListener
from common.lifecycle.startup import test_db_connection, test_redis_connection
from common.lifecycle.shutdown import graceful_shutdown_tasks
from common.const.settings import settings
from file.const.consts import ensure_bucket_exists

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    structlog.contextvars.bind_contextvars(
        request_id=f"lifespan-{uuid.uuid4().hex[:8]}",
        user_id=None,
    )
    logger.info("starting_up")

    listener_task: asyncio.Task[None] | None = None

    try:
        await test_db_connection()
        await test_redis_connection()

        try:
            ensure_bucket_exists()
            logger.info("minio_bucket_ready", bucket=settings.MINIO_BUCKET)
        except Exception as e:
            logger.error("minio_init_failed", error=str(e))

        # 팀 이벤트 리스너 기동 — 이 프로세스(파드) 수명 동안 유일한 Redis
        # pub/sub 구독자. 접속 WS 수와 무관하게 파드당 subscribe 1개로 고정.
        listener = TeamEventsListener(read_redis, connection_manager)
        listener_task = asyncio.create_task(
            listener.run(), name="team_events_listener"
        )
        logger.info("team_events_listener_started")

        logger.info("all_services_connected")
    except Exception:
        logger.critical("startup_failed_service_connection_error")
        if listener_task is not None:
            listener_task.cancel()
        raise

    try:
        yield
    finally:
        logger.info("shutting_down")

        # 리스너 먼저 정리 — 이후 broadcast 호출이 들어오지 않도록.
        if listener_task is not None:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                logger.warning("team_events_listener_shutdown_error")

        await async_engine.dispose()
        try:
            await redis.close()
        except Exception:
            logger.warning("redis_close_failed")
        await graceful_shutdown_tasks()
        logger.info("cleanup_done")
