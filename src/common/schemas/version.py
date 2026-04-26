# src/common/schemas/version.py
"""
버전 조회용 공통 스키마

히스토리 상세 페이지의 버전 드롭다운 (Ver.1, Ver.2, Ver.3...)에서 사용
- 체인 내 모든 이벤트 목록 조회
- 각 이벤트의 버전 번호, 이벤트 종류, 생성일시, 작성자 정보 포함
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from common.schemas.base import ResponseSchema
from common.schemas.nested import UserNestedWithFilesSchema


class VersionInfoSchema(ResponseSchema):
    """
    단일 버전 정보 스키마
    
    버전 드롭다운 아이템용:
    - Ver.3: 2025-12-26 12:12 (hyeong taek jo) - CANCEL  ← 최신 (첫 번째)
    - Ver.2: 2025-12-26 12:05 (hyeong taek jo) - ADJUST
    - Ver.1: 2025-12-26 11:57 (hyeong taek jo) - ORIGINAL ← 가장 오래됨
    """
    # 헤더 ID (해당 버전 상세 조회용)
    id: int
    
    # 버전 번호 (1, 2, 3...)
    # 체인 내 created_at 순서로 자동 계산
    # 가장 오래된 것이 1, 최신이 total
    version_number: int
    
    # 이벤트 종류 (ORIGINAL, ADJUST, CANCEL)
    event_kind: str
    
    # 생성일시
    created_at: datetime
    
    # 작성자 정보 (프로필 이미지 포함)
    created_by: Optional[UserNestedWithFilesSchema] = None
    
    # 현재 버전 여부 (가장 최신 버전)
    is_current: bool = False


class ChainVersionsResponseSchema(ResponseSchema):
    """
    체인 버전 목록 응답 스키마
    
    GET /{domain}/{originalId}/versions 응답용
    예: GET /inbound/1/versions
    
    응답 예시:
    {
        "original_id": 1,
        "total_versions": 3,
        "current_version": 3,
        "is_deleted": true,
        "versions": [
            {"id": 3, "version_number": 3, "event_kind": "CANCEL", "is_current": true, ...},  ← 최신 (첫 번째)
            {"id": 2, "version_number": 2, "event_kind": "ADJUST", ...},
            {"id": 1, "version_number": 1, "event_kind": "ORIGINAL", ...}  ← 가장 오래됨
        ]
    }
    """
    # ORIGINAL 헤더 ID
    original_id: int
    
    # 전체 버전 수
    total_versions: int
    
    # 현재(최신) 버전 번호
    current_version: int
    
    # 삭제(취소) 여부 (첫 번째(최신) 이벤트가 CANCEL인 경우)
    is_deleted: bool
    
    # 변경: 버전 목록 (created_at 내림차순, 최신이 먼저)
    versions: List[VersionInfoSchema]