# src/common/logging/config.py
"""
구조적 로깅 초기화 (structlog + 표준 logging)
- ENV=development → 콘솔(컬러, 사람이 읽기 쉽게), 파일 로그 없음
- ENV=prod        → JSON stdout, 기본 레벨 WARNING
- LOG_LEVEL이 있으면 두 환경 모두에서 그 레벨로 override
"""

from __future__ import annotations
import logging
from logging.config import dictConfig
import structlog

from common.logging.processors import base_processors, console_processors, json_processors
from common.logging.filters import HealthCheckFilter
from common.const.settings import settings

# pydantic Enum(LogLevelEnum) → logging 레벨 숫자로 변환
# settings.LOG_LEVEL.value 가 "DEBUG" | "INFO" ... 라고 가정
_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}

def _resolve_level() -> int:
    """LOG_LEVEL이 있으면 우선, 없으면 ENV별 기본값."""
    if settings.LOG_LEVEL:
        # 예: LogLevelEnum.DEBUG.value == "DEBUG"
        name = getattr(settings.LOG_LEVEL, "value", str(settings.LOG_LEVEL)).upper()
        return _LEVELS.get(name, logging.INFO)

    # LOG_LEVEL 미지정 시 환경 기본
    if settings.ENV.lower() in ("dev", "development", "local"):
        return logging.DEBUG
    # 운영 기본은 WARNING
    return logging.WARNING

def _is_dev() -> bool:
    return settings.ENV.lower() in ("dev", "development", "local")

def setup_logging() -> None:
    level = _resolve_level()
    is_dev = _is_dev()

    # 표준 logging 설정
    # - 개발: 콘솔만(사람이 읽기 좋은 rich formatter)
    # - 운영: 콘솔만(plain; structlog가 JSON으로 렌더링)
    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "health_filter": {"()": HealthCheckFilter}
        },
        "formatters": {
            # structlog가 최종 렌더링을 할 거라, 여기서는 심플 포맷 사용
            "plain": {"format": "%(message)s"},
            "rich": {
                "format": "%(asctime)s [%(levelname)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": "rich" if is_dev else "plain",
                "filters": ["health_filter"],
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": level,
            "handlers": ["console"],  # ★ 개발/운영 공통: 콘솔만
        },
        "loggers": {
            # uvicorn 로그도 root로 전파(동일 포맷)
            "uvicorn": {"level": level, "handlers": ["console"], "propagate": True},
            "uvicorn.error": {"level": level, "handlers": ["console"], "propagate": True},
            "uvicorn.access": {"level": level, "handlers": ["console"], "propagate": True},
        },
    })

    # structlog processors: 개발(컬러 콘솔) vs 운영(JSON)
    processors = base_processors + (console_processors if is_dev else json_processors)

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,  # stdlib 레벨/필터 연동
        cache_logger_on_first_use=True,
    )

    structlog.get_logger("bootstrap").info(
        "logging_initialized",
        env=settings.ENV,
        level=logging.getLevelName(level),
        mode="console" if is_dev else "json_stdout",
    )
