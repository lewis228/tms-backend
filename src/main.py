# src/main.py
"""
FastAPI 메인 애플리케이션 (범용 보일러플레이트)
"""
import logging
import asyncio
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path
from fastapi import FastAPI

from common.exceptions.handlers import (
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    global_exception_handler,
    timeout_exception_handler,
    sqlalchemy_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from common.exceptions.base import AppException
from fastapi.middleware.cors import CORSMiddleware

from common.const.settings import settings
from common.const.path_consts import PUBLIC_FOLDER_PATH
from common.middleware.access_log import AccessLogMiddleware
from common.middleware.context import LogContextMiddleware
from common.middleware.delay import DelayMiddleware
from common.middleware.auth import AuthMiddleware
from fastapi.staticfiles import StaticFiles

from common.lifecycle.lifespan import lifespan

# routers
from user.router import router as user_router
from auth.router import router as auth_router
from team.router import router as team_router
from rbac.router import router as rbac_router
from file.router import router as file_router
from api_key.router import router as api_key_router
from tag.router import router as tag_router
from customer.router import router as customer_router
from carrier.router import router as carrier_router
from location.router import router as location_router
from ocean.shipment.router import router as shipment_router, track_router
from ocean.container.router import (
    router as container_router,
    global_router as container_global_router,
)
from ocean.container_event.router import router as container_event_router
from ocean.scrape_log.router import router as scrape_log_router
from vessel.router import router as vessel_router
from common.events.ws_router import ws_router


app = FastAPI(lifespan=lifespan, root_path=settings.ROOT_PATH)


# Middleware (등록 역순으로 실행)
# 1) Context(요청ID) -> 2) Auth(user 식별) -> 3) AccessLog(응답 상태/지연 기록)
# app.add_middleware(DelayMiddleware, delay_seconds=2)  # 개발 시 지연 필요하면 활성화
app.add_middleware(AccessLogMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(LogContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_origin_regex,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization", "Content-Type", "Accept",
        "X-Client-Type", "X-Device-Key", "X-App-Version",
        "User-Agent", "X-Team-Id", "X-Request-ID",
    ],
)

# Exception handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(asyncio.TimeoutError, timeout_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)

# Static files
app.mount("/public", StaticFiles(directory=PUBLIC_FOLDER_PATH), name="public")

# Routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(team_router)
app.include_router(rbac_router)
app.include_router(file_router)
app.include_router(api_key_router)
app.include_router(tag_router)
app.include_router(customer_router)
app.include_router(carrier_router)
app.include_router(location_router)
app.include_router(shipment_router)
app.include_router(container_router)
app.include_router(container_global_router)
app.include_router(container_event_router)
app.include_router(scrape_log_router)
app.include_router(track_router)
app.include_router(vessel_router)
# WebSocket — 단일 엔드포인트 /ws (쿼리 param 으로 token + team_id).
# 현재는 shipment 이벤트 push 만 수행, 향후 채팅 / 알림도 같은 연결에 추가.
app.include_router(ws_router)


@app.get("/", include_in_schema=False)
async def ping_root():
    return {"status": "connect success"}


@app.get("/health", include_in_schema=False)
async def ping_health():
    return {"status": "ok"}
