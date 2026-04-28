# src/main.py — TMS Pro 백엔드 진입점 (ste 패턴)
"""
FastAPI 메인 애플리케이션.

ste/backend_sample 패턴:
  - lifespan 통합 (common/lifecycle/lifespan.py)
  - 미들웨어 순서: CORS → AccessLog → Auth → LogContext (역순 add)
  - 예외 핸들러 일괄 등록
  - 도메인 router 명시 등록

TMS Phase A — 시스템 도메인만 등록 (auth/user/team/rbac/file).
TMS 도메인 router (customer/terminal/vessel/location/driver/delivery_order/leg/
street_turn/settlement/rate_setting/notification/realtime/ai_intake/driver_mobile)
는 Phase B 이후 추가.
"""
import asyncio
import logging  # noqa: F401

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from common.const.path_consts import PUBLIC_FOLDER_PATH
from common.const.settings import settings
from common.exceptions.base import AppException
from common.exceptions.handlers import (
    app_exception_handler,
    global_exception_handler,
    http_exception_handler,
    sqlalchemy_exception_handler,
    timeout_exception_handler,
    validation_exception_handler,
)
from common.lifecycle.lifespan import lifespan
from common.middleware.access_log import AccessLogMiddleware
from common.middleware.auth import AuthMiddleware
from common.middleware.context import LogContextMiddleware

# ── 시스템 도메인 routers ────────────────────────────────────
from auth.router import router as auth_router
from user.router import router as user_router
from team.router import router as team_router
from rbac.router import router as rbac_router
from file.router import router as file_router

# ── TMS Master Data routers (Phase B) ────────────────────────
from customer.router import router as customer_router
from terminal.router import router as terminal_router
from vessel.router import router as vessel_router
from location.router import router as location_router
from driver.router import router as driver_router
from truck.router import router as truck_router
from equipment_pool.router import router as equipment_pool_router
from chassis.router import router as chassis_router

# ── TMS D/O / Leg / Settlement routers (Phase C) ─────────────
from rate_setting.router import router as rate_setting_router
from charge_code.router import router as charge_code_router
from rate_card.router import router as rate_card_router
from delivery_order.router import router as delivery_order_router
from container.router import router as container_router
from leg.router import router as leg_router
from leg_stop.router import router as leg_stop_router
from chassis_event.router import router as chassis_event_router
from leg_charge.router import router as leg_charge_router
from street_turn.router import router as street_turn_router
from settlement.router import router as settlement_router

# ── TMS Phase D routers (Notification / Realtime / AI Intake / Driver Mobile) ──
from notification.router import router as notification_router
from realtime.router import router as realtime_router
from ai_intake.router import router as ai_intake_router
from driver_mobile.router import router as driver_mobile_router

# ── TMS API Keys (개발자 통합용) ─────────────────────────────
from api_key.router import router as api_key_router


app = FastAPI(lifespan=lifespan, root_path=settings.ROOT_PATH)

# ── 미들웨어 (역순 add) ─────────────────────────────────────
# 1) LogContext (요청 ID 바인딩) → 2) Auth (user 식별) → 3) AccessLog (응답 기록)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(LogContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.ALLOWED_ORIGIN_REGEX,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization", "Content-Type", "Accept",
        "X-Client-Type", "X-Device-Key", "X-App-Version",
        "User-Agent", "X-Team-Id", "X-Request-ID",
    ],
)

# ── 예외 핸들러 ──────────────────────────────────────────────
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(asyncio.TimeoutError, timeout_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)

# ── 정적 파일 ───────────────────────────────────────────────
# /public — 로고 등 공용 에셋
app.mount("/public", StaticFiles(directory=PUBLIC_FOLDER_PATH), name="public")

# ── 시스템 도메인 router 등록 ────────────────────────────────
# 각 router 는 자체 prefix 에 /api/v1 을 직접 박는다 (ste 운영 패턴).
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(team_router)
app.include_router(rbac_router)
app.include_router(file_router)

# ── TMS Master Data router 등록 (Phase B) ────────────────────
app.include_router(customer_router)
app.include_router(terminal_router)
app.include_router(vessel_router)
app.include_router(location_router)
app.include_router(driver_router)
app.include_router(truck_router)
app.include_router(equipment_pool_router)
app.include_router(chassis_router)

# ── TMS D/O / Leg / Settlement router 등록 (Phase C) ─────────
app.include_router(rate_setting_router)
app.include_router(charge_code_router)
app.include_router(rate_card_router)
app.include_router(delivery_order_router)
app.include_router(container_router)
app.include_router(leg_router)
app.include_router(leg_stop_router)
app.include_router(chassis_event_router)
app.include_router(leg_charge_router)
app.include_router(street_turn_router)
app.include_router(settlement_router)

# ── TMS Phase D router 등록 ──────────────────────────────────
app.include_router(notification_router)
app.include_router(realtime_router)
app.include_router(ai_intake_router)
app.include_router(driver_mobile_router)

# ── TMS API Keys ─────────────────────────────────────────────
app.include_router(api_key_router)


@app.get("/", include_in_schema=False)
async def ping_root():
    return {"status": "connect success"}


@app.get("/health", include_in_schema=False)
async def ping_health():
    return {"status": "ok"}
