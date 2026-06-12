# src/rate_zone/const/status.py
from __future__ import annotations
from enum import StrEnum


class ZoneKind(StrEnum):
    """존 종류 — 멤버 원자 타입과 사용 가능한 정산 방식을 결정.

    ZIP  : 멤버 = zip 만. ZIP 방식 그룹의 셀 좌표로 사용.
           '도시로 추가'는 그 도시의 zip 전부를 멤버로 넣는 확장 단축키일 뿐.
    CITY : 멤버 = (city, state) 만. CITY 방식 그룹 전용 도시존.
    한 존에 zip 과 도시를 섞을 수 없다 (혼합되면 CITY 방식의 존재 의미가 없음 — 사용자 확정).
    """
    ZIP = "ZIP"
    CITY = "CITY"
