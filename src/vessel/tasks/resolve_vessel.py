"""Celery task: 단일 선박 이름을 AIS provider 로 조회 + DB 캐싱.

================================================================================
호출 시점
================================================================================
Ocean scraping 파이프라인이 shipment 를 UPSERT 한 직후:
  - `vessel_name` 필드가 새로 세팅됐고
  - 매핑되는 vessel row 가 아직 없거나 MMSI 가 없을 때

Ocean scrape task 말미에 `resolve_vessel.delay(shipment_id)` 로 enqueue.
당장 네트워크 호출이 필요하지 않으니 shipment upsert 의 트랜잭션에서는 빼고
async 로 처리 (스크래핑 자체 응답 속도에 영향 없게).

================================================================================
흐름
================================================================================
    1. DB 에서 shipment 로드 → vessel_name 추출
    2. VesselService.resolve_by_name(name) 호출
       → AIS provider search → DB upsert (MMSI/IMO 채움)
       → VesselModel 반환
    3. ocean_shipments.vessel_id 를 방금 찾은 vessel 로 UPDATE
       (마이그레이션 후 vessel_id 필드 추가되면 활성화)

================================================================================
재시도 정책
================================================================================
- provider 가 rate limit / 5xx 반환 시 Celery autoretry (최대 3회, 지수 백오프).
- 400 / 이름 없음은 재시도해도 소용없으니 silent 종료.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import structlog

# NOTE: celery_app 경로는 기존 프로젝트 관례에 맞춰 조정.
from celery_app import celery as celery_app
from database.mysql_connection import async_session_maker as async_session_factory
from vessel.service import VesselService

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="vessel.resolve_vessel",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
)
def resolve_vessel_task(
    *,
    shipment_id: Optional[int] = None,
    vessel_name: str,
    imo_number: Optional[str] = None,
) -> Optional[int]:
    """선박 이름 해석 후 vessel.id 반환.

    shipment_id 를 넘겨주면 ocean_shipments.vessel_id 업데이트까지 한다 (TODO).
    그냥 이름만 해석하고 싶으면 shipment_id 없이 호출.
    """
    return asyncio.run(
        _run(vessel_name=vessel_name, imo_number=imo_number, shipment_id=shipment_id)
    )


async def _run(
    *,
    vessel_name: str,
    imo_number: Optional[str],
    shipment_id: Optional[int],
) -> Optional[int]:
    async with async_session_factory() as db:
        svc = VesselService(db)
        vessel = await svc.resolve_by_name(name=vessel_name, imo_number=imo_number)
        if vessel is None:
            logger.info("resolve_vessel_noop", name=vessel_name)
            return None

        # TODO: ocean_shipments 에 vessel_id 필드 추가 후 아래 활성화.
        # if shipment_id is not None:
        #     from ocean.shipment.model import ShipmentModel
        #     from sqlalchemy import update as sa_update
        #     await db.execute(
        #         sa_update(ShipmentModel)
        #         .where(ShipmentModel.id == shipment_id)
        #         .values(vessel_id=vessel.id)
        #     )

        await db.commit()
        logger.info(
            "resolve_vessel_ok",
            name=vessel_name,
            mmsi=vessel.mmsi,
            imo=vessel.imo_number,
            shipment_id=shipment_id,
        )
        return vessel.id
