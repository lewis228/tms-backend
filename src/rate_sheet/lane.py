# src/rate_sheet/lane.py
"""양방향 구간(lane) 정규화 — 셀 = 무순서 쌍.

확정 설계(컨플루언스 v12): 요율 셀은 방향이 없다(↔). zip1↔zip2 한 줄이
양쪽 방향 운행을 모두 커버하고, 방향 차이(수입/수출)는 Move/Service 조합이 흡수한다.

구현: 셀 양측 좌표를 토큰화해 사전순으로 작은 쪽을 from-측에 고정한다.
같은 구간을 어느 방향으로 입력/조회해도 항상 같은 정규형이 되므로
DB 에는 한 형태만 존재(이중 입력 원천 차단)하고, 조회도 단일 lookup 으로 끝난다.
저장(versioning.set_rate 진입 전)과 해석(resolver 후보 생성) 양쪽에서 반드시 통과시킨다.
"""
from __future__ import annotations


def _side_token(zip_: str | None, zone_id: int | None, city: str | None, state: str | None) -> str:
    """한쪽 좌표(zip|zone|city 중 1개)를 비교 가능한 토큰으로."""
    if zip_ is not None:
        return f"zip:{zip_}"
    if zone_id is not None:
        return f"zone:{zone_id:012d}"  # 숫자 패딩 — 자릿수 무관 결정적 순서
    if city is not None:
        return f"city:{(state or '').upper()}/{city.lower()}"
    return ""  # 빈 좌표 (MILE/HOURLY 단일 셀)


def normalize_cell(cell: dict) -> dict:
    """무순서 쌍 정규화 — from-측 토큰이 to-측보다 크면 양측 좌표를 통째로 스왑."""
    f = _side_token(cell.get("from_zip"), cell.get("from_zone_id"),
                    cell.get("from_city"), cell.get("from_state"))
    t = _side_token(cell.get("to_zip"), cell.get("to_zone_id"),
                    cell.get("to_city"), cell.get("to_state"))
    if f <= t:
        return dict(cell)
    out = dict(cell)
    out["from_zip"], out["to_zip"] = cell.get("to_zip"), cell.get("from_zip")
    out["from_zone_id"], out["to_zone_id"] = cell.get("to_zone_id"), cell.get("from_zone_id")
    out["from_city"], out["to_city"] = cell.get("to_city"), cell.get("from_city")
    out["from_state"], out["to_state"] = cell.get("to_state"), cell.get("from_state")
    return out
