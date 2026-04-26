# src/common/lifecycle/shutdown.py
"""앱 종료 시 정리 작업 — engine pool / redis pool / WS 매니저 dispose."""
import structlog

logger = structlog.get_logger(__name__)


async def graceful_shutdown_tasks():
    logger.info("graceful_shutdown_start")

    # WebSocket: 활성 연결 모두 종료 + manager 큐 정리
    try:
        from realtime.service import manager
        await manager.shutdown()
        logger.info("graceful_shutdown.ws_manager_closed")
    except Exception as e:
        logger.warning("graceful_shutdown.ws_manager_failed", error=str(e))

    # Redis pool dispose
    try:
        from cache.redis_connection import write_redis, read_redis
        try: await write_redis.aclose()
        except Exception: pass
        if read_redis is not write_redis:
            try: await read_redis.aclose()
            except Exception: pass
        logger.info("graceful_shutdown.redis_closed")
    except Exception as e:
        logger.warning("graceful_shutdown.redis_failed", error=str(e))

    # SQLAlchemy engine pool dispose
    try:
        from database.mysql_connection import write_engine, read_engine
        try: await write_engine.dispose()
        except Exception: pass
        if read_engine is not write_engine:
            try: await read_engine.dispose()
            except Exception: pass
        logger.info("graceful_shutdown.db_engine_disposed")
    except Exception as e:
        logger.warning("graceful_shutdown.db_engine_failed", error=str(e))

    logger.info("graceful_shutdown_completed")
