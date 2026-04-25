"""자유-형식 location 텍스트 → ``locations.id`` 매퍼.

3단계 resolution:
  1) **aliases 캐시** — 이전에 성공한 매핑 재사용 (O(1) DB 조회)
  2) **UN/LOCODE 패턴 탐지** — ``KRPUS`` 같은 5자 대문자 → 직접 조회
  3) **이름 정확/퍼지 매칭** — normalize 후 exact, 그래도 실패면 rapidfuzz

매핑 성공하면 **자동으로 alias 테이블에 기록** → 동일 raw_text 재호출 시 1단계로 끝.
실패하면 None 반환 + 호출자가 FK=NULL 로 처리.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from location.model import LocationModel, LocationAliasModel


logger = logging.getLogger(__name__)

# UN/LOCODE 는 2자 국가 + 3자 지역 = 5자 대문자.
UNLOCODE_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}$")

# 퍼지 매칭 임계점 — 90 이상만 자동 매핑. 아래면 사람에게 돌림.
FUZZY_THRESHOLD = 90


@dataclass
class MapResolution:
    location_id: int
    confidence: str  # 'alias' / 'unlocode' / 'exact' / 'fuzzy'


def _normalize(text: str) -> str:
    """raw 텍스트를 정규화 — 대문자화, 쉼표 공백 정리."""
    if not text:
        return ""
    s = text.strip().upper()
    # 쉼표 주변 공백 정리: "BUSAN ,REPUBLIC OF KOREA" → "BUSAN,REPUBLIC OF KOREA"
    s = re.sub(r"\s*,\s*", ",", s)
    # 연속 공백 하나로
    s = re.sub(r"\s+", " ", s)
    return s


def _extract_primary_token(normalized: str) -> str:
    """"BUSAN,REPUBLIC OF KOREA" → "BUSAN". 첫 쉼표 앞 토큰이 대개 도시명."""
    head = normalized.split(",", 1)[0].strip()
    return head


async def resolve_location(
    db: AsyncSession,
    raw_text: Optional[str],
    *,
    carrier_id: Optional[int] = None,
    cache_result: bool = True,
) -> Optional[int]:
    """raw 텍스트 → location_id. 실패 시 None.

    Async (tracking-api) 용. ``carrier_id`` 가 주어지면 해당 선사 전용 alias
    도 함께 검사한다 (carrier_id=NULL 인 전역 alias 가 항상 먼저 검색됨).
    """
    if not raw_text or not raw_text.strip():
        return None

    normalized = _normalize(raw_text)

    # ── 1) alias 캐시 ────────────────────────────────────────
    stmt = select(LocationAliasModel.location_id).where(
        LocationAliasModel.raw_text == raw_text,
        LocationAliasModel.is_active.is_(True),
    )
    if carrier_id is not None:
        stmt = stmt.where(
            (LocationAliasModel.carrier_id == carrier_id)
            | (LocationAliasModel.carrier_id.is_(None))
        )
    else:
        stmt = stmt.where(LocationAliasModel.carrier_id.is_(None))
    cached = await db.scalar(stmt)
    if cached is not None:
        return cached

    # ── 2) UN/LOCODE 패턴 탐지 ───────────────────────────────
    if UNLOCODE_RE.match(normalized):
        row = await db.scalar(
            select(LocationModel).where(
                LocationModel.unlocode == normalized,
                LocationModel.is_active.is_(True),
            )
        )
        if row is not None:
            if cache_result:
                await _record_alias(db, row.id, raw_text, carrier_id, "unlocode")
            return row.id

    # ── 3) 이름 exact 매치 (정규화된 primary token 기준) ────
    primary = _extract_primary_token(normalized)
    if primary:
        row = await db.scalar(
            select(LocationModel).where(
                LocationModel.name == primary.title(),
                LocationModel.is_active.is_(True),
            ).limit(1)
        )
        if row is None:
            # uppercase 대소문자 무관 한 번 더 시도
            row = await db.scalar(
                select(LocationModel).where(
                    LocationModel.name.ilike(primary),
                    LocationModel.is_active.is_(True),
                ).limit(1)
            )
        if row is not None:
            if cache_result:
                await _record_alias(db, row.id, raw_text, carrier_id, "exact")
            return row.id

    # ── 4) 퍼지 매칭 ────────────────────────────────────────
    # 후보를 좁히기 위해 같은 country 로 1차 필터 (텍스트에 국가명/코드가 있으면).
    # 단순화: 전체 locations 대상 퍼지 — 데이터가 116K 라 한 번에 밀어넣긴
    # 부담. 후보를 이름 ILIKE ‘%prefix%’ 로 줄인 뒤 퍼지.
    if primary and len(primary) >= 3:
        candidates_q = select(LocationModel.id, LocationModel.name).where(
            LocationModel.is_active.is_(True),
            LocationModel.name.ilike(f"{primary[:3]}%"),
        ).limit(200)
        result = await db.execute(candidates_q)
        candidates = result.all()
        if candidates:
            names = [c.name for c in candidates]
            match = process.extractOne(
                primary, names, scorer=fuzz.token_sort_ratio
            )
            if match is not None and match[1] >= FUZZY_THRESHOLD:
                matched_name = match[0]
                matched_id = next(c.id for c in candidates if c.name == matched_name)
                if cache_result:
                    await _record_alias(db, matched_id, raw_text, carrier_id, "fuzzy")
                return matched_id

    logger.info(
        "location_mapping_failed", extra={"raw_text": raw_text, "carrier_id": carrier_id}
    )
    return None


async def _record_alias(
    db: AsyncSession,
    location_id: int,
    raw_text: str,
    carrier_id: Optional[int],
    confidence: str,
) -> None:
    """성공한 매핑을 alias 캐시에 저장.

    **nested transaction (SAVEPOINT) 로 감싼다** — alias 쓰기 실패가 바깥
    transaction 의 shipment/event 변경을 날려버리지 않도록. 중복 alias 에서
    발생하는 IntegrityError 는 정상 경로로 간주.
    """
    try:
        async with db.begin_nested():
            alias = LocationAliasModel(
                location_id=location_id,
                raw_text=raw_text,
                carrier_id=carrier_id,
                confidence=confidence,
            )
            db.add(alias)
    except Exception as e:  # noqa: BLE001
        logger.debug(
            "alias_record_skip",
            extra={"raw_text": raw_text, "err": str(e)},
        )
