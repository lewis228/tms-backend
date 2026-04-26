"""
structlog용 공통 Processor 모듈
- 모든 로그에 request_id/user_id/time/level 자동 포함
- 개발: 콘솔 컬러 포맷, 운영: JSON 포맷
- None 필드 제거(drop_none), 민감정보 마스킹(redact) 포함
"""

from __future__ import annotations
import re
import structlog
from datetime import datetime
from typing import Mapping, Any


# ─────────────────────────────────────────────────────────────
# 민감정보 마스킹 (기본 패턴 예시)
# ─────────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_RE = re.compile(r"\b(01[016789]-?\d{3,4}-?\d{4})\b", re.UNICODE)
TOKEN_KEYS = {"authorization", "access_token", "refresh_token", "password", "secret", "token"}

def redact_value(val: Any) -> Any:
    if not isinstance(val, str):
        return val
    s = EMAIL_RE.sub("***@***", val)
    s = PHONE_RE.sub("***-****-****", s)
    return s

def redact_sensitive(logger, method_name, event_dict: Mapping[str, Any]) -> Mapping[str, Any]:
    # 키 이름으로 토큰/패스워드류 마스킹
    for k in list(event_dict.keys()):
        if k.lower() in TOKEN_KEYS and isinstance(event_dict[k], str):
            event_dict[k] = "***"
    # 메시지에 포함된 민감패턴도 마스킹
    if "event" in event_dict and isinstance(event_dict["event"], str):
        event_dict["event"] = redact_value(event_dict["event"])
    if "message" in event_dict and isinstance(event_dict["message"], str):
        event_dict["message"] = redact_value(event_dict["message"])
    return event_dict


# ─────────────────────────────────────────────────────────────
# 공통 processors
# ─────────────────────────────────────────────────────────────
def add_context(_, __, event_dict):
    """ContextVar에 저장된 request_id/user_id 자동 병합"""
    from common.utils.contextvars import request_id_ctx_var, user_id_ctx_var
    rid = request_id_ctx_var.get(None)
    uid = user_id_ctx_var.get(None)
    if rid is not None:
        event_dict["request_id"] = rid
    if uid is not None:
        event_dict["user_id"] = uid
    return event_dict

def add_timestamp(_, __, event_dict):
    """ISO8601Z 타임스탬프 추가"""
    event_dict["timestamp"] = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
    return event_dict

def add_level(_, method_name, event_dict):
    """로그 레벨을 level 키로 추가(INFO/ERROR 등)"""
    event_dict["level"] = method_name.upper()
    return event_dict

def rename_event_key(_, __, event_dict):
    """기본 event 키를 message로 변경(일관성)"""
    if "event" in event_dict and "message" not in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict

def drop_none_fields(_, __, event_dict):
    """값이 None인 필드는 로그에서 제거 (불필요한 None 노출 방지)"""
    return {k: v for k, v in event_dict.items() if v is not None}


# 개발 모드: 콘솔 렌더러
console_processors = [
    structlog.contextvars.merge_contextvars,   # structlog 컨텍스트와 병합
    add_context,                               # request_id/user_id 병합
    add_level,
    add_timestamp,
    redact_sensitive,                          # 민감정보 마스킹
    drop_none_fields,                          # None 필드 제거
    rename_event_key,
    structlog.dev.ConsoleRenderer(colors=True),
]

# 운영 모드: JSON 렌더러
json_processors = [
    structlog.contextvars.merge_contextvars,
    add_context,
    add_level,
    add_timestamp,
    redact_sensitive,
    drop_none_fields,
    rename_event_key,
    structlog.processors.JSONRenderer(),
]

# 공통(선행) 프로세서: 예외/스택
base_processors = [
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]
