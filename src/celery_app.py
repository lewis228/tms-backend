# src/celery_app.py
"""
Celery 애플리케이션 + Beat 스케줄 설정
"""
# 부트스트랩이 먼저 실행되도록 settings를 가장 먼저 import.
from common.const.settings import settings  # noqa: F401

import ssl
from urllib.parse import quote_plus

from celery import Celery

_redis_host = settings.REDIS_WRITE_HOST if settings.is_redis_read_write_split else settings.REDIS_HOST
_redis_port = settings.REDIS_PORT
_redis_db = settings.REDIS_DB
_redis_password = settings.REDIS_PASSWORD or ""
_redis_ssl = bool(settings.REDIS_SSL)
_redis_scheme = "rediss" if _redis_ssl else "redis"
# 패스워드 특수문자(@:/#?)가 URL 파싱을 깨뜨리지 않도록 quote_plus.
_redis_auth = f":{quote_plus(_redis_password)}@" if _redis_password else ""
# 전체 컴포넌트(Beat / Worker / scheduling 락)가 동일한 Redis DB를 쓰도록 settings.REDIS_DB 사용.
_broker_url = f"{_redis_scheme}://{_redis_auth}{_redis_host}:{_redis_port}/{_redis_db}"

celery = Celery(
    "tracking",
    broker=_broker_url,
    backend=_broker_url,
)

celery.conf.update(
    # 시스템 전체 UTC 원칙 — 하드코딩.
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_default_queue="celery",
    # 도메인별 tasks 모듈을 명시적으로 import (autodiscover 대신)
    imports=[
        "ocean.tasks.scheduling",
        "vessel.tasks.resolve_vessel",
        "vessel.tasks.poll_fleet_positions",
    ],
)

if _redis_ssl:
    celery.conf.broker_use_ssl = {"ssl_cert_reqs": ssl.CERT_NONE}
    celery.conf.redis_backend_use_ssl = {"ssl_cert_reqs": ssl.CERT_NONE}

# Celery Beat 스케줄
celery.conf.beat_schedule = {
    "check-and-schedule-ocean-scrapes-every-hour": {
        "task": "ocean.tasks.scheduling.check_and_schedule_scrapes",
        "schedule": 3600.0,  # 매 1시간
    },
    # AIS 최신 위치 폴링 — settings.AIS_POLL_INTERVAL_MINUTES 분마다.
    # 기본 10분. mock provider 인 동안에도 돌면서 프론트 실시간 갱신 테스트.
    "poll-fleet-positions": {
        "task": "vessel.poll_fleet_positions",
        "schedule": float(settings.AIS_POLL_INTERVAL_MINUTES * 60),
    },
}
