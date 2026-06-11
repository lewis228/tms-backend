# src/service_area/scope.py
"""영업권역 선언 → zip 마스터 검색 조건 변환.

zip_code 라우터가 scope=true 검색 시 사용. 선언이 하나도 없으면 빈 리스트를
반환하고 호출부는 무필터(전체)로 동작한다 — "권역 기능을 안 쓰는 팀" 과 동일.
해석/정산 경로는 이 모듈을 사용하지 않는다(입력 편의 필터 전용).
"""
from __future__ import annotations
from typing import List

from sqlalchemy import and_, func

from zip_code.model import ZipCodeModel
from service_area.model import ServiceAreaModel
from service_area.const.status import ServiceAreaKind


def zip_scope_conditions(selections: List[ServiceAreaModel]) -> list:
    """선언 목록 → ZipCodeModel OR 조건 리스트 (비면 무필터)."""
    conds = []
    for s in selections:
        if s.kind == ServiceAreaKind.STATE:
            conds.append(ZipCodeModel.state == s.state)
        elif s.kind == ServiceAreaKind.COUNTY:
            conds.append(and_(
                ZipCodeModel.state == s.state,
                func.lower(ZipCodeModel.county) == s.value.lower(),
            ))
        elif s.kind == ServiceAreaKind.CITY:
            conds.append(and_(
                ZipCodeModel.state == s.state,
                func.lower(ZipCodeModel.city) == s.value.lower(),
            ))
        elif s.kind == ServiceAreaKind.ZIP3:
            # state 도 AND — 다른 kind 와 일관 + prefix 를 잘못된 주로 선언해도 누출 방지
            conds.append(and_(
                ZipCodeModel.state == s.state,
                ZipCodeModel.zip.like(f"{s.value}%"),
            ))
    return conds
