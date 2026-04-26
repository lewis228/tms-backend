from fastapi import Depends, HTTPException, Request
from auth.tokens.bearer_token import bearer_token  

async def refresh_token(
    request: Request,
    user=Depends(bearer_token)  # Bearer Token 공통 검증 먼저 실행
):
    """
    Refresh Token 전용 검증
    """
    if request.state.token_type != "refresh":
        raise HTTPException(status_code=401, detail="Refresh Token이 아닙니다.")

    return user