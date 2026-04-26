"""
요청 단위 ContextVar 정의
- request_id / user_id는 structlog 프로세서에서 자동 사용됨
"""

from contextvars import ContextVar
#  각 요청(request)마다 고유한 request_id를 안전하게 저장하기 위한 컨텍스트 변수
# - 비동기 요청 간 충돌 없이 개별 요청 단위로 값을 보존할 수 있음
request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)


#  로그인된 사용자 ID를 요청별로 안전하게 보관하는 컨텍스트 변수
# - 로그나 에러 추적 시 어떤 사용자가 발생시킨 요청인지 구분 가능
user_id_ctx_var: ContextVar[int | None] = ContextVar("user_id", default=None)
