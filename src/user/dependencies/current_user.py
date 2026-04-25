from fastapi import Request, HTTPException, status
from user.schemas.response import UserResponseSchema
import logging
logger = logging.getLogger(__name__)

def _coerce_user(user_obj) -> UserResponseSchema:
    if isinstance(user_obj, UserResponseSchema):
        return user_obj
    if isinstance(user_obj, dict):
        try:
            return UserResponseSchema.model_validate(user_obj)
        except Exception as e:
            logger.exception("state.user dict -> UserResponseSchema conversion failed: %s", e)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Auth context corrupted (state.user)")


async def get_current_user(request: Request) -> UserResponseSchema:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return _coerce_user(user)
