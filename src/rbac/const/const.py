# rbac/const/const.py
# ────────────────────────────────────────────────
# RBAC 권한 코드 정의 (TMS) — 단일 소스
#
# team 스코프. SUPER_ADMIN 은 permission_guard 에서 자동 통과.
# team 의 admin_group 도 자동 통과 (rbac.permission_groups.is_admin_group=True).
# 그 외 team 멤버는 permission_group → 권한 코드 집합으로 게이트됨.
# ────────────────────────────────────────────────

# ===== Master Data =====
CUSTOMER_WRITE   = "CUSTOMER_WRITE"    # 고객사 등록/수정/삭제
TERMINAL_WRITE   = "TERMINAL_WRITE"    # 터미널 등록/수정/삭제
VESSEL_WRITE     = "VESSEL_WRITE"      # 본선 등록/수정/삭제
LOCATION_WRITE   = "LOCATION_WRITE"    # 야드/고객 주소 등록/수정/삭제
DRIVER_WRITE     = "DRIVER_WRITE"      # 기사 등록/수정/삭제 (User 자동 생성)
TRUCK_WRITE      = "TRUCK_WRITE"       # 트럭 자산 등록/수정/삭제
CHASSIS_WRITE        = "CHASSIS_WRITE"        # 챠시 자산 등록/수정/삭제
EQUIPMENT_POOL_WRITE = "EQUIPMENT_POOL_WRITE" # 챠시 풀 마스터

# ===== Delivery Order / Leg =====
DO_WRITE         = "DO_WRITE"          # D/O 생성/수정/삭제
DO_TRANSITION    = "DO_TRANSITION"     # D/O 상태 전이 (PLANNING → DISPATCHED 등)
LEG_WRITE        = "LEG_WRITE"         # Leg 생성/수정/삭제
LEG_TRANSITION   = "LEG_TRANSITION"    # Leg 상태 전이 (PENDING → IN_TRANSIT 등)
CHASSIS_EVENT_WRITE  = "CHASSIS_EVENT_WRITE"  # 챠시 이벤트 로그
STREET_TURN_WRITE = "STREET_TURN_WRITE" # Street turn 생성/취소
STREET_TURN_APPROVE = "STREET_TURN_APPROVE" # Street turn 승인/거절 (선사 통신)
LOAD_TYPE_TEMPLATE_WRITE = "LOAD_TYPE_TEMPLATE_WRITE"  # Load Type 템플릿 등록/수정/삭제 (재설계)

# ===== Settlement / Rate =====
SETTLEMENT_WRITE      = "SETTLEMENT_WRITE"       # 등록/수정/삭제 (lifecycle 외)
SETTLEMENT_CALCULATE  = "SETTLEMENT_CALCULATE"   # 계산
SETTLEMENT_ADJUST     = "SETTLEMENT_ADJUST"      # 조정 (사유 필수)
SETTLEMENT_APPROVE    = "SETTLEMENT_APPROVE"     # 승인 (잠금)
SETTLEMENT_UNAPPROVE  = "SETTLEMENT_UNAPPROVE"   # 승인 취소 (사유 필수, 감사 로그)
RATE_SETTING_WRITE    = "RATE_SETTING_WRITE"     # 요율 등록/수정 (rate_setting alias)
RATE_WRITE            = "RATE_WRITE"             # 요율 등록/수정 (legacy alias)
RATE_ZONE_WRITE       = "RATE_ZONE_WRITE"        # 요율표 Zone(+zip/city 멤버) 등록/수정/삭제 (재설계)
RATE_SHEET_WRITE      = "RATE_SHEET_WRITE"       # 요율표 슬롯/셀(유효일자 버전) 등록/수정/삭제 (재설계)
ADDON_WRITE           = "ADDON_WRITE"            # 부가요금(addon) 타입 마스터 등록/수정/삭제
RATE_GROUP_WRITE      = "RATE_GROUP_WRITE"       # 정산/요율 그룹 등록/수정/삭제 (재설계)
DRIVER_RATE_WRITE     = "DRIVER_RATE_WRITE"      # 드라이버↔요율그룹 배정 등록/수정/삭제 (재설계)
INVOICE_WRITE         = "INVOICE_WRITE"          # 고객 인보이스 생성/라인 수정/삭제 (재설계 2c)
INVOICE_ISSUE         = "INVOICE_ISSUE"          # 인보이스 발행/수금/취소 (lifecycle, 재설계 2c)

# ===== Notification =====
NOTIFICATION_WRITE    = "NOTIFICATION_WRITE"     # 알림 mark_read 등 본인 inbox 액션

# ===== Analytics =====
ANALYTICS_DASH_VIEW   = "ANALYTICS_DASH_VIEW"    # 대시보드 조회

# ===== Team / Members (관리자 전용 - 커스텀 권한 UI에 노출하지 않음) =====
TEAM_RENAME                   = "TEAM_RENAME"                   # team 이름/설정 변경
TEAM_DELETE                   = "TEAM_DELETE"                   # team 삭제 (purge)
TEAM_MEMBER_INVITE            = "TEAM_MEMBER_INVITE"            # 멤버 초대
TEAM_MEMBER_REMOVE            = "TEAM_MEMBER_REMOVE"            # 멤버 제거
TEAM_MEMBER_ROLE_WRITE        = "TEAM_MEMBER_ROLE_WRITE"        # 멤버 역할 변경
TEAM_MEMBER_PERMISSION_ASSIGN = "TEAM_MEMBER_PERMISSION_ASSIGN" # 권한 그룹 지정

# ===== API Keys (관리자 전용 - 발급/회수) =====
API_KEY_WRITE                   = "API_KEY_WRITE"                   # API 키 발급/수정/회수


def _unique(seq: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


ALL_PERMISSION_CODES = _unique([
    # Master Data
    CUSTOMER_WRITE, TERMINAL_WRITE, VESSEL_WRITE, LOCATION_WRITE, DRIVER_WRITE,
    TRUCK_WRITE, CHASSIS_WRITE, EQUIPMENT_POOL_WRITE,
    # D/O / Leg / StreetTurn
    DO_WRITE, DO_TRANSITION, LEG_WRITE, LEG_TRANSITION,
    CHASSIS_EVENT_WRITE, STREET_TURN_WRITE, STREET_TURN_APPROVE,
    LOAD_TYPE_TEMPLATE_WRITE,
    # Settlement / Rate
    SETTLEMENT_WRITE, SETTLEMENT_CALCULATE, SETTLEMENT_ADJUST, SETTLEMENT_APPROVE,
    SETTLEMENT_UNAPPROVE, RATE_SETTING_WRITE, RATE_WRITE,
    RATE_ZONE_WRITE,
    RATE_SHEET_WRITE, RATE_GROUP_WRITE, DRIVER_RATE_WRITE, ADDON_WRITE,
    INVOICE_WRITE, INVOICE_ISSUE,
    # Notification
    NOTIFICATION_WRITE,
    # Analytics
    ANALYTICS_DASH_VIEW,
    # Team / Members
    TEAM_RENAME, TEAM_DELETE,
    TEAM_MEMBER_INVITE, TEAM_MEMBER_REMOVE,
    TEAM_MEMBER_ROLE_WRITE, TEAM_MEMBER_PERMISSION_ASSIGN,
    # API Keys
    API_KEY_WRITE,
])


# ── 시스템 그룹별 기본 권한 세트 (team 생성 시 자동 시드) ─────────
DEFAULT_ADMIN_CODES = ALL_PERMISSION_CODES[:]  # 관리자: 전체

DEFAULT_MEMBER_CODES = [
    # Master Data — 운영자가 등록/수정
    CUSTOMER_WRITE, TERMINAL_WRITE, VESSEL_WRITE, LOCATION_WRITE, DRIVER_WRITE,
    TRUCK_WRITE, CHASSIS_WRITE, EQUIPMENT_POOL_WRITE,
    # D/O / Leg — 일상 운영
    DO_WRITE, DO_TRANSITION, LEG_WRITE, LEG_TRANSITION,
    CHASSIS_EVENT_WRITE, STREET_TURN_WRITE, STREET_TURN_APPROVE,
    # Settlement — 계산/조정만 (승인/취소는 ADMIN)
    SETTLEMENT_CALCULATE, SETTLEMENT_ADJUST,
    # Invoice — 작성/라인편집 (발행/수금/취소는 ADMIN)
    INVOICE_WRITE,
    # Notification
    NOTIFICATION_WRITE,
    # Analytics
    ANALYTICS_DASH_VIEW,
]

DEFAULT_VIEWER_CODES = [
    # 뷰어: 대시보드만
    ANALYTICS_DASH_VIEW,
]


# ── system_key → 기본 권한 매핑 (team 생성 시 사용) ─────────────
GROUP_DEFAULTS_BY_SYSTEM_KEY = {
    "ADMIN":  DEFAULT_ADMIN_CODES,
    "MEMBER": DEFAULT_MEMBER_CODES,
    "VIEWER": DEFAULT_VIEWER_CODES,
}


# ── 커스텀 그룹에 자동 포함되는 코드 (뷰어 제외) ──────────────────
# 사용자가 정의하는 그룹에도 무조건 들어가는 안전한 권한 (대시보드 조회 등)
IMPLICIT_NON_VIEWER_CODES = [
    ANALYTICS_DASH_VIEW,
]


# ── 커스텀 권한 UI 노출 가능한 코드 ───────────────────────────────
# team 의 admin 이 그룹 만들 때 토글로 선택 가능한 코드 화이트리스트.
# TEAM_* 같은 시스템 권한은 admin_group 만 가능 (UI 에 노출 X).
CUSTOMIZABLE_CODES = [
    # Master Data
    CUSTOMER_WRITE, TERMINAL_WRITE, VESSEL_WRITE, LOCATION_WRITE, DRIVER_WRITE,
    # D/O / Leg
    DO_WRITE, DO_TRANSITION, LEG_WRITE, LEG_TRANSITION,
    CHASSIS_EVENT_WRITE, STREET_TURN_WRITE, STREET_TURN_APPROVE,
    # Settlement
    SETTLEMENT_CALCULATE, SETTLEMENT_ADJUST,
    SETTLEMENT_APPROVE, SETTLEMENT_UNAPPROVE,
    # Rate
    RATE_WRITE, RATE_ZONE_WRITE, RATE_SHEET_WRITE,
    RATE_GROUP_WRITE, DRIVER_RATE_WRITE, ADDON_WRITE,
    # Invoice
    INVOICE_WRITE, INVOICE_ISSUE,
]
