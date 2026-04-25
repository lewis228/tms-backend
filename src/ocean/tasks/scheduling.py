# src/tasks/scheduling.py
"""
Celery Beat 스케줄링 태스크
- shipments 테이블에서 next_scrape_at이 현재보다 과거인 건을 찾아
  carrier.scrape 태스크를 Redis Queue에 등록하고, next_scrape_at을 갱신한다.
"""
import logging
from datetime import datetime, timedelta, timezone

import redis as sync_redis
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import sessionmaker, Session
from urllib.parse import quote_plus

from celery_app import celery
from common.const.settings import settings
# 전체 모델을 한번에 등록해야 ShipmentModel.relationship("TeamModel") 등이 해소됨.
from common.model import models_registry  # noqa: F401
from ocean.shipment.model import ShipmentModel

logger = logging.getLogger(__name__)

_redis_kwargs: dict = dict(
    host=settings.REDIS_WRITE_HOST if settings.is_redis_read_write_split else settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD or None,
    decode_responses=True,
)
if settings.REDIS_SSL:
    # ElastiCache는 TLS만 지원하고 자체 서명 인증서를 쓰므로 CERT_NONE.
    _redis_kwargs["ssl"] = True
    _redis_kwargs["ssl_cert_reqs"] = None

_redis = sync_redis.Redis(**_redis_kwargs)

SCRAPE_LOCK_PREFIX = "scraping:lock:"
SCRAPE_LOCK_TTL = 600  # 10분


def _build_sync_dsn() -> str:
    """Celery Worker용 동기 MySQL DSN (PyMySQL)"""
    host = settings.DB_WRITE_HOST if settings.is_db_read_write_split else settings.DB_HOST
    if host in ("localhost", "::1"):
        host = "127.0.0.1"
    user = quote_plus(settings.DB_USERNAME)
    pwd = settings.DB_PASSWORD or ""
    auth = f"{user}:{quote_plus(pwd)}@" if pwd else f"{user}@"
    return f"mysql+pymysql://{auth}{host}:{settings.DB_PORT}/{settings.DB_DATABASE}?charset=utf8mb4"


_engine = create_engine(
    _build_sync_dsn(),
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
    pool_pre_ping=True,
)


# UTC 원칙: 모든 MySQL 커넥션이 세션 타임존을 UTC로 설정
@event.listens_for(_engine, "connect")
def _set_utc(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    try:
        cur.execute("SET time_zone = '+00:00'")
    finally:
        cur.close()


_SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def _calc_next_scrape_at(shipment: ShipmentModel, now: datetime) -> datetime | None:
    """상태별 다음 스크래핑 시간 계산.

    status 값은 `ocean/shipment/const/status.py:ShipmentStatus` 참조.
    종료 상태(stopped / failed / cancelled)는 None 반환 → Beat 가 더이상 dispatch 안 함.
    """
    status = (shipment.status or "").lower()

    if status in ("stopped", "failed", "cancelled"):
        return None

    if status == "awaiting_manifest":
        # 캐리어에 아직 MBL 이 안 올라왔음 — 12시간 주기로 재시도.
        return now + timedelta(hours=12)

    # status == "tracking" 또는 "pending" (pending 은 보통 Beat 가 잡기 전에
    # create 라우터가 inline dispatch 하지만, 실패로 남은 pending 이 있으면 Beat 가 커버).
    if shipment.eta:
        if shipment.eta.tzinfo is None:
            # DateTime(timezone=True) + 세션 UTC 설정이라 원칙적으로 naive는 들어올 수 없다.
            # 이 경로가 실행되면 schema/data 오염 신호 — 경고 로그 후 UTC로 간주.
            logger.warning(
                "shipment.id=%s eta is naive (%s); assuming UTC. Schema drift suspected.",
                shipment.id, shipment.eta,
            )
            eta = shipment.eta.replace(tzinfo=timezone.utc)
        else:
            eta = shipment.eta
        if (eta - now) <= timedelta(days=3):
            return now + timedelta(hours=6)

    return now + timedelta(hours=12)


@celery.task(name="ocean.tasks.scheduling.check_and_schedule_scrapes")
def check_and_schedule_scrapes() -> dict:
    """
    매 1시간마다 실행:
    1. next_scrape_at <= now 인 shipments 조회
    2. 각 MBL에 대해 carrier.scrape 태스크 등록
    3. 상태별로 next_scrape_at 갱신
    """
    now = datetime.now(timezone.utc)
    dispatched = 0

    with _SessionLocal() as db:
        shipments = db.execute(
            select(ShipmentModel).where(
                ShipmentModel.is_active.is_(True),
                ShipmentModel.next_scrape_at.isnot(None),
                ShipmentModel.next_scrape_at <= now,
            )
        ).scalars().all()

        skipped = 0
        for shipment in shipments:
            lock_key = f"{SCRAPE_LOCK_PREFIX}{shipment.mbl}"

            # SET NX로 락을 먼저 획득한 경우에만 task를 보낸다.
            # 다른 경로(POST /shipments 또는 이미 처리 중인 워커)가 락을 잡고 있으면 skip.
            acquired = _redis.set(lock_key, "1", ex=SCRAPE_LOCK_TTL, nx=True)
            if not acquired:
                logger.info("Skipping MBL %s — scraping lock exists", shipment.mbl)
                skipped += 1
                continue

            # scraping 서버의 Celery Worker로 태스크 전송.
            # 전송 실패 시 락이 10분간 고아로 남지 않도록 해제.
            # NOTE: `shipment.carrier` 는 CarrierModel 관계 객체라 JSON 직렬화 불가.
            # 이름 문자열만 힌트로 전달 — scraping 워커가 MBL prefix 로 재해석.
            carrier_hint = shipment.carrier.name if shipment.carrier else None
            try:
                celery.send_task(
                    "ocean.tasks.scrape.scrape_mbl",
                    kwargs={
                        "shipment_id": shipment.id,
                        "mbl": shipment.mbl,
                        "carrier": carrier_hint,
                    },
                    queue="scraping-ocean",
                )
            except Exception as e:  # noqa: BLE001
                # Redis 장애로 delete가 또 실패하면 원본 send_task 예외 정보를 덮어쓰게 되므로
                # 자체 try/except로 감싸 로깅만 하고 loop는 계속 진행.
                try:
                    _redis.delete(lock_key)
                except Exception as del_err:  # noqa: BLE001
                    logger.error(
                        "Failed to release scrape lock for MBL %s after send_task error: %s",
                        shipment.mbl, del_err,
                    )
                logger.error("send_task failed for MBL %s: %s", shipment.mbl, e)
                skipped += 1
                continue

            next_at = _calc_next_scrape_at(shipment, now)
            db.execute(
                update(ShipmentModel)
                .where(ShipmentModel.id == shipment.id)
                .values(next_scrape_at=next_at)
            )
            dispatched += 1

        db.commit()

    return {"dispatched": dispatched, "skipped": skipped, "checked_at": now.isoformat()}
