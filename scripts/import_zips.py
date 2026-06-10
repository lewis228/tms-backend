# scripts/import_zips.py
"""미국 zip 마스터(zip_code 테이블) 외부 적재.

- 기본: GeoNames US.zip 다운로드 → US.txt 파싱 → bulk insert.
- 오프라인/실패 시: fallback 소량(시드 도시) insert (테이블 안 비게).
- seed.py 가 load_zip_codes() 를 호출해 자립 적재(zip 하드코딩 금지).

실행:
  PYTHONPATH=src python scripts/import_zips.py            # 전체 US 다운로드
  PYTHONPATH=src python scripts/import_zips.py --states CA,NV
"""
from __future__ import annotations
import asyncio
import io
import zipfile

from sqlalchemy import text, insert
from sqlalchemy.ext.asyncio import AsyncSession

import common.model.models_registry  # noqa: F401
from database.mysql_connection import write_engine
from zip_code.model import ZipCodeModel

GEONAMES_URL = "https://download.geonames.org/export/zip/US.zip"

# 다운로드 실패 시 최소 폴백 (시드 도시 + 인근). 테이블이 비지 않게.
_FALLBACK = [
    # zip, city, state, county, lat, lng
    ("90745", "Carson", "CA", "Los Angeles", 33.831, -118.281),
    ("90802", "Long Beach", "CA", "Los Angeles", 33.768, -118.193),
    ("90731", "San Pedro", "CA", "Los Angeles", 33.736, -118.292),
    ("92335", "Fontana", "CA", "San Bernardino", 34.101, -117.459),
    ("92336", "Fontana", "CA", "San Bernardino", 34.131, -117.459),
    ("91761", "Ontario", "CA", "San Bernardino", 34.040, -117.612),
    ("91762", "Ontario", "CA", "San Bernardino", 34.063, -117.652),
    ("90021", "Los Angeles", "CA", "Los Angeles", 34.030, -118.236),
    ("90040", "Commerce", "CA", "Los Angeles", 33.996, -118.154),
    ("92376", "Rialto", "CA", "San Bernardino", 34.116, -117.384),
]


async def _download_geonames() -> list[tuple]:
    """GeoNames US.zip → [(zip, city, state, county, lat, lng), ...]. 실패 시 예외."""
    import httpx
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(GEONAMES_URL)
        resp.raise_for_status()
    out: list[tuple] = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open("US.txt") as f:
            for raw in io.TextIOWrapper(f, encoding="utf-8"):
                p = raw.rstrip("\n").split("\t")
                if len(p) < 12:
                    continue
                # 0:country 1:postal 2:place(city) 3:admin1(state name) 4:admin1code(state) 5:admin2(county) ... 9:lat 10:lng
                zip_, city, state, county = p[1], p[2], p[4], p[5] or None
                try:
                    lat, lng = float(p[9]) if p[9] else None, float(p[10]) if p[10] else None
                except ValueError:
                    lat, lng = None, None
                if zip_ and city and state:
                    out.append((zip_, city, state, county, lat, lng))
    return out


async def load_zip_codes(db: AsyncSession, *, states: list[str] | None = None,
                         fallback_minimal: bool = True) -> int:
    """zip_code 테이블 적재(멱등: truncate 후 insert). 반환=행수."""
    try:
        rows = await _download_geonames()
        src = "geonames"
    except Exception as e:  # noqa: BLE001 (네트워크/파싱 실패 → 폴백)
        if not fallback_minimal:
            raise
        print(f"  [warn] GeoNames 다운로드 실패({type(e).__name__}) → 폴백 {len(_FALLBACK)}행 사용")
        rows, src = _FALLBACK, "fallback"

    if states:
        keep = {s.strip().upper() for s in states}
        rows = [r for r in rows if r[2].upper() in keep]

    # 중복 zip 제거(GeoNames 에 동일 zip 다중 place 존재 — 첫 행 채택)
    seen: set[str] = set()
    deduped = []
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        deduped.append(r)

    await db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    await db.execute(text("TRUNCATE TABLE zip_code"))
    await db.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    payload = [
        {"zip": z, "city": c, "state": st, "county": co, "latitude": la, "longitude": ln}
        for (z, c, st, co, la, ln) in deduped
    ]
    CHUNK = 1000
    for i in range(0, len(payload), CHUNK):
        await db.execute(insert(ZipCodeModel), payload[i:i + CHUNK])
    await db.flush()
    print(f"  zip_code 적재: {len(payload)}행 (source={src}{', states='+','.join(states) if states else ''})")
    return len(payload)


async def main():
    import sys
    states = None
    for i, a in enumerate(sys.argv):
        if a == "--states" and i + 1 < len(sys.argv):
            states = sys.argv[i + 1].split(",")
    async with AsyncSession(write_engine, expire_on_commit=False) as db:
        n = await load_zip_codes(db, states=states, fallback_minimal=True)
        await db.commit()
    await write_engine.dispose()
    print(f"DONE — zip_code {n}행")


if __name__ == "__main__":
    asyncio.run(main())
