import asyncio
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class DelayMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, delay_seconds: float = 1.0):
        super().__init__(app)
        self.delay = delay_seconds

    async def dispatch(self, request: Request, call_next):
        # CORS 프리플라이트(OPTIONS)는 지연하지 않는게 개발 편의에 좋아요.
        if request.method == "OPTIONS":
            return await call_next(request)

        await asyncio.sleep(self.delay)
        response: Response = await call_next(request)
        return response
