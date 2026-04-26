from fastapi.responses import JSONResponse
from common.exceptions.base import AppException

def middleware_error_handler(e: Exception):
    """미들웨어에서 발생하는 에러를 처리하는 공통 함수"""
    if isinstance(e, AppException):
        return JSONResponse(status_code=e.status_code, content=e.to_dict())

    return JSONResponse(
        status_code=500,
        content={
                "error": {
                "code": e.__class__.__name__,
                "message": str(e),
                "status_code": 500,
            }
        },
    ) 