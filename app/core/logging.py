"""structlog 설정 + PII 마스킹."""
from __future__ import annotations

import logging
import re
import sys

import structlog

from app.config import settings

_PII_PATTERNS = [
    (re.compile(r'("password"\s*:\s*)"[^"]*"'), r'\1"***"'),
    (re.compile(r'("token"\s*:\s*)"[^"]*"'), r'\1"***"'),
    (re.compile(r'("secret"\s*:\s*)"[^"]*"'), r'\1"***"'),
    (re.compile(r'("authorization"\s*:\s*)"[^"]*"', re.IGNORECASE), r'\1"***"'),
]


def _mask_pii(_logger, _name, event_dict):
    for k, v in list(event_dict.items()):
        if k.lower() in {"password", "token", "secret", "authorization", "jwt"}:
            event_dict[k] = "***"
        elif isinstance(v, str) and v:
            for pat, repl in _PII_PATTERNS:
                v = pat.sub(repl, v)
            event_dict[k] = v
    return event_dict


def configure_logging() -> None:
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _mask_pii,
    ]
    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
