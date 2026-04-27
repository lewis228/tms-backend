from __future__ import annotations
from enum import StrEnum

class FileDomain(StrEnum):
    """
    파일이 속할 수 있는 도메인 Enum
    - Python 3.11 이상: StrEnum을 사용해 문자열 변환 자동 처리.
    - DB에는 SQLAlchemy SAEnum(FileDomain)으로 반영됨.
    - f"{FileDomain.PRODUCT}" → "product" 로 자연스럽게 문자열화됨.
    """

    USER = "user"           # 사용자 프로필/첨부
    PRODUCT = "product"     # 상품 이미지/첨부
    PARTNER = "partner"     # 거래처 첨부
    PURCHASE = "purchase"   # 발주서 첨부
    SALES = "sales"         # 판매서 첨부

    # 트랜잭션 메모 첨부파일
    TRANSACTION_TEMP = "transaction_temp"  # 임시저장 첨부
    INBOUND = "inbound"                    # 입고 첨부
    OUTBOUND = "outbound"                  # 출고 첨부
    TRANSFER = "transfer"                  # 이동 첨부
    ADJUST = "adjust"                      # 조정 첨부
    RETURN_INBOUND = "return_inbound"      # 반품입고 첨부
    TEAM = "team"                          # 팀 이미지
    # TMS Phase F — 운송 도메인
    LEG_DOCUMENT = "leg_document"          # 기사 모바일 leg 첨부 (POD/Receipt)

    @classmethod
    def values(cls) -> list[str]:
        """['user', 'product', ...] 형태로 Enum 값만 반환"""
        return [v.value for v in cls]
