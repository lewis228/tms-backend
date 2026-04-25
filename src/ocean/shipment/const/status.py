from __future__ import annotations
from enum import StrEnum


class ShipmentStatus(StrEnum):
    """시스템 레벨 추적 상태 (MBL 전체). 컨테이너의 물리적 움직임 상태는
    ``ocean_container_events`` 타임라인이 담당하며, 이와 구분된다.

    전이 규칙은 `src/ocean/CLAUDE.md` 참조.
    """

    # 등록된 직후 ~ 첫 스크래핑 직전. POST /ocean/shipments 성공 시 기본값.
    PENDING = "pending"

    # Terminal49의 "Created" 상당. 첫 스크래핑 성공 + 컨테이너/이벤트 발견.
    # 이후 주기적 재스크래핑이 계속된다.
    TRACKING = "tracking"

    # 캐리어 DB 에 MBL 데이터가 아직 없음 (첫 스크래핑 OK 였지만 결과 비어있음).
    # 주기적으로 재시도 (기본 12시간).
    AWAITING_MANIFEST = "awaiting_manifest"

    # 영구 실패 — 잘못된 MBL 포맷, scraper 없음, max_retries 소진.
    # 사용자가 Resubmit 하면 다시 PENDING 으로 되돌린다.
    FAILED = "failed"

    # 모든 컨테이너가 "Empty In" 이벤트에 도달해 추적 종료,
    # 또는 사용자가 DELETE 로 수동 중단. ``next_scrape_at = NULL``.
    STOPPED = "stopped"

    # 사용자가 첫 스크래핑 완료 전에 취소한 경우.
    CANCELLED = "cancelled"


# 재시도 대상 status — Celery Beat 의 주기 스캔에 포함되는 상태.
RETRYABLE_STATUSES: frozenset[str] = frozenset(
    {
        ShipmentStatus.PENDING.value,
        ShipmentStatus.TRACKING.value,
        ShipmentStatus.AWAITING_MANIFEST.value,
    }
)


# Container 이벤트 description 이 이 목록에 들어있으면 해당 컨테이너는 "종료" 간주.
# Shipment 내 모든 컨테이너가 종료 상태면 shipment.status = STOPPED.
TERMINAL_EVENT_KEYWORDS: frozenset[str] = frozenset(
    {
        "empty in",
        "empty returned",
    }
)


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
