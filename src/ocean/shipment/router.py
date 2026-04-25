from __future__ import annotations
import logging as _logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from common.pagination.schemas.pagination_response import CursorPaginationResult
from database.dependencies import get_write_db, get_read_db
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from auth.dependencies.rate_limit import rate_limit
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema
from ocean.shipment.schemas.request import (
    CreateShipmentRequestSchema,
    PaginateShipmentRequestSchema,
    UpdateShipmentRequestSchema,
)
from ocean.shipment.schemas.response import (
    ShipmentResponseSchema,
    ShipmentDetailResponseSchema,
    TrackResponseSchema,
)
from ocean.shipment.service import ShipmentService
from celery_app import celery
from cache.redis_connection import redis_client, write_redis
from common.events.publisher import publish_team_event


SCRAPE_LOCK_PREFIX = "scraping:lock:"
SCRAPE_LOCK_TTL = 600  # 10분

logger = _logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ocean/shipments", tags=["shipment"])
track_router = APIRouter(prefix="/api/v1/ocean", tags=["track"])


async def _dispatch_scrape(shipment: ShipmentResponseSchema) -> None:
    """Celery 스크래핑 태스크를 dispatch.

    Redis SET NX 락을 먼저 획득한 경우에만 send_task. 락 획득 실패는
    이미 다른 경로(Beat 또는 직전 요청)가 dispatch 했다는 뜻이므로 조용히 skip.
    send_task 가 실패하면 락을 해제해 다음 사이클이 재시도 가능하게 한다.

    Shipment 상태가 tracking/pending/... 어디든 호출되도, 실행 중복은 Redis
    락이 막는다. 호출부(create_shipment, resubmit)는 이 함수 한 번만 호출.
    """
    lock_key = f"{SCRAPE_LOCK_PREFIX}{shipment.mbl}"
    acquired = await redis_client.set(lock_key, "1", ex=SCRAPE_LOCK_TTL, nx=True)
    if not acquired:
        return
    try:
        celery.send_task(
            "ocean.tasks.scrape.scrape_mbl",
            kwargs={
                "shipment_id": shipment.id,
                "mbl": shipment.mbl,
                # 스크래퍼 측은 carrier 문자열을 informational/로깅용으로만
                # 받고 실제 스크래퍼 선택은 MBL prefix 로 한다. nested carrier
                # 객체에서 name 만 뽑아 전달.
                "carrier": shipment.carrier.name if shipment.carrier else None,
            },
            queue="scraping-ocean",
        )
    except Exception:
        try:
            await redis_client.delete(lock_key)
        except Exception as del_err:  # noqa: BLE001
            logger.error(
                "Failed to release scrape lock for %s after send_task error: %s",
                shipment.mbl,
                del_err,
            )
        raise


# ── Shipments CRUD ──────────────────────────────────────


@router.post("", response_model=ShipmentResponseSchema, status_code=201)
async def create_shipment(
    body: CreateShipmentRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    svc = ShipmentService(db, team_id)
    result = await svc.create_shipment(body, creator_user_id=me.id)

    # Worker가 shipment row를 조회할 때 이미 커밋된 상태여야 하므로 send_task 전에 명시적 commit.
    # (get_write_db 디펜던시의 종료 시 commit이 한 번 더 호출되지만, SQLAlchemy async session에서
    #  이미 커밋된 세션의 재커밋은 no-op이라 안전하다. 의도적 이중 commit.)
    await db.commit()
    # 팀 WS 채널에 "새 shipment 등록" 이벤트 발행 — 리스트 뷰가 실시간으로 append.
    await publish_team_event(
        write_redis,
        team_id,
        "shipment.created",
        {"shipment_id": result.id, "mbl": result.mbl, "status": result.status},
    )
    await _dispatch_scrape(result)
    return result


@router.post(
    "/{shipment_id}/resubmit",
    response_model=ShipmentResponseSchema,
)
async def resubmit_shipment(
    shipment_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """실패/중단된 shipment 를 다시 추적 — 같은 row 재사용 모델.
    status 를 PENDING 으로 되돌리고 Celery 태스크를 다시 dispatch.
    """
    svc = ShipmentService(db, team_id)
    result = await svc.resubmit_shipment(shipment_id)
    await db.commit()
    await publish_team_event(
        write_redis,
        team_id,
        "shipment.status.changed",
        {
            "shipment_id": result.id,
            "mbl": result.mbl,
            "new_status": result.status,
            "reason": "resubmit",
        },
    )
    await _dispatch_scrape(result)
    return result


@router.get("", response_model=CursorPaginationResult[ShipmentResponseSchema])
async def list_shipments(
    request: PaginateShipmentRequestSchema = Depends(),
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    svc = ShipmentService(db, team_id)
    return await svc.list_shipments(request)


@router.get("/{shipment_id}", response_model=ShipmentDetailResponseSchema)
async def get_shipment(
    shipment_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    svc = ShipmentService(db, team_id)
    return await svc.get_shipment_detail(shipment_id)


@router.patch("/{shipment_id}", response_model=ShipmentResponseSchema)
async def update_shipment(
    shipment_id: int,
    body: UpdateShipmentRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    svc = ShipmentService(db, team_id)
    return await svc.update_shipment(shipment_id, body, updater_user_id=me.id)


@router.delete("/{shipment_id}", status_code=204)
async def delete_shipment(
    shipment_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """DELETE = 수동 "Stop Tracking" — status 를 STOPPED 로 전이시킨다.
    Row 자체는 보존 (사용자가 Resubmit 으로 재개 가능)."""
    svc = ShipmentService(db, team_id)
    result = await svc.stop_shipment(shipment_id)
    await publish_team_event(
        write_redis,
        team_id,
        "shipment.status.changed",
        {
            "shipment_id": result.id,
            "mbl": result.mbl,
            "new_status": result.status,
            "reason": "manual_stop",
        },
    )


# ── Track (MBL 바로 조회) ───────────────────────────────


@track_router.get("/track", response_model=TrackResponseSchema)
async def track(
    mbl: str = Query(..., description="Master B/L 번호"),
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    svc = ShipmentService(db, team_id)
    return await svc.track_by_mbl(mbl)
