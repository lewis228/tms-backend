"""
로깅 시 extra 데이터 타입 힌트 (선택)
"""
from typing import TypedDict, Optional

class LogExtra(TypedDict, total=False):
    request_id: Optional[str]
    user_id: Optional[int]
    ip: Optional[str]
    path: Optional[str]
