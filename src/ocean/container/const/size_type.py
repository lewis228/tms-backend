"""컨테이너 사양(사이즈 + 타입) 정규화 Enum.

스크래퍼마다 선사 응답을 `"40' DH"` / `"40HC"` / `"40 HIGH CUBE"` 등 서로
다른 raw 문자열로 돌려주기 때문에, 집계 / 필터 / 프론트 탭 분류가 불가능하다.
`normalizer.normalize_size_type` 이 raw 를 이 Enum 값으로 해석해서 저장하고,
raw 원문은 `ocean_containers.size_type` 컬럼에 그대로 보존된다.

값 포맷: `{size_ft}{type_code}` — 두 자리 정수 + 두 자리 타입 약어.
근거: ISO 6346 size/type code 의 "의미 해석된 단축형". 실제 ISO 4-char
코드(22G1 / 45G1 등) 는 선사가 잘 안 내려주므로 가독성 위주로 재정의.

새 값 추가 절차:
    1. 이 Enum 에 상수 추가
    2. `normalizer.py` 의 SIZE / TYPE 정규식에 패턴 반영
    3. migration 불필요 (컬럼은 String) — 운영 반영 즉시 적용됨
"""

from enum import StrEnum


class ContainerSizeType(StrEnum):
    # 20ft
    TWENTY_DS = "20DS"      # 20' Dry Standard (GP / G1 / Standard)
    TWENTY_DH = "20DH"      # 20' Dry High-cube (드물게 존재)
    TWENTY_RF = "20RF"      # 20' Reefer (냉장)
    TWENTY_OT = "20OT"      # 20' Open Top
    TWENTY_FR = "20FR"      # 20' Flat Rack
    TWENTY_TK = "20TK"      # 20' Tank

    # 40ft
    FORTY_DS = "40DS"       # 40' Dry Standard
    FORTY_HC = "40HC"       # 40' High Cube (= DH 표기도 여기로)
    FORTY_RF = "40RF"       # 40' Reefer
    FORTY_HR = "40HR"       # 40' High-cube Reefer
    FORTY_OT = "40OT"       # 40' Open Top
    FORTY_FR = "40FR"       # 40' Flat Rack

    # 45ft — 대부분 High Cube
    FORTY_FIVE_HC = "45HC"
