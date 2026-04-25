"""선사별 raw 문자열 → 정규화 Enum 값 매핑.

여러 선사 스크래퍼가 돌려주는 자유 문자열 (40' DH / 40HC / Empty returned /
gate out 등) 을 fuzzy matching 으로 Enum 값에 매핑한다.

설계 원칙:
    1. **Lossy OK — raw 는 따로 보존됨.** 매칭 실패 시 None/UNKNOWN 반환하고,
       raw 원문은 호출부가 기존 컬럼(`size_type`, `status`, `event_type`)에 저장.
       나중에 Enum 을 확장하면 backfill 스크립트로 채울 수 있다.
    2. **사전 조사 + 운영 관찰 이중 보강.** 현재 12개 선사 샘플 응답을 보고
       공통 패턴을 정규식으로 박아 뒀지만, 새 선사 추가나 기존 선사 포맷 변경
       시 `*_code = None/UNKNOWN` 비율을 모니터링해 정규식을 추가한다.
    3. **순서가 중요.** 구체적 패턴 → 포괄적 패턴 순으로 검사. 예컨대 "empty
       returned" 는 "returned" 보다 먼저 매치돼야 한다.
"""

from __future__ import annotations

import re
from typing import Optional

from ocean.container.const.physical_status import ContainerPhysicalStatus
from ocean.container.const.size_type import ContainerSizeType
from ocean.container_event.const.event_type import ContainerEventType


# ─────────────────────────────────────────────────────────────
# Size type
# ─────────────────────────────────────────────────────────────
# 45 는 40 보다 먼저 체크 (45 는 40 정규식에도 매칭될 수 있음)
# word boundary 뒤에 숫자만 시작하면 되고, 뒤쪽은 ft 표기(') 나 바로 이어지는
# 타입 문자('40HC', "40' DH") 모두 허용. `\b40` 만 요구하고 뒤는 자유롭게.
_SIZE_45 = re.compile(r"\b45")
_SIZE_40 = re.compile(r"\b40")
_SIZE_20 = re.compile(r"\b20")

# 숫자 바로 뒤에 타입 약어가 붙는 표기("40HC", "20GP") 를 커버하기 위해
# word boundary 대신 좌측 경계를 완화 — 숫자 or 공백 or 문자열 시작.
# HC 는 "HIGH CUBE" / "DH" (Dry High-cube) 도 포함.
_TYPE_HC = re.compile(r"(?:^|[^A-Z])(HC|H/?C|HIGH[-\s]?CUBE|DH)(?![A-Z])", re.I)
_TYPE_RF = re.compile(r"(?:^|[^A-Z])(RF|REEFER|RH|R[-\s]?REF)(?![A-Z])", re.I)
_TYPE_OT = re.compile(r"(?:^|[^A-Z])(OT|OPEN[-\s]?TOP)(?![A-Z])", re.I)
_TYPE_FR = re.compile(r"(?:^|[^A-Z])(FR|FLAT[-\s]?RACK|PF)(?![A-Z])", re.I)
_TYPE_TK = re.compile(r"(?:^|[^A-Z])(TK|TANK|T1|T11)(?![A-Z])", re.I)
_TYPE_DS = re.compile(r"(?:^|[^A-Z])(DS|DRY|GP|STANDARD|G1|22G1|42G1)(?![A-Z])", re.I)


# ISO 6346 size/type code 4자리 표기 (22G1, 42G1, 45G1 등) 전용 선-핸들러.
# 첫 자리 = 길이 (2=20ft, 4=40ft), 둘째 자리 = 높이 (0/2=Standard, 5=HC, 9=N/A).
# 셋째/넷째 = 그룹 코드 (G=Dry, R=Reefer, U=Open top, P=Flat rack, T=Tank).
_ISO_CODE = re.compile(r"\b([2-4])([0-9])([A-Z])([0-9])\b")

_ISO_LEN_MAP = {"2": "20", "4": "40"}
_ISO_HEIGHT_HC = {"5", "9"}
_ISO_GROUP_MAP = {
    "G": "DS",  # General purpose (dry)
    "V": "DS",  # Ventilated dry
    "R": "RF",  # Reefer
    "U": "OT",  # Open top
    "P": "FR",  # Flat / Platform
    "T": "TK",  # Tank
}


def _from_iso_code(raw: str) -> Optional[str]:
    """ISO 6346 4자리 코드 (42G1, 22G1, 45R1 등) → 내부 size_type 값."""
    m = _ISO_CODE.search(raw)
    if not m:
        return None
    length_digit, height_digit, group, _ = m.groups()
    size = _ISO_LEN_MAP.get(length_digit)
    if size == "40" and height_digit == "5":
        size = "40"  # 길이만 40, 높이 HC
    if length_digit == "4" and height_digit in _ISO_HEIGHT_HC:
        # 45ft 는 드물어서 별도 — 45ft 는 length=4, height=9 대신 45HC 로 나오는 게 보통
        pass
    group_t = _ISO_GROUP_MAP.get(group)
    if group_t is None:
        return None
    # 높이 HC 이면 DS → HC, RF → HR 로 승격
    if height_digit in _ISO_HEIGHT_HC:
        if group_t == "DS":
            group_t = "HC"
        elif group_t == "RF":
            group_t = "HR"
    return f"{size}{group_t}"


def normalize_size_type(raw: Optional[str]) -> Optional[str]:
    """raw 컨테이너 사양 문자열 → ContainerSizeType 값.

    매칭 실패 시 None 반환. 호출부는 raw 를 `size_type` 에 그대로 저장하고
    이 함수 결과를 `size_type_code` 컬럼에 저장한다.

    Examples:
        "40' DH"             → "40HC"
        "40HC"               → "40HC"
        "40 DRY HIGH CUBE"   → "40HC"
        "40HR"               → "40HR"   (High-cube Reefer)
        "40"                 → "40DS"   (타입 정보 없으면 DS 추정)
        "20'DS"              → "20DS"
        "22G1"               → "20DS"   (ISO 6346 코드)
        "42G1"               → "40DS"
        "45G1"               → "45HC"
        ""                   → None
    """
    if not raw or not raw.strip():
        return None
    s = raw.upper().strip()

    # 0) ISO 6346 4자리 코드 우선 체크
    iso_result = _from_iso_code(s)
    if iso_result is not None and iso_result in _SIZE_TYPE_VALUES_SET:
        return iso_result

    # 1) size (ft) 추출 — 45 먼저
    if _SIZE_45.search(s):
        size = "45"
    elif _SIZE_40.search(s):
        size = "40"
    elif _SIZE_20.search(s):
        size = "20"
    else:
        return None

    # 2) type 추출 — 구체 패턴 우선. HR 은 HC+RF 조합이라 특수.
    if re.search(r"(?:^|[^A-Z])HR(?![A-Z])", s):
        t = "HR"
    elif _TYPE_HC.search(s):
        t = "HC"
    elif _TYPE_RF.search(s):
        t = "RF"
    elif _TYPE_OT.search(s):
        t = "OT"
    elif _TYPE_FR.search(s):
        t = "FR"
    elif _TYPE_TK.search(s):
        t = "TK"
    elif _TYPE_DS.search(s):
        t = "DS"
    else:
        t = "HC" if size == "45" else "DS"

    candidate = f"{size}{t}"
    try:
        return ContainerSizeType(candidate).value
    except ValueError:
        return None


# ContainerSizeType 의 유효 값 집합 — ISO 매핑 후 검증용
_SIZE_TYPE_VALUES_SET = frozenset(v.value for v in ContainerSizeType)


# ─────────────────────────────────────────────────────────────
# Physical status
# ─────────────────────────────────────────────────────────────
_ST_EMPTY_RETURNED = re.compile(
    r"empty[-\s]?(returned|in|back|delivered|dehired|drop[-\s]?off)",
    re.I,
)
_ST_GATE_OUT = re.compile(
    r"gate[-\s]?out|pick[-\s]?up|dispatched|departed[-\s]?terminal|out[-\s]?gate|delivered[-\s]?to[-\s]?consignee",
    re.I,
)
_ST_DISCHARGED = re.compile(
    r"discharg|unload|vessel[-\s]?arriv|arriv(ed)?[-\s]?at[-\s]?port|landed|on[-\s]?shore",
    re.I,
)
_ST_ON_SHIP = re.compile(
    r"vessel[-\s]?(departed|sailed|underway)|on[-\s]?board|in[-\s]?transit|on[-\s]?vessel|at[-\s]?sea",
    re.I,
)
_ST_LOADED = re.compile(r"\bloaded\b|\bladen\b|loading[-\s]?complete", re.I)
_ST_GATE_IN = re.compile(
    r"gate[-\s]?in|received|empty[-\s]?(out|dispatch|released)|container[-\s]?at[-\s]?terminal",
    re.I,
)


def normalize_physical_status(raw: Optional[str]) -> Optional[str]:
    """raw 이벤트 description → ContainerPhysicalStatus 값.

    매칭 실패 시 UNKNOWN 반환 (None 이 아님 — 이 축은 항상 값이 있어야 탭
    분류가 깔끔함). 진짜 입력 자체가 없는 경우만 None.
    """
    if not raw or not raw.strip():
        return None

    s = raw.lower()

    # 순서 중요 — 구체적인 것부터. "empty returned" 가 "returned" 보다 우선.
    if _ST_EMPTY_RETURNED.search(s):
        return ContainerPhysicalStatus.EMPTY_RETURNED.value
    if _ST_GATE_OUT.search(s):
        return ContainerPhysicalStatus.GATE_OUT.value
    if _ST_DISCHARGED.search(s):
        return ContainerPhysicalStatus.DISCHARGED.value
    if _ST_ON_SHIP.search(s):
        return ContainerPhysicalStatus.ON_SHIP.value
    if _ST_LOADED.search(s):
        return ContainerPhysicalStatus.LOADED.value
    if _ST_GATE_IN.search(s):
        return ContainerPhysicalStatus.GATE_IN.value
    return ContainerPhysicalStatus.UNKNOWN.value


# ─────────────────────────────────────────────────────────────
# Event type — physical_status 와 매핑 대부분 겹치나, 선박 이벤트 / T/S 가 추가
# ─────────────────────────────────────────────────────────────
_ET_VESSEL_DEPARTED = re.compile(r"vessel[-\s]?(departed|sailed)", re.I)
_ET_VESSEL_ARRIVED = re.compile(r"vessel[-\s]?arriv", re.I)
_ET_TRANSSHIPMENT = re.compile(r"transshipment|\bt/?s\b|transfer[-\s]?to", re.I)


def normalize_event_type(raw: Optional[str]) -> Optional[str]:
    """raw event description → ContainerEventType 값.

    선박 이벤트(VESSEL_DEPARTED / VESSEL_ARRIVED / TRANSSHIPMENT) 는 먼저
    특수 처리. 나머지는 physical_status 매핑을 재사용해 같은 분류 체계를
    공유한다 (physical_status 대부분 값이 EventType 과 동명 — EMPTY_RETURNED /
    GATE_OUT / DISCHARGED / LOADED / GATE_IN).
    """
    if not raw or not raw.strip():
        return None

    s = raw.lower()

    if _ET_VESSEL_DEPARTED.search(s):
        return ContainerEventType.VESSEL_DEPARTED.value
    if _ET_VESSEL_ARRIVED.search(s):
        return ContainerEventType.VESSEL_ARRIVED.value
    if _ET_TRANSSHIPMENT.search(s):
        return ContainerEventType.TRANSSHIPMENT.value

    # physical_status 매핑 재사용
    status = normalize_physical_status(raw)
    if status is None:
        return None
    try:
        return ContainerEventType(status).value
    except ValueError:
        return ContainerEventType.UNKNOWN.value
