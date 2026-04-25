"""Backfill 스크립트 — 정규화 컬럼 + event_hash 1회 채우기.

Step 3 마이그레이션 (`j0k1l2m3n4o5_add_vessel_and_normalized_columns`) 으로
아래 세 컬럼이 신설되었다:

  ocean_containers.size_type_code     ← ContainerSizeType Enum 값
  ocean_containers.physical_status    ← ContainerPhysicalStatus Enum 값
  ocean_container_events.event_type_code ← ContainerEventType Enum 값

Step 6 마이그레이션 (`k1l2m3n4o5p6_add_event_hash_unique`) 으로 추가:

  ocean_container_events.event_hash   ← SHA-256 hex (UNIQUE 제약용)

신설 직후엔 기존 row 가 전부 NULL / '' 이다. 다음 스크래핑 사이클에서
자동으로 채워지지만, **프론트 탭 (On Ship / Arrived) 이 이 컬럼으로 바로
필터링** 하므로 기존 데이터가 탭에 안 나타나는 공백이 생긴다.

이 스크립트가:
  1. raw 컬럼(`size_type`, `status`, `event_type`, `description`) 을 normalizer
     에 통과시켜 `*_code` 컬럼을 채움
  2. 기존 event 의 `event_hash` 를 sha256 로 채움 (UNIQUE 제약 유효화)

특징:
  • **Raw 컬럼은 건드리지 않음** (원본 보존 원칙).
  • **재실행 안전** — WHERE *_code IS NULL / event_hash = '' 로 이미 채워진
    행은 skip.
  • **배치 커밋** — 1,000 row 단위로 flush/commit 해서 대용량에서도 메모리 안전.
  • 모든 팀 공통 — team scope 없이 전 테이블 대상 (시스템 모드).

사용:
  cd backend_tracking-api
  PYTHONPATH=src .venv/bin/python scripts/backfill_normalized_columns.py

  # 특정 테이블만:
  PYTHONPATH=src .venv/bin/python scripts/backfill_normalized_columns.py --only containers
  PYTHONPATH=src .venv/bin/python scripts/backfill_normalized_columns.py --only events

  # Dry run (변경 안 함, 해석 결과만 로깅):
  PYTHONPATH=src .venv/bin/python scripts/backfill_normalized_columns.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from common.const.config_bootstrap import load_env  # noqa: F401
load_env()

import asyncio
import hashlib
from datetime import timezone
from typing import Optional

from sqlalchemy import select, update

from database.mysql_connection import write_session_maker
from ocean.container.model import ContainerModel
from ocean.container.normalizer import (
    normalize_event_type,
    normalize_physical_status,
    normalize_size_type,
)
from ocean.container_event.model import ContainerEventModel


BATCH_SIZE = 1000


def _compute_event_hash(container_id, timestamp, description) -> str:
    """scraping 레포의 `_event_hash` 와 동일한 알고리즘 — 양쪽에서 같은 값이
    나오도록 유지. 한쪽이라도 바뀌면 UNIQUE 제약이 과거 데이터 vs 신규 스크래핑
    사이에서 충돌하거나 중복을 놓칠 수 있음."""
    if timestamp is None:
        ts_part = "0"
    else:
        ts = timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ts_part = str(int(ts.timestamp()))
    payload = f"{container_id}|{ts_part}|{(description or '')[:500]}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def backfill_containers(dry_run: bool = False) -> tuple[int, int, int]:
    """ocean_containers 의 size_type_code / physical_status 채움.

    Returns:
        (scanned, updated, skipped) — skipped = raw 값 null 또는 normalizer 매칭 실패.
    """
    scanned = updated = skipped = 0
    batch_buffer: list[dict] = []

    async with write_session_maker() as db:
        # physical_status 또는 size_type_code 가 NULL 인 row 만. 이미 채워진 행은
        # skip → 재실행 안전.
        stmt = (
            select(
                ContainerModel.id,
                ContainerModel.size_type,
                ContainerModel.size_type_code,
                ContainerModel.status,
                ContainerModel.physical_status,
            )
            .where(
                (ContainerModel.size_type_code.is_(None))
                | (ContainerModel.physical_status.is_(None))
            )
            .order_by(ContainerModel.id.asc())
        )
        result = await db.stream(stmt)

        async for row in result:
            scanned += 1
            row_id, raw_size, cur_size_code, raw_status, cur_phys = row

            # 각 컬럼 독립적으로 — 한쪽만 null 일 수도 있음.
            new_size_code: Optional[str] = cur_size_code
            if cur_size_code is None and raw_size:
                new_size_code = normalize_size_type(raw_size)

            new_phys: Optional[str] = cur_phys
            if cur_phys is None and raw_status:
                new_phys = normalize_physical_status(raw_status)

            # 바뀌는 게 없으면 skip (원본 raw 가 비어있거나 normalizer 가 None 반환).
            if new_size_code == cur_size_code and new_phys == cur_phys:
                skipped += 1
                continue

            if dry_run:
                print(
                    f"[dry] container id={row_id}: "
                    f"size_type({raw_size!r}) → code={new_size_code!r}, "
                    f"status({raw_status!r}) → phys={new_phys!r}"
                )
                updated += 1
                continue

            batch_buffer.append(
                {
                    "id": row_id,
                    "size_type_code": new_size_code,
                    "physical_status": new_phys,
                }
            )
            updated += 1

            if len(batch_buffer) >= BATCH_SIZE:
                await _flush_container_batch(db, batch_buffer)
                batch_buffer.clear()
                print(f"  … containers scanned={scanned} updated={updated}")

        if batch_buffer:
            await _flush_container_batch(db, batch_buffer)
            batch_buffer.clear()

        if not dry_run:
            await db.commit()

    return scanned, updated, skipped


async def _flush_container_batch(db, rows: list[dict]) -> None:
    """Bulk UPDATE 로 한 배치를 한 번에 반영."""
    # SQLAlchemy 2.0 의 Core UPDATE … VALUES 대량 갱신.
    for r in rows:
        await db.execute(
            update(ContainerModel)
            .where(ContainerModel.id == r["id"])
            .values(
                size_type_code=r["size_type_code"],
                physical_status=r["physical_status"],
            )
        )
    await db.flush()


async def backfill_events(dry_run: bool = False) -> tuple[int, int, int]:
    """ocean_container_events 의 event_type_code + event_hash 채움.

    - event_type_code: description + raw event_type 으로 fuzzy 해석
    - event_hash: (container_id, timestamp, description) 으로 sha256 계산
      → UNIQUE(team_id, container_id, event_hash) 제약 유효화

    둘 중 하나라도 비어있으면 업데이트 대상 — 이미 둘 다 채워진 행은 skip.
    """
    scanned = updated = skipped = 0
    batch_buffer: list[dict] = []

    async with write_session_maker() as db:
        stmt = (
            select(
                ContainerEventModel.id,
                ContainerEventModel.container_id,
                ContainerEventModel.timestamp,
                ContainerEventModel.description,
                ContainerEventModel.event_type,
                ContainerEventModel.event_type_code,
                ContainerEventModel.event_hash,
            )
            .where(
                (ContainerEventModel.event_type_code.is_(None))
                | (ContainerEventModel.event_hash == "")
            )
            .order_by(ContainerEventModel.id.asc())
        )
        result = await db.stream(stmt)

        async for row in result:
            scanned += 1
            (
                row_id,
                container_id,
                timestamp,
                description,
                raw_type,
                cur_code,
                cur_hash,
            ) = row

            # event_type_code — 이미 채워진 건 유지.
            new_code: Optional[str] = cur_code
            if cur_code is None:
                new_code = (
                    normalize_event_type(raw_type)
                    or normalize_event_type(description)
                )

            # event_hash — 비어있으면 계산, 이미 있으면 유지.
            new_hash = cur_hash if cur_hash else _compute_event_hash(
                container_id, timestamp, description,
            )

            # 변경점 없으면 skip.
            if new_code == cur_code and new_hash == cur_hash:
                skipped += 1
                continue

            if dry_run:
                print(
                    f"[dry] event id={row_id}: "
                    f"event_type({raw_type!r}) / desc({description!r}) → "
                    f"code={new_code!r} hash={new_hash[:12]}..."
                )
                updated += 1
                continue

            batch_buffer.append(
                {
                    "id": row_id,
                    "event_type_code": new_code,
                    "event_hash": new_hash,
                }
            )
            updated += 1

            if len(batch_buffer) >= BATCH_SIZE:
                await _flush_event_batch(db, batch_buffer)
                batch_buffer.clear()
                print(f"  … events scanned={scanned} updated={updated}")

        if batch_buffer:
            await _flush_event_batch(db, batch_buffer)
            batch_buffer.clear()

        if not dry_run:
            await db.commit()

    return scanned, updated, skipped


async def _flush_event_batch(db, rows: list[dict]) -> None:
    for r in rows:
        await db.execute(
            update(ContainerEventModel)
            .where(ContainerEventModel.id == r["id"])
            .values(
                event_type_code=r["event_type_code"],
                event_hash=r["event_hash"],
            )
        )
    await db.flush()


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=["containers", "events"],
        default=None,
        help="특정 테이블만 처리",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="변경 없이 해석 결과만 출력",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Backfill normalized columns")
    print(f"  mode = {'DRY RUN' if args.dry_run else 'COMMIT'}")
    print(f"  only = {args.only or 'all'}")
    print("=" * 70)

    if args.only in (None, "containers"):
        print("\n▶ ocean_containers ...")
        scanned, updated, skipped = await backfill_containers(dry_run=args.dry_run)
        print(
            f"  done. scanned={scanned} updated={updated} skipped={skipped}"
        )

    if args.only in (None, "events"):
        print("\n▶ ocean_container_events ...")
        scanned, updated, skipped = await backfill_events(dry_run=args.dry_run)
        print(
            f"  done. scanned={scanned} updated={updated} skipped={skipped}"
        )

    print("\n✅ backfill finished.")


if __name__ == "__main__":
    asyncio.run(main())
