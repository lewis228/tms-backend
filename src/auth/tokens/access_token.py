from fastapi import Depends, HTTPException, Request
from auth.tokens.bearer_token import bearer_token  

async def access_token(
    request: Request,
    #user = Depends(BearerTokenDependency)  # 만일 추후에 accessToken 통과 후 바로 user 데이터가 필요한 경우 사용
    _ = Depends(bearer_token) # Bearer Token 공통 검증 먼저 실행
):
    """
    Access Token 전용 검증
    """
    if request.state.token_type != "access":
        raise HTTPException(status_code=401, detail="Access Token이 아닙니다.")

    # return user