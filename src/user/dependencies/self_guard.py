# common/guards/self_guard.py
from __future__ import annotations
from fastapi import Depends, status
from user.schemas.response import UserResponseSchema
from user.dependencies.current_user import get_current_user
from common.exceptions import AppException


async def require_self_only(
    user_id: int,  # ← 라우터 경로 파라미터 그대로 매칭됨
    me: UserResponseSchema = Depends(get_current_user),
) -> None:
    """
      본인만 접근 가능한 가드
    - /user/{user_id} 같은 라우터에서 사용
    - 라우터 예시:
        _self_guard: None = Depends(require_self_only)
    """
    if int(me.id) != int(user_id):
        raise AppException(
            code="FORBIDDEN",
            message="본인 계정만 접근할 수 있습니다.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
