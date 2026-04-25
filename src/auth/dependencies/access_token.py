from fastapi import Depends, HTTPException, Request
from auth.dependencies.bearer_token import bearer_token

async def access_token(
    request: Request,
    _ = Depends(bearer_token)
):
    if request.state.token_type != "access":
        raise HTTPException(status_code=401, detail="Access Token이 아닙니다.")
