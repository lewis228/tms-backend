# user/dependencies/current_user.py
from fastapi import Request, HTTPException, status
from user.schemas.response import UserResponseSchema  
import logging
logger = logging.getLogger(__name__)

def _coerce_user(user_obj) -> UserResponseSchema:
    """
    request.state.user 에 들어온 것을 안전하게 UserResponseSchema로 변환.
    dict/pydantic 모두 허용, 실패 시 예외.
    """
    if isinstance(user_obj, UserResponseSchema):
        return user_obj
    if isinstance(user_obj, dict):
        try:
            return UserResponseSchema.model_validate(user_obj)
        except Exception as e:
            logger.exception("state.user dict -> UserResponseSchema 변환 실패: %s", e)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="인증 컨텍스트 손상(state.user)",
    )


async def get_current_user(request: Request) -> UserResponseSchema:
    """
    🔹 토큰 검증은 '별도 가드(access_token)'에서 끝낸다.
    🔹 이 함수는 오직 request.state.user 를 꺼내서 반환만 한다.
    - 라우터에서 반드시 _1=Depends(access_token) 같은 가드를 앞에 두세요.
    """
    user = getattr(request.state, "user", None)
    if not user:
        # access_token 가드를 안 붙였거나, 내부 계약 위반
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
        )
    return _coerce_user(user)

# async def get_current_user(
#     request: Request,
#     _ = Depends(access_token),  # 이미 bearer_token까지 실행되어 state.user 세팅됨
# ) -> UserResponseSchema:
#     user = getattr(request.state, "user", None)

#     # 기존 주석 유지
#     if isinstance(user, UserResponseSchema):
#         return user

#     if isinstance(user, dict):
#         try:
#             # 기존 주석 유지
#             return UserResponseSchema.model_validate(user)
#         except Exception as e:
#             logger.exception("state.user dict -> UserSchema 변환 실패: %s", e)  # (로그 메시지는 그대로 둠)

#     # 이 지점이라면 access_token은 통과했는데 state.user가 없음 → 내부 계약 위반
#     raise HTTPException(status_code=500, detail="인증 컨텍스트 누락")
