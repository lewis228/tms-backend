from fastapi import Depends, HTTPException, Request
from starlette.status import HTTP_403_FORBIDDEN
from user.dependencies.current_user import get_current_user
from user.const.roles import RolesEnum
from user.schemas.response import UserResponseSchema

def role_guard(*required_roles: RolesEnum):                     # 여러 역할 허용 가능
    required = set(required_roles)
    async def guard(user: UserResponseSchema  = Depends(get_current_user)):
        if user.role not in required:
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="권한이 없습니다.")
    return guard


# 아래와 같이 사용하면 어드민과 유저의 역할을 가진 사용자가 접근이 가능하도록 할 수 있다. 즉 여러개 파라미터로 보낼 수 있다.
# _ = Depends(role_guard(RolesEnum.ADMIN, RolesEnum.USER))

#  → ADMIN 이거나 USER 이면 통과.
#  즉 in required 체크라서 user.role이 그 집합 중 하나면 허용되는 거예요.