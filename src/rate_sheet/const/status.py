# src/rate_sheet/const/status.py
from __future__ import annotations
from enum import StrEnum


class SheetKind(StrEnum):
    """Rate Sheet(요율표 슬롯) 종류 = rate_group.method 와 동일(denormalize).

    재설계(Zone×Zone):
    - ZONE   : from_zone → to_zone 매트릭스 (가장 일반)
    - CITY   : from_city/state → to_city/state 매트릭스 (zip 마스터 도시명)
    - MILE   : 거리 × per_unit (좌표 없이 per_unit 단일 셀)
    - HOURLY : 시간 × per_unit (좌표 없이 per_unit 단일 셀)
    """
    ZONE   = "ZONE"
    CITY   = "CITY"
    MILE   = "MILE"
    HOURLY = "HOURLY"


class RateMoveType(StrEnum):
    """요율 산정용 이동 적재상태 (leg 도메인과 디커플 — 재설계 독립)."""
    LOAD  = "LOAD"   # 적재
    EMPTY = "EMPTY"  # 공컨
    NONE  = "NONE"   # Bobtail (배율 미적용)


class RateServiceType(StrEnum):
    """요율 산정용 서비스 방식 (도착지 처리). 컨플루언스 'Leg 전체 유형':
    같은 From→To·Move 라도 Service Type 별로 요율표가 다르다.
    """
    LIVE = "LIVE"   # 도착지 대기/즉시 처리
    DROP = "DROP"   # 드롭 후 이탈
    NONE = "NONE"   # Bobtail/Shunt/Failed


class RateContainerSize(StrEnum):
    """요율 배율 기준 컨테이너 사이즈 (40ft 기준)."""
    SIZE_20 = "SIZE_20"   # 40ft × 0.85 (기본)
    SIZE_40 = "SIZE_40"   # 기준
    SIZE_45 = "SIZE_45"   # 40ft × 1.0 (기본)


class RateEntrySource(StrEnum):
    """요율 셀(rate_entry) 의 출처."""
    SHEET       = "SHEET"        # 그리드 수기 입력 (매트릭스)
    MILE_RATE   = "MILE_RATE"    # 마일 단가
    HOURLY_RATE = "HOURLY_RATE"  # 시간 단가
    MANUAL      = "MANUAL"       # 단건 수동 보정
    IMPORT      = "IMPORT"       # Excel/CSV import


class RateEntryAction(StrEnum):
    """rate_entry_history 의 변경 액션."""
    SET    = "SET"      # 새 값 등록
    CLOSE  = "CLOSE"    # 기존 버전 종료(effective_to 지정)
    SUPERSEDE = "SUPERSEDE"  # 같은 시작일 값 폐기(is_active=False)
    DELETE = "DELETE"   # 삭제(soft)


class SheetStatus(StrEnum):
    """슬롯 충진 상태 (서비스가 계산해서 응답에 노출 — 컬럼 아님)."""
    EMPTY    = "EMPTY"     # 셀 0
    PARTIAL  = "PARTIAL"   # 일부만
    ACTIVE   = "ACTIVE"    # 충진 (열린 셀 존재)
    INACTIVE = "INACTIVE"  # 비활성(시트 soft delete)
