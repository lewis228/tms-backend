"""FastAPI 앱 팩토리."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config import settings
from app.core.database import dispose_engines
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware, TenantContextMiddleware
from app.core.redis import close_redis
from app.domains.ai_intake.router import router as ai_intake_router
from app.domains.auth.router import router as auth_router
from app.domains.customers.router import router as customers_router
from app.domains.delivery_orders.router import router as delivery_orders_router
from app.domains.driver.router import router as driver_router
from app.domains.drivers.router import router as drivers_router
from app.domains.files.router import router as files_router
from app.domains.legs.router import router as legs_router
from app.domains.locations.router import router as locations_router
from app.domains.notifications.router import router as notifications_router
from app.domains.rate_settings.router import router as rate_settings_router
from app.domains.realtime.router import router as realtime_router
from app.domains.settlements.router import router as settlements_router
from app.domains.street_turns.router import router as street_turns_router
from app.domains.tenants.router import router as tenants_router
from app.domains.terminals.router import router as terminals_router
from app.domains.users.router import router as users_router
from app.domains.vessels.router import router as vessels_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield
    await dispose_engines()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="TMS Pro API",
        version="0.1.0",
        debug=settings.debug,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # 미들웨어: add_middleware 는 LIFO 로 실행됨 → 밖에서 안으로 CORS → ReqLog → TenantCtx
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health_router, prefix="/health", tags=["health"])
    app.include_router(auth_router)
    app.include_router(tenants_router)
    app.include_router(users_router)
    app.include_router(drivers_router)
    app.include_router(customers_router)
    app.include_router(terminals_router)
    app.include_router(vessels_router)
    app.include_router(locations_router)
    app.include_router(delivery_orders_router)
    app.include_router(legs_router)
    app.include_router(street_turns_router)
    app.include_router(rate_settings_router)
    app.include_router(settlements_router)
    app.include_router(files_router)
    app.include_router(notifications_router)
    app.include_router(realtime_router)
    app.include_router(ai_intake_router)
    app.include_router(driver_router)

    return app


app = create_app()
