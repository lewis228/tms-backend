# scripts/notion_design/content.py
"""TMS 시스템 로직 설명서 — Notion 페이지 본문 빌더.

원칙(사용자 요구):
- 테이블 나열 금지. 흐름을 "이야기"처럼, 구체적인 숫자 예시 + ASCII 박스 다이어그램으로.
- 코드에 있는 모든 로직을 빠짐없이. 현재 코드 기준. 미구현/개선은 솔직히 별도 챕터.
다이어그램은 mermaid 가 아니라 '정렬된 ASCII 박스'(plain text 코드블록)로 그린다 — 어디서나 보기 쉽게.
"""
from __future__ import annotations

import notion_api as N


# ── ASCII 다이어그램 도구 (한글 폭 2칸 보정으로 박스 정렬) ─────
def _w(s: str) -> int:
    t = 0
    for c in s:
        o = ord(c)
        wide = (
            0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F
            or 0x3000 <= o <= 0x303F or 0x4E00 <= o <= 0x9FFF or 0xFF00 <= o <= 0xFF60
            or o in (0x25BC, 0x25B6, 0x25C0, 0x2B05)  # ▼ ▶ ◀ ⬅ (ambiguous→2)
        )
        t += 2 if wide else 1
    return t


def box(*lines: str) -> list[str]:
    w = max(_w(l) for l in lines)
    top = "┌" + "─" * (w + 2) + "┐"
    bot = "└" + "─" * (w + 2) + "┘"
    mid = ["│ " + l + " " * (w - _w(l)) + " │" for l in lines]
    return [top, *mid, bot]


def vstack(boxes: list[list[str]]) -> list[str]:
    """박스들을 세로로 잇는다(가운데 │/▼ 커넥터)."""
    out: list[str] = []
    for i, b in enumerate(boxes):
        out += b
        if i < len(boxes) - 1:
            c = len(b[0]) // 2
            out.append(" " * c + "│")
            out.append(" " * c + "▼")
    return out


def dia(lines) -> dict:
    """ASCII 다이어그램을 plain text 코드블록으로."""
    text = lines if isinstance(lines, str) else "\n".join(lines)
    return N.code(text.strip("\n"), language="text")


def ex(text: str):
    return N.code(text.strip("\n"), language="text")


def lead(text: str):
    return N.callout(text, emoji="📘", color="blue_background")


def tip(text: str):
    return N.callout(text, emoji="💡", color="gray_background")


def warn(text: str):
    return N.callout(text, emoji="⚠️", color="yellow_background")


def gap(text: str):
    return N.callout(text, emoji="🛠️", color="orange_background")


# ════════════════════════════════════════════════════════════
# 부모 페이지 본문 (Overview)
# ════════════════════════════════════════════════════════════
def page_overview():
    flow = vstack([
        box("(1) 운송 의뢰 D/O 입력", "수기 또는 AI 사진"),
        box("(2) 컨테이너 + 정차점(Stop)"),
        box("(3) Leg(구간) 자동 생성", "load_type_template"),
        box("(4) 기사 배차 assign_driver"),
        box("(5) 운행 — 모바일 체크포인트"),
        box("(6) Leg COMPLETED"),
    ])
    flow += [
        "        │",
        "        ├──▶ 정산 payroll : leg 단위로 기사에게 지급",
        "        │",
        "        └──▶ 청구 invoice : 고객에게 원가 + 마진",
        "                ( 정산·청구 둘 다 같은 요율엔진 사용 )",
    ]
    return [
        N.callout(
            "이 문서는 TMS 백엔드(backend_tms-api)에 실제로 구현된 로직을 "
            "'한 컨테이너가 들어와서 → 운송되고 → 기사에게 정산되고 → 고객에게 청구되기까지'의 "
            "이야기로 풀어 쓴 설명서입니다. 표 나열이 아니라 흐름·예시·다이어그램 중심입니다.",
            emoji="🚚", color="blue_background",
        ),
        N.h2("한 문장 요약"),
        N.p("TMS 는 컨테이너 운송 회사를 위한 시스템입니다. 디스패처가 운송 의뢰(D/O)를 넣으면, "
            "시스템이 그 안의 컨테이너를 어떻게 옮길지 'leg(구간)'로 쪼개고, 각 leg 에 기사를 배차하고, "
            "기사가 모바일 앱으로 운행을 보고하면 상태가 자동으로 흐르고, 완료된 leg 는 요율표에 따라 "
            "기사에게 정산되고 고객에게는 원가+마진으로 청구됩니다."),
        N.h2("전체 흐름 한눈에"),
        dia(flow),
        N.h2("이 문서를 읽는 순서"),
        N.numbered("01. 시스템 개요 & 멀티테넌시 & 공통 규약 — 모든 도메인이 공유하는 토대"),
        N.numbered("02. 마스터 데이터 — 고객·터미널·기사·트럭 등 '재료'"),
        N.numbered("03~07. 실행 단계 — D/O 입력 → 컨테이너 → Leg → 배차 → 운행"),
        N.numbered("08. 요율 — 얼마를 줄지 정하는 4가지 방식"),
        N.numbered("09~10. 정산(기사 지급) & 청구(고객 인보이스 + 마진)"),
        N.numbered("11~13. 실시간·알림·감사·분석 / 모바일 BFF / 인증·권한·API·파일"),
        N.numbered("14. 상태 머신 한눈에 (모든 다이어그램 모음)"),
        N.numbered("15. 개선 제안 — 지금 코드에서 더 채우면 좋은 것"),
        tip("아래 하위 페이지들을 위에서부터 차례로 읽으면 시스템 전체가 하나의 이야기로 이어집니다."),
    ]


# ════════════════════════════════════════════════════════════
# 01. 시스템 개요 & 멀티테넌시 & 공통 규약
# ════════════════════════════════════════════════════════════
def page_architecture():
    pipe = vstack([
        box("HTTP 요청  (Authorization: Bearer JWT)"),
        box("AuthMiddleware  —  JWT 디코드"),
        box("access_token  —  토큰 종류 검증"),
        box("permission_guard  —  RBAC 코드 검사"),
        box("get_team_scope  —  X-Team-Id 멤버십 검증"),
        box("Service(db, team_id)"),
        box("Repository._require_team()", "WHERE team_id = ?  ← 모든 쿼리 첫 조건"),
        box("MySQL"),
    ])
    return [
        lead("모든 도메인이 똑같이 따르는 토대입니다. 여기를 알면 나머지 챕터가 쉬워집니다."),
        N.h2("팀(Team)이 모든 것의 뿌리"),
        N.p("TMS 는 여러 운송사가 한 시스템을 나눠 쓰는 멀티테넌시 구조입니다. "
            "User·Team·권한 카탈로그·파일을 빼면 거의 모든 데이터(D/O·컨테이너·leg·기사·트럭·요율·정산…)는 "
            "team_id 를 갖습니다. 팀이 지워지면 그 팀의 데이터는 DB 레벨에서 통째로(CASCADE) 사라집니다."),
        N.p("다른 팀 데이터가 새지 않도록 3겹으로 막습니다:"),
        N.numbered("DB 계층 — team_id FK(ondelete=CASCADE) + 같은 도메인 내부 라인은 복합 FK (team_id, parent_id) + UniqueConstraint(team_id, id)."),
        N.numbered("ORM 계층 — 모든 relationship 의 primaryjoin 에 foreign(X.team_id)==Y.team_id 를 포함."),
        N.numbered("앱 계층 — Repository 의 모든 쿼리 첫 조건이 Model.team_id == _require_team(), Router 는 get_team_scope 로 X-Team-Id 멤버십 검증."),
        N.h2("요청 한 건이 흐르는 길"),
        dia(pipe),
        tip("드라이버는 한 팀에 1:1이라 JWT 클레임에 team_id 가 들어 있어 DB 조회 없이 빠르게 스코프가 잡힙니다. "
            "그 외 사용자는 X-Team-Id 헤더 + (Redis 캐시된) user_teams 멤버십으로 검증합니다."),
        N.h2("삭제는 '지우지 않고 끈다' (soft delete)"),
        N.p("모든 비즈니스 데이터 삭제는 물리 삭제가 아니라 is_active=False 입니다. 언제 지워졌는지는 updated_at 이 말해줍니다. "
            "물리 삭제는 오직 팀/부모가 지워질 때 DB의 FK CASCADE 가 자동으로 처리합니다. "
            "단, 이벤트성 로그(chassis_event, location_ping, audit_log)는 append-only — 아예 삭제가 없습니다."),
        N.p("삭제 API 도 특이합니다. 204(내용 없음)가 아니라 200 + 꺼진 엔티티를 그대로 돌려줍니다. "
            "프론트가 추가 조회 없이 캐시를 바로 갱신할 수 있게 하기 위함입니다."),
        N.h2("목록은 커서 페이지네이션"),
        N.p("offset/limit 방식이 아니라 커서 기반입니다. 응답 meta 에 다음 페이지 커서와 next URL 이 들어오고, "
            "where__<필드>__<연산자>(equal/i_like/more_than/in/between…)과 order__<필드> 로 필터·정렬합니다. "
            "실시간으로 맨 앞에 데이터가 추가돼도 페이지가 밀리지 않습니다."),
        N.h2("실시간 동기화 규약 (id-only + /sync)"),
        N.p("어떤 데이터가 바뀌면 서비스가 WebSocket 으로 '무엇이 바뀌었다'만(id만) 쏩니다. "
            "클라이언트는 그 id로 다시 GET 해서 캐시를 갱신합니다. 페이로드를 가볍게 유지하는 설계입니다."),
        ex("""
WS 이벤트 페이로드 예
{
  "type": "delivery_order.created",
  "team_id": 1,
  "timestamp": "2026-06-10T10:00:00Z",
  "payload": { "id": 123, "team_id": 1 }   ← id만
}
"""),
        N.p("연결이 끊겼다 붙으면 놓친 변경은 GET /<도메인>/sync?since=<시각> 으로 따라잡습니다. "
            "created/updated/deleted 를 같은 모양의 events 배열로 돌려줍니다."),
        N.h2("상태 전이는 한 곳에서만"),
        N.p("상태가 있는 도메인(D/O·leg·payroll·invoice·street_turn)은 임의로 status 를 UPDATE 하지 않습니다. "
            "반드시 state_machine 의 assert_can_transition(허용표) 또는 서비스의 단일 전이 함수를 통과해야 합니다. "
            "관리자 강제(force=True)만 예외입니다."),
        tip("정리: 팀 스코프 + soft delete + 커서 페이징 + id-only 실시간 + 상태머신 — 이 5가지가 모든 도메인에 깔린 공통 토대입니다."),
    ]


# ════════════════════════════════════════════════════════════
# 02. 마스터 데이터
# ════════════════════════════════════════════════════════════
def page_master():
    fk = """
[ 마스터 ]                         [ 트랜잭션 ]

 customer ──RESTRICT (사용중이면 삭제거부)──▶ delivery_order
 terminal ──SET NULL──────────────────────▶ delivery_order
 vessel   ──SET NULL──────────────────────▶ delivery_order
 driver   ──SET NULL──────────────────────▶ leg
 truck    ──SET NULL──────────────────────▶ leg
 chassis  ──SET NULL──────────────────────▶ container
 location ──SET NULL──────────────────────▶ container_stop
 pool     ──SET NULL──────────────────────▶ chassis

 같은 도메인 내부 라인:  container ──CASCADE──▶ delivery_order
"""
    return [
        lead("운송이라는 '요리'를 하기 전의 재료들입니다. 전부 팀 스코프 + soft delete 를 따르는 단순 CRUD 이고, "
             "상태 머신은 없습니다. 대신 트랜잭션(D/O·leg·정산)이 이들을 참조합니다."),
        N.h2("재료 목록"),
        N.bullet(("고객사(customer) ", {"bold": True}), "— 화주·운송사(carrier)·브로커·벤더. kind 로 구분. carrier 면 MC/DOT 번호·보험만료일 같은 컴플라이언스 필드를 더 가짐. 코드는 팀 내 유일."),
        N.bullet(("터미널(terminal) ", {"bold": True}), "— 항만 터미널. 위경도 보유."),
        N.bullet(("선박(vessel) ", {"bold": True}), "— IMO 번호가 자연키."),
        N.bullet(("장소(location) ", {"bold": True}), "— 야드·창고·화주 도어·픽업/하역지. 위경도가 핵심(기사 내비, 요율 지오, 지도). customer 와 연결될 수 있음."),
        N.bullet(("기사(driver) ", {"bold": True}), "— 모바일 앱 사용자. user 와 1:1(driver.user_id)로 묶임 → 폰/푸시토큰/로그인은 user 쪽. duty_status(근무/휴식) 토글, 고용형태(사내/계약/외주 carrier)."),
        N.bullet(("트럭(truck) ", {"bold": True}), "— 동력차. 번호판 팀 내 유일. 소유(회사/기사/carrier), 등록·보험·검사 만료일."),
        N.bullet(("샤시(chassis) ", {"bold": True}), "— 컨테이너 받침대. 사이즈(20/40), 소유(회사/기사/풀), 현재 위치. 상태변화는 append-only chassis_event 로 적재."),
        N.bullet(("장비풀(equipment_pool) ", {"bold": True}), "— 샤시를 모아두는 터미널/3자(TRAC 등) 풀."),
        N.bullet(("청구코드(charge_code) ", {"bold": True}), "— 청구·정산 라인에 붙는 코드 마스터(기본운임·대기·할증 등). 고객청구 여부/기사지급 여부, 단위(FLAT/HOUR/…), 카테고리, 음수허용(signed)."),
        N.h2("재료가 트랜잭션에 어떻게 묶이나 (삭제 정책)"),
        dia(fk),
        N.p("핵심 규칙: 운영에 꼭 필요한 참조(고객↔D/O)는 RESTRICT 로 보호하고, 부가정보(터미널·선박·장소)는 "
            "SET NULL 로 끊어도 D/O 자체는 살아남습니다. 같은 도메인 내부 라인(컨테이너↔D/O)만 CASCADE 입니다."),
        tip("driver 가 곧 user 라는 점이 중요합니다. 같은 사람이 사내 기사이기도, 모바일 로그인 사용자이기도 합니다. "
            "기사를 soft delete 해도 user 계정은 살아 있습니다(과거 운행·정산 보존)."),
    ]


# ════════════════════════════════════════════════════════════
# 03. 1단계 — D/O 진입
# ════════════════════════════════════════════════════════════
def page_do_intake():
    intake = """
[ 수기 ]
   디스패처 ─▶ D/O 폼 작성 (고객·컨테이너·Stop) ──┐
                                                ├─▶ POST /delivery-orders
[ AI ]                                          │
   운송장 사진 ─▶ ai_intake (Vision 추출) ─▶ 필드 ─┘
                                                │
                                                ▼
                       ┌──────────────────────────────────────┐
                       │ D/O          status     = PLANNING     │
                       │ 컨테이너      work_state = DRAFT/PLANNED │
                       │ ContainerStop (planned 만, actual 비움)  │
                       └──────────────────────────────────────┘
"""
    return [
        lead("모든 것의 시작. 누군가가 '이 컨테이너를 여기서 저기로 옮겨줘'라는 운송 의뢰(Delivery Order)를 넣습니다."),
        N.h2("D/O 는 머리(헤더) + 컨테이너들"),
        N.p("D/O 헤더에는 고객(필수)·방향(IMPORT/EXPORT, 필수)·BL/부킹번호·터미널·선박·ETA 가 들어갑니다. "
            "그 아래 컨테이너(=shipment 라인) N개가 매달립니다. 컨테이너마다 번호·사이즈·약속시간(픽업/하역/반납)·"
            "프리타임(LFD) 같은 정보가 있고, 각 컨테이너는 정차점(Stop)들을 가집니다."),
        N.h2("데이터가 들어오는 두 가지 길"),
        dia(intake),
        N.p("AI 경로는 사진을 Claude/Gemini Vision 으로 보내 BL번호·컨테이너·정차점을 뽑아 폼을 미리 채워주는 "
            "'입력 보조'입니다. 최종 저장은 사람이 확인 후 일반 D/O 생성과 같은 경로로 들어갑니다."),
        N.h2("정차점(Stop)의 4가지 역할"),
        N.bullet(("ORIGIN ", {"bold": True}), "— 첫 출발점(보통 터미널/항만)"),
        N.bullet(("DELIVERY ", {"bold": True}), "— 화물을 내리거나 싣는 화주 도어/창고 (여러 개 가능)"),
        N.bullet(("TRANSIT ", {"bold": True}), "— 중간 경유(적재 변화 없음)"),
        N.bullet(("TERMINUS ", {"bold": True}), "— 마지막 종료점(보통 빈 컨 반납 디포)"),
        N.h2("예시"),
        ex("""
디스패처가 IMPORT D/O 를 만든다 (고객 X, 컨테이너 1개 40ft)

POST /delivery-orders
{
  direction: "IMPORT", customer_id: 5, bl_number: "BL-2026-001",
  containers: [{
    container_number: "MSKU1234567", size: "40HC",
    stops: [
      { role: "ORIGIN",   location: "LA 터미널" },
      { role: "DELIVERY", location: "NYC 창고" },
      { role: "TERMINUS", location: "반납 디포" }
    ]
  }]
}

결과
  D/O   #100  status = PLANNING
  컨테이너 #50  work_state = PLANNED  (stop 들이 생겼으므로)
  ContainerStop 3개 (planned 만 있고 actual_arrival 은 비어있음)
"""),
        tip("아직 leg(운송 구간)는 없습니다. 다음 단계에서 템플릿으로 자동 생성됩니다."),
    ]


# ════════════════════════════════════════════════════════════
# 04. 2단계 — Container & Stop & work_state
# ════════════════════════════════════════════════════════════
def page_container():
    ws = """
 DRAFT ──(stop 1+)──▶ PLANNED ──(leg 출발)──▶ IN_TRANSIT ──(전부 완료 & TERMINUS 도착)──▶ COMPLETED
                         │                       ▲    │
                         │           (다시 출발)  │    └──(stop 도착 & 다음 leg PENDING)──▶ AT_STOP
                         │                       └────────────────────────────────────────┘
                         │                                          │
                         │                          (마지막 plan stop 도착 & 다음 미생성)
                         │                                          ▼
                         │                                    WAITING_PLAN  ⚠
                         │
   수동 토글:  PLANNED ◀──▶ HOLD        PLANNED ──▶ CANCELLED
"""
    return [
        lead("컨테이너는 D/O 의 '라인 아이템'이자 실제 운송 단위입니다. 컨테이너에는 사람이 보는 status 와, "
             "시스템이 leg/stop 으로부터 자동 계산하는 work_state(작업상태) 두 가지가 있습니다."),
        N.h2("work_state 8단계 — 자동으로 계산됨"),
        N.p("디스패처가 직접 만지는 건 HOLD/CANCELLED 뿐이고, 나머지는 leg 와 stop 의 현재 상태로부터 매번 다시 계산됩니다."),
        dia(ws),
        warn("WAITING_PLAN 은 '마지막으로 계획된 stop 에 도착했는데 다음 stop/leg 가 아직 안 만들어진' 경고 상태입니다. "
             "현재 코드는 다음 leg 를 자동 생성하지 않으므로 디스패처가 손으로 채워야 합니다(개선 챕터 참고)."),
        N.h2("컨테이너 이벤트(container_event)"),
        N.p("컨테이너의 생애 이정표를 append-only 로 적습니다 — 예: STREET_TURNED(스트리트턴 승인 시 자동 기록), "
            "GATE_OUT/DELIVERED/RETURNED 등. 분석(컨테이너 회전율·dwell time)이 이 이벤트를 집계합니다."),
        N.h2("예시"),
        ex("""
컨테이너 #50 의 work_state 변화

stop 3개 + leg 2개(둘 다 PENDING)      → PLANNED
기사 출발, leg1 IN_TRANSIT             → IN_TRANSIT
leg1 완료(NYC 창고 도착), leg2 PENDING  → AT_STOP
leg2 완료(반납 디포=TERMINUS 도착)      → COMPLETED
"""),
    ]


# ════════════════════════════════════════════════════════════
# 05. 3단계 — Leg 자동 생성
# ════════════════════════════════════════════════════════════
def page_leg_gen():
    gen = """
 템플릿 "IMPORT 풀컨 배송"
    │
    ├─ step1: 터미널 → 화주   LOAD / LIVE / PPU ─▶ ┌────────────────────────┐
    │                                            │ Leg1  PENDING (LOADED)  │
    │                                            └────────────────────────┘
    └─ step2: 화주 → 터미널   EMPTY / PRE       ─▶ ┌────────────────────────┐
                                                 │ Leg2  PENDING (EMPTY)   │
                                                 └────────────────────────┘
                                                            │
                                                            ▼
                                  컨테이너 work_state = PLANNED
                                  D/O status = DISPATCHING (미배차 leg 있음)
"""
    return [
        lead("Leg 은 '트럭 한 대가, 컨테이너 하나를, 한 구간 옮기는 일'입니다. 운송의 최소 실행 단위이자 "
             "정산의 단위이기도 합니다. leg 은 보통 손으로 하나씩 만들지 않고 템플릿으로 한 번에 찍어냅니다."),
        N.h2("load_type_template = leg 청사진"),
        N.p("템플릿은 방향(IMPORT/EXPORT)별로 'step' 들을 가집니다. 각 step 은 어디서→어디로(터미널/야드/화주), "
            "적재 방식(LOAD/EMPTY), 서비스(LIVE/DROP), move_code(PPU/PRE 등)를 정의합니다. "
            "컨테이너에 템플릿을 적용(apply_load_type)하면 step 순서대로 leg 들이 PENDING(미배차)으로 생성됩니다."),
        dia(gen),
        N.p("생성된 leg 은 운송에 필요한 정보를 함께 스냅샷합니다: move_type(LOADED/EMPTY/BOBTAIL), service_type, "
            "from/to_location_type, move_code, 그리고 나중에 요율 해석에 쓰일 입력(rate_point_id=터미널/야드, "
            "dest_zip/city/state=목적지, rate_miles/rate_hours=거리/시간)."),
        N.h2("예시"),
        ex("""
컨테이너 #50 에 'IMPORT 풀컨 배송' 템플릿 적용

apply_load_type(container_id=50, template_id=10)

→ Leg1  PENDING  move=LOADED  서비스=LIVE  (터미널→화주)
→ Leg2  PENDING  move=EMPTY              (화주→터미널)
→ 컨테이너 work_state = PLANNED
→ D/O status = DISPATCHING (미배차 leg 2개)
"""),
        tip("replace_existing 으로 기존 leg 을 갈아끼울 수 있지만, 이미 IN_TRANSIT/COMPLETED 인 leg 은 보호되어 건드리지 않습니다."),
    ]


# ════════════════════════════════════════════════════════════
# 06. 4단계 — 배차
# ════════════════════════════════════════════════════════════
def page_dispatch():
    derive = """
 leg 변경 (생성 / 배정 / 삭제)
        │
        ▼
   활성 leg 중 미배정이 있나?
        ├─ 활성 leg 없음 ─────────▶ PLANNING
        ├─ 1개 이상 미배정 ───────▶ DISPATCHING
        └─ 전부 배정됨 ───────────▶ DISPATCHED

   ※ D/O 가 Hold/Cancel 이면 자동 파생 정지
   ※ YARD_STAGED 이후 진행 상태는 디스패처가 수동 전이
"""
    st = """
 ┌───────────┐  승인 (+선사 승인번호)   ┌──────────┐
 │ REQUESTED │ ───────────────────▶ │ APPROVED │  → 컨테이너 STREET_TURNED 이벤트
 └───────────┘                      └──────────┘
      │  반려(+사유)  ─▶ REJECTED
      └  취소        ─▶ CANCELLED
"""
    return [
        lead("이제 PENDING leg 에 기사를 붙입니다. 배차는 단순 update 가 아니라 전용 동작(assign/unassign)이고, "
             "그 결과로 컨테이너·D/O 상태가 자동으로 다시 계산됩니다."),
        N.h2("기사 배정 / 취소"),
        N.p("assign_driver 는 leg 에 기사(+선택적으로 트럭·샤시)를 붙이고 offered_at·assigned_at 을 찍으며 "
            "PENDING→ASSIGNED 로 바꿉니다. 그리고 컨테이너 파생 + D/O dispatch 파생을 트리거합니다. "
            "unassign_driver 는 그 반대(ASSIGNED→PENDING, 기사·시각 초기화)입니다. 즉 기사는 언제든 바꿀 수 있습니다."),
        N.h2("D/O dispatch 상태는 leg 로부터 자동 계산"),
        dia(derive),
        N.h2("한 leg 안에서 기사가 바뀔 때 (핸드오버)"),
        N.p("장거리 leg 에서 터미널 마감·사고·교대로 기사가 중간에 바뀌면 leg_driver_segment 로 구간을 나눠 기록합니다. "
            "각 segment 는 자기 기사·시작/종료시각·사유(TERMINAL_CLOSED/ACCIDENT/SHIFT_CHANGE/OTHER)를 가집니다."),
        N.h2("두 leg 을 한 기사에게 묶기 (dual_transaction)"),
        N.p("빈 컨 반납 leg + 다음 픽업 leg 을 한 기사·한 트럭으로 묶어 공차 주행을 줄입니다. "
            "dual_transaction 을 만들면 두 leg 을 같은 기사에게 자동 배차합니다."),
        N.h2("스트리트 턴 (street_turn) — 컨테이너 직접 재사용"),
        N.p("수입으로 들어와 비워진 컨테이너를, 터미널에 반납했다 다시 꺼내는 대신 곧바로 수출 화물에 재사용하는 것입니다. "
            "승인 워크플로우를 따릅니다."),
        dia(st),
        N.p("승인되면 컨테이너에 STREET_TURNED 이벤트가 자동으로 적힙니다. 같은 import/export D/O 로 중복 요청은 막힙니다."),
        N.h2("예시"),
        ex("""
Leg1 에 기사 7 배정 → ASSIGNED, 미배차 1개 남음 → D/O 는 DISPATCHING 유지
Leg2 에 기사 8 배정 → ASSIGNED, 미배차 0개      → D/O 자동 DISPATCHED
"""),
    ]


# ════════════════════════════════════════════════════════════
# 07. 5단계 — 운행
# ════════════════════════════════════════════════════════════
def page_runtime():
    sm = """
 ┌─────────┐  배차    ┌──────────┐  출발    ┌────────────┐  완료   ┌───────────┐
 │ PENDING │ ──────▶ │ ASSIGNED │ ──────▶ │ IN_TRANSIT │ ─────▶ │ COMPLETED │
 └─────────┘         └──────────┘         └────────────┘        └───────────┘
     ▲                    │                     │  실패
     │  재배차             │  배차취소            ▼
     │                    ▼                ┌────────┐
     └──────────────── PENDING            │ FAILED │ ──재배차──▶ PENDING
                                          └────────┘
 · 추가 전이:  PENDING ──즉시출발──▶ IN_TRANSIT  (드라이버앱)
 · DRY_RUN  :  reissue_dry_run 이 원본을 직접 종료시키는 종료 상태(아래)
"""
    re = """
 ┌──────────────────────────┐  reissue_dry_run
 │ 원본 Leg                  │ ─────────────────┬──▶ 원본 → DRY_RUN  (종료, 정산 base 없음)
 │ (ASSIGNED / IN_TRANSIT)   │                  │
 └──────────────────────────┘                  └──▶ 새 Leg PENDING (reissued_from=원본) ─▶ 다시 배차
"""
    return [
        lead("기사가 모바일 앱으로 운행을 보고하면 leg 상태가 흐릅니다. 이 상태머신이 운송의 심장입니다."),
        N.h2("Leg 상태머신 (단일 진실: leg/state_machine.py)"),
        dia(sm),
        N.p("전이마다 시각이 자동으로 찍힙니다: ASSIGNED→assigned_at, IN_TRANSIT→started_at, "
            "COMPLETED→completed_at(+arrived_at). FAILED 는 failure_reason 이 필수입니다. "
            "COMPLETED 가 되면 컨테이너 work_state 파생이 다시 돌아갑니다."),
        N.h2("빠꾸(DRY_RUN)와 재발급"),
        N.p("현장에 도착했는데 화물이 없어서 일을 못 한 경우(빠꾸)가 있습니다. 이건 일반 transition 으로 가는 상태가 "
            "아니라, reissue_dry_run 이 원본 leg 을 DRY_RUN 으로 '직접' 종료시키고, 같은 구간·요율입력을 복사한 "
            "새 PENDING leg 을 발급합니다. 원본은 '시도했으나 실패'로 남고, 새 leg 으로 다시 배차합니다."),
        dia(re),
        N.h2("기사 모바일 체크포인트"),
        N.p("기사 앱은 오늘 할 일(tasks/today)을 받고, 도착/출발/완료를 체크포인트로 보고하며, "
            "GPS 는 location/batch 로 묶어 올립니다(오프라인 버퍼 지원). 체크포인트는 결국 leg.transition 을 호출합니다 — "
            "단, 그 leg 이 본인 leg 인지 먼저 검증합니다."),
        N.h2("예시 — 빠꾸"),
        ex("""
Leg5 (기사7, IN_TRANSIT) 가 현장 도착했으나 화물 없음
→ reissue_dry_run(Leg5)
   Leg5  → DRY_RUN (종료, 정산엔 base 안 잡힘)
   Leg6  → PENDING (reissued_from=5)  → 재배차
→ D/O 는 미배차 leg 가 생겼으므로 다시 DISPATCHING
"""),
    ]


# ════════════════════════════════════════════════════════════
# 08. 요율 — 4가지 방식
# ════════════════════════════════════════════════════════════
def page_rate():
    big = """
 rate_group.method ─┬─ ZONE  ─┐
                    ├─ CITY  ─┤
                    ├─ MILE  ─┼──▶ rate_sheet + rate_entry  (유효일자 버전, append-only)
                    └─ HOURLY ┘             │
                                            ▼
                          driver_rate_assignment  (기사 ↔ 그룹, 유효일자)
                                            │
                                            ▼
                     정산/청구 시 RateResolver 가 leg 의 base 계산
"""
    tree = """
 leg
  │
  ▼
 기사의 그 날짜 요율그룹 있나? ──없음──▶ UNRESOLVED (배정 없음)
  │ 있음
  ▼
 method ?
  ├─ MILE / HOURLY ─▶ per_unit × (거리 또는 시간) ─▶ base ✔
  │
  └─ ZONE / CITY ─▶ point + move_type 시트 있나? ──없음──▶ UNRESOLVED
                       │ 있음
                       ▼
                    목적지 → zone(zip) / city 매핑되나? ──없음──▶ UNRESOLVED
                       │ 있음
                       ▼
                    요청 사이즈 셀 있나?
                       ├─ 있음 ─▶ 그 금액 × 1.0 ─▶ base ✔
                       └─ 없음 ─▶ 40ft 마스터 셀 있나?
                                   ├─ 있음 ─▶ 40ft 금액 × 사이즈배율 ─▶ base ✔
                                   └─ 없음 ─▶ UNRESOLVED
"""
    return [
        lead("핵심 질문: '이 leg 에 기사에게 얼마를 줄까?' 답을 내는 게 요율 엔진(RateResolver)입니다. "
             "요율은 4가지 방식이 있고, 방식마다 그룹을 만들어 표를 채우고, 그 그룹을 기사에게 할당합니다."),
        N.h2("큰 그림: 그룹 → 표 → 기사 할당 → leg 해석"),
        dia(big),
        N.p("4가지 방식:"),
        N.bullet(("MILE ", {"bold": True}), "— 거리 × 마일당 단가"),
        N.bullet(("HOURLY ", {"bold": True}), "— 시간 × 시간당 단가"),
        N.bullet(("ZONE ", {"bold": True}), "— (출발지 point) × (목적지 zip→zone) 매트릭스 셀 금액"),
        N.bullet(("CITY ", {"bold": True}), "— (출발지 point) × (목적지 city/state) 매트릭스 셀 금액"),
        N.p("ZONE/CITY 는 행(rate_point=터미널/야드) × 열(rate_zone=zip/city 묶음, 또는 city)로 된 표이고, "
            "컨테이너 사이즈별 셀을 가집니다. 요율표는 절대 덮어쓰지 않고 유효일자(effective_from/to)로 새 버전을 쌓습니다(append-only). "
            "사이즈 배율(rate_multiplier)은 20/40/45 에 대해 기본 0.85/1.0/1.0."),
        N.h2("RateResolver 가 leg 하나를 푸는 순서"),
        dia(tree),
        N.p("work_date 는 leg.completed_at(없으면 assigned_at) 기준입니다. 결과 base 는 정산 라인에 그대로 동결(snapshot)됩니다 — "
            "나중에 요율표가 바뀌어도 이미 정산된 금액은 변하지 않습니다."),
        N.h2("방식별 숫자 예시"),
        ex("""
[MILE]  기사101 → 그룹A(MILE), 단가 $2.50/mi, leg 410mi
        base = 2.50 × 410 = $1,025.00

[HOURLY] 기사102 → 그룹B(HOURLY), 단가 $45/h, leg 8.5h
        base = 45 × 8.5 = $382.50

[ZONE] 기사103 → 그룹C(ZONE), LA터미널→zip 90210
        90210 → Zone7. 셀(Zone7, 40ft) = $1,800
        40ft 정확 셀이므로 배율 1.0 → base = $1,800.00

[ZONE 사이즈 폴백] 같은 leg 인데 컨테이너가 20ft
        (Zone7, 20ft) 셀 없음 → 40ft 마스터 $1,800 × 0.85
        base = $1,530.00

[CITY] 기사104 → 그룹D(CITY), 롱비치야드→"Los Angeles, CA", 45ft
        셀(LA, CA, 45ft) = $2,200, 배율 1.0 → base = $2,200.00
"""),
        warn("UNRESOLVED(요율 못 찾음) 사유 예: 그 날짜에 기사 요율그룹 배정 없음 / point·move 시트 없음 / "
             "목적지 zip 이 어떤 zone 에도 안 묶임 / 해당 셀·날짜에 금액 미등록. 이 경우 base=0 으로 라인은 남되, "
             "정산 확정(confirm)을 막습니다."),
    ]


# ════════════════════════════════════════════════════════════
# 09. 6단계 — 정산(payroll)
# ════════════════════════════════════════════════════════════
def page_settlement():
    life = """
 ┌───────┐  confirm (UNRESOLVED 0건일 때만)  ┌───────────┐  지급   ┌──────┐
 │ DRAFT │ ───────────────────────────────▶ │ CONFIRMED │ ─────▶ │ PAID │
 └───────┘                                   └───────────┘        └──────┘
     │                                            │                  │
     └──────────────────── VOID ◀─────────────────┴──────────────────┘
   ※ VOID 된 정산의 leg 는 다시 정산 수집 대상이 됨
"""
    return [
        lead("정산은 'leg 단위'로 기사에게 지급합니다. 완료된 leg 들을 한 기사·한 기간으로 모아 한 번에 정산합니다."),
        N.h2("정산은 leg 1건 = 라인 1줄"),
        N.p("정산 헤더(payroll_settlement)는 기사 × 기간(기본 격주, 2024-01-01 기준 14일 블록)입니다. "
            "그 아래 라인(payroll_line)이 leg 한 건당 하나씩 붙고, 각 라인은 RateResolver 가 푼 base 를 "
            "그 시점에 동결(snapshot)해 가집니다(RESOLVED/UNRESOLVED 표시)."),
        N.p("어떤 leg 이 정산에 들어오나? — COMPLETED 이고, 그 기간 안이고, 아직 VOID 아닌 정산에 안 들어간 leg. "
            "(VOID 처리하면 다시 수집 대상이 됩니다.)"),
        N.h2("정산 생애주기"),
        dia(life),
        warn("confirm 은 UNRESOLVED 라인이 하나라도 있으면 막힙니다 — '요율 등록/그룹 배정 후 확정하세요'. "
             "정산 금액이 0원짜리 미해석 라인으로 새어나가는 걸 방지합니다."),
        N.h2("추가정산(accessorial) — 중간 stop, 야간 할증 등"),
        N.p("기본 운임(leg base) 외에 대기·추가정차·야간 할증 같은 부가요금을 정산에 더할 수 있습니다. "
            "이건 payroll_charge 로 들어가며, 코드·수량·단가(snapshot)·금액을 가집니다. "
            "정산 합계는 base_total(라인 base 합) + accessorial_total(charge 합) = grand_total 입니다."),
        gap("중요(현재 코드의 한계): 이 추가정산은 DRAFT 상태에서 사람이 '수동으로' 더합니다. "
            "leg 에 기록되는 부가요금 레이어(leg_layer: 중간 stop·대기·할증)는 아직 정산으로 '자동 합산되지 않습니다'. "
            "또 charge 는 leg_id 없이 정산 헤더에 붙어, 어느 leg 때문인지 코드상 연결되지 않습니다. → 15장 개선 제안 참고."),
        N.h2("핵심 예시 — leg 단위로 다 합쳐 한 번에 지급"),
        ex("""
기사 D, 기간 2026-05-01 ~ 05-14

Leg101 (완료, 410mi, MILE $2.5)        라인 base = $1,250   RESOLVED
  + 중간 stop 2회      수동 charge       EXTRA_STOP  2×$20 = $40
  + 야간 게이트 할증    수동 charge       NIGHT       1×$50 = $50
Leg102 (완료, 8.5h, HOURLY $100)        라인 base = $600    RESOLVED
Leg103 (완료, 그날 기사 요율그룹 없음)    라인 base = $0      UNRESOLVED ← confirm 차단

base_total        = 1250 + 600 + 0 = $1,850
accessorial_total = 40 + 50          = $90
grand_total       =                  = $1,940   (Leg103 요율 해결 전엔 확정 불가)
"""),
        tip("정리: leg 마다 base 가 동결되고, 부가요금이 더해지고, 한 기간치를 모아 grand_total 로 기사에게 한 번에 지급됩니다."),
    ]


# ════════════════════════════════════════════════════════════
# 10. 7단계 — 청구(invoice)
# ════════════════════════════════════════════════════════════
def page_invoice():
    money = """
 D/O 의 COMPLETED leg 들
        │  resolve_leg_rate  (정산과 같은 RateResolver)
        ├──▶ 정산 : payroll_line.base 동결      = 기사 지급액
        └──▶ 청구 : cost_total prefill          = 우리 원가
                       │
                       ▼
                charge_total (라인 합)           = 고객 청구액
                       │
                       ▼
                margin = charge_total − cost_total
"""
    life = """
 ┌───────┐ 발행  ┌────────┐ 입금  ┌──────┐
 │ DRAFT │ ────▶ │ ISSUED │ ────▶ │ PAID │
 └───────┘ ◀──── └────────┘       └──────┘
     │   수정 위해 되돌림   │            │
     └───────── VOID ◀─────┴────────────┘
"""
    return [
        lead("고객에게는 '원가 + 마진'으로 청구합니다. 원가는 기사 정산과 똑같은 요율엔진으로 계산하고, "
             "거기에 마크업을 얹어 청구액을 만듭니다."),
        N.h2("같은 요율엔진, 두 갈래"),
        dia(money),
        N.p("인보이스를 만들 때 D/O 를 연결하고 prefill 을 켜면, compute_do_cost 가 그 D/O 의 완료 leg 들을 "
            "같은 resolver 로 돌려 컨테이너별 원가를 라인으로 깔고 cost_total 을 동결합니다. "
            "처음엔 charge_total = cost_total 이라 마진 0에서 시작합니다."),
        N.h2("마크업과 마진"),
        N.p("디스패처는 DRAFT 에서 라인 단가를 올리거나(연료 할증 등) 수동 라인을 추가합니다. "
            "charge_total 은 라인 금액의 합으로 다시 계산되고, margin 은 charge_total − cost_total 으로 즉시 산출됩니다(저장 필드 아님, 계산값). "
            "원가는 D/O 의 leg 상황이 바뀌면 recompute_cost 로 다시 계산할 수 있습니다(라인은 안 건드림)."),
        N.h2("인보이스 생애주기"),
        dia(life),
        N.h2("예시"),
        ex("""
D/O #50, 컨테이너 2개(둘 다 완료)

원가 prefill (정산과 같은 요율)
  컨테이너 C-2000  원가 $1,250
  컨테이너 C-2001  원가 $600
  cost_total = $1,850   (초기 charge_total 도 $1,850, margin 0)

마크업
  C-2000 라인 단가 $1,250 → $1,350
  + 연료 할증 수동 라인     $55.50
  charge_total = 1350 + 600 + 55.50 = $2,005.50

margin = 2,005.50 − 1,850 = $155.50  (이익)
"""),
        tip("정산(원가)과 청구는 서로 독립입니다 — 정산을 안 만들었어도 인보이스 원가는 요율엔진으로 바로 계산됩니다."),
    ]


# ════════════════════════════════════════════════════════════
# 11. 실시간·알림·감사·분석
# ════════════════════════════════════════════════════════════
def page_realtime():
    seq = """
 도메인 서비스 ──publish(team, "leg.status_changed", {id})──▶ Redis pub/sub
 Redis pub/sub ──채널 메시지─────────────────────────────────▶ WS ConnectionManager
 WS ConnectionManager ──fanout (id만)───────────────────────▶ 클라이언트
 클라이언트 ──GET /legs/{id} 로 최신 조회─────────────────────▶ 도메인 서비스
"""
    return [
        lead("운영을 실시간으로 굴리고, 추적하고, 들여다보는 가로축 기능들입니다."),
        N.h2("실시간(realtime) — Redis pub/sub → WebSocket"),
        N.p("도메인 서비스가 CUD 후 이벤트를 발행하면 Redis 채널(tms:team:{id}:events)로 가고, "
            "각 워커의 ConnectionManager 가 그 팀에 붙은 WS 연결들로 뿌립니다(fanout). 페이로드는 id-only."),
        dia(seq),
        N.p("WS 연결은 ?token=JWT&team_id= 로 인증하고, 30초 ping/60초 idle timeout 으로 관리합니다. "
            "연결 큐가 넘치면 오래된 메시지를 버리고 dropped 카운터를 올립니다(끊지 않음)."),
        N.h2("알림(notification) — 이벤트 → 담당자 받은함"),
        N.p("realtime.publish(db=...) 가 호출되면 fan_out 이 이벤트 종류를 제목/본문으로 바꿔(예: 'D/O 상태가 변경되었습니다', "
            "'PLANNING → DISPATCHING') 팀의 admin/dispatcher 들에게 인박스 행을 만듭니다 — 단, 기사(DRIVER)와 행위자 본인은 제외. "
            "읽음 처리·soft delete 지원. (푸시 발송 인프라는 있으나 실제 FCM/APNS 디스패치는 미구현)"),
        N.h2("감사 로그(audit_log) — 누가·언제·무엇을"),
        N.p("폴리모픽 append-only 타임라인입니다. entity_type+entity_id(FK 없이) + action + summary + before/after 스냅샷을 적습니다. "
            "WS 이벤트와 달리 '자동'이 아니라 도메인 서비스가 명시적으로 record 를 호출합니다. "
            "엔티티별 타임라인 조회와 최근 활동 대시보드에 쓰입니다."),
        N.h2("분석(analytics) — 모델 없이 집계만"),
        N.bullet(("margin_trend ", {"bold": True}), "— 일자별 매출(invoice)−지급(payroll) 마진 추이"),
        N.bullet(("driver_utilization ", {"bold": True}), "— 기사별 leg 완료율"),
        N.bullet(("container_turnover ", {"bold": True}), "— 컨테이너 이벤트·평균 dwell time"),
        N.bullet(("street_turn_savings ", {"bold": True}), "— 승인된 스트리트턴 × 절감단가(=$155/건)"),
        N.bullet(("expiring_compliance ", {"bold": True}), "— 트럭/샤시/기사 보험·검사·면허 만료 임박"),
        tip("분석은 캐시 없이 매 요청 집계합니다(개선 여지). 모두 읽기 전용이라 권한 가드 없이 조회됩니다."),
    ]


# ════════════════════════════════════════════════════════════
# 12. 모바일 앱 백엔드 (BFF)
# ════════════════════════════════════════════════════════════
def page_mobile():
    flow = """
 GET tasks/today (오늘 PENDING/IN_TRANSIT leg)
        │
        ▼
 POST legs/{id}/checkpoint (도착/출발/완료) ──▶ leg.transition  (본인 leg 인지 검증 후)

 POST location/batch (GPS 묶음) ───────────▶ location_ping  (append-only)
 POST push-tokens (FCM/APNS) ──────────────▶ push_token     (upsert)
 수익/정산 보기 ───────────────────────────▶ _earnings_by_leg (payroll_line 기반)
"""
    return [
        lead("driver_mobile 은 기사용 Flutter 앱의 전용 백엔드(BFF)입니다. 자기 모델·레포가 없고, "
             "다른 도메인(leg·driver·payroll·location_ping·push_token)을 조립해 모바일 친화 응답을 만듭니다."),
        N.h2("모든 엔드포인트는 기사 전용"),
        N.p("require_driver 가드로 role==DRIVER 만 통과합니다. 프리픽스는 /api/v1/driver/... 입니다."),
        N.h2("주요 흐름"),
        dia(flow),
        N.p("today 는 오늘 범위의 본인 PENDING/IN_TRANSIT leg 을 픽업시간순으로 줍니다. "
            "checkpoint 는 결국 leg 상태머신을 호출하되 leg.driver_id == 본인인지 먼저 확인합니다. "
            "수익 화면은 payroll_line 을 조인해 PAID=정산완료/그외=대기로 보여줍니다(정산 도메인 기준)."),
        N.h2("위치·푸시 토큰 (둘 다 append-only/registry)"),
        N.p("location_ping 은 위경도(소수 7자리 ~1cm)·속도·방향·시각을 묶음으로 적재합니다(오프라인 버퍼 대응). "
            "push_token 은 (기사, 플랫폼, 토큰) 유일로 upsert. 둘 다 기사 삭제 시 CASCADE."),
        gap("미구현: 관리자용 기사 경로 조회 엔드포인트 없음, location_ping 정리(보존) 잡 없음, "
            "FCM/APNS 실제 발송 코드 없음."),
    ]


# ════════════════════════════════════════════════════════════
# 13. 인증·권한·API·파일
# ════════════════════════════════════════════════════════════
def page_authz():
    auth = """
 사용자 ──POST /login (email+pw)───────────────▶ auth
 auth   ──세션 sess/refresh/device 저장─────────▶ Redis
 auth   ──access(30분) + refresh(쿠키)──────────▶ 사용자
 ───────────────────── (access 만료, 401) ─────────────────────
 사용자 ──POST /token/access (refresh)──────────▶ auth
 auth   ──refresh 일치 확인 (재사용=탈취 감지)────▶ Redis
 auth   ──새 access─────────────────────────────▶ 사용자
"""
    guard = """
 mutation 요청
      │
      ▼
 permission_guard(필요코드)
      │   user+team 권한메타 (Redis 2단 캐시)
      ▼
 is_admin ?  ──예──▶ 통과
      │ 아니오
      ▼
 보유코드 ∩ 필요코드 있음 ?  ──있음──▶ 통과
      │ 없음
      ▼
 403 권한 없음
"""
    return [
        lead("누가 들어오고, 무엇을 할 수 있고, 외부와 어떻게 연동하고, 파일을 어떻게 다루는가."),
        N.h2("인증(auth) — JWT + OTP + OAuth"),
        N.p("access 토큰(30분)·refresh 토큰(쿠키, 약 2시간)을 발급합니다. access JWT 에는 role 클레임이 들어가 "
            "WS·미들웨어가 빠르게 역할을 판단합니다. 세션·디바이스·리프레시는 Redis 로 관리하고, "
            "리프레시 재사용(탈취) 감지로 회전합니다."),
        dia(auth),
        N.p("OTP 는 이메일(비번 재설정)과 기사 폰 로그인 흐름이 있고, OAuth(Google 등)는 웹 팝업 → 콜백으로 "
            "토큰을 교환합니다(에러는 JSON 이 아니라 프론트 에러 페이지로 리다이렉트)."),
        N.h2("권한(rbac) — 역할 + 권한코드 + 그룹"),
        N.p("두 축이 있습니다. (1) RolesEnum(ADMIN/DISPATCHER/DRIVER/CUSTOMER/VIEWER)으로 빠른 역할 게이팅(require_driver 등). "
            "(2) 권한그룹(team-scoped)에 권한코드(DO_WRITE, LEG_ASSIGN_DRIVER, SETTLEMENT_APPROVE…)를 담아 사용자에 부여."),
        dia(guard),
        N.p("캐시는 2단입니다 — 사용자↔그룹 메타(5분), 그룹↔코드목록(그룹 version 키, 5분). "
            "그룹 권한을 바꾸면 version 이 올라 캐시키가 갈리며 자동 무효화됩니다. "
            "mutation 라우터마다 permission_guard 를 sentinel 의존성으로 부착합니다."),
        N.h2("외부 연동(api_key)"),
        N.p("팀별 API 키(tms_ 접두 + 256bit)를 발급합니다. 전체 값은 생성 시 1회만 보여주고, "
            "목록에는 접두(prefix)만 노출합니다. 회수는 soft delete(is_active=False). (X-API-Key 인증 배선은 아직 미완.)"),
        N.h2("파일(file) — MinIO presigned, 폴리모픽"),
        N.p("파일은 백엔드를 거치지 않고 클라이언트가 MinIO 로 직접 업로드합니다. "
            "(1) 업로드 URL 요청(검증 후 10분 presigned PUT) → (2) 클라이언트가 직접 PUT → (3) commit 으로 확정(이미지면 리사이즈). "
            "소유는 FK 가 아니라 domain+object_id 폴리모픽으로 연결합니다(예: delivery_order/50)."),
        ex("""
파일 키 구조
  private/{team_id}/{domain}/{object_id}/{filename}
  예: private/1/delivery_order/50/invoice.pdf
"""),
    ]


# ════════════════════════════════════════════════════════════
# 14. 상태 머신 한눈에
# ════════════════════════════════════════════════════════════
def page_statemachines():
    do = """
 [ 자동 파생 구간 — leg 기준 ]
   PLANNING ⇄ DISPATCHING ⇄ DISPATCHED
     (미배정 leg 0 → DISPATCHED, 1+ → DISPATCHING, 활성 leg 없음 → PLANNING)
                          │
                          ▼  (이후 디스패처 수동 전이)
   YARD_STAGED ─▶ FINAL_DELIVERY ─▶ EMPTY_STAGED ─▶ COMPLETED
                       └────────────────────────────────┘
   ※ Hold/Cancel overlay 가 걸리면 자동 파생 정지
"""
    cont = """
 DRAFT ─▶ PLANNED ─▶ IN_TRANSIT ⇄ AT_STOP ─▶ COMPLETED
                         │           │
                         │           └─▶ WAITING_PLAN ⚠ (다음 stop/leg 미생성)
                         └─▶ HOLD / CANCELLED (수동)
"""
    leg = """
 PENDING ─▶ ASSIGNED ─▶ IN_TRANSIT ─▶ COMPLETED
   ▲   ▲       │             │
   │   └─배차취소┘             └─▶ FAILED ─▶ (재배차) PENDING
   └─ 즉시출발 ─────────────────────────────┘
 DRY_RUN : reissue_dry_run 이 원본을 직접 종료(별도 종료상태)
"""
    pay = """
 DRAFT ─▶ CONFIRMED ─▶ PAID
   │          │          │
   └──── VOID ◀┴──────────┘   (VOID 면 leg 재수집)
"""
    inv = """
 DRAFT ⇄ ISSUED ─▶ PAID
   │       │         │
   └─ VOID ◀┴─────────┘
"""
    stt = """
 REQUESTED ─▶ APPROVED  (+컨테이너 STREET_TURNED)
     ├─▶ REJECTED
     └─▶ CANCELLED
"""
    return [
        lead("앞에서 흩어져 나온 모든 상태 머신을 한 곳에 모았습니다. 빠른 참조용."),
        N.h2("D/O (운송 의뢰)"),
        dia(do),
        N.h2("Container work_state"),
        dia(cont),
        N.h2("Leg"),
        dia(leg),
        N.h2("정산(payroll)"),
        dia(pay),
        N.h2("청구(invoice)"),
        dia(inv),
        N.h2("스트리트 턴(street_turn)"),
        dia(stt),
    ]


# ════════════════════════════════════════════════════════════
# 15. 개선 제안
# ════════════════════════════════════════════════════════════
def page_improvements():
    return [
        lead("현재 코드를 직접 확인해서 찾은, '더 채우면 좋은' 지점들입니다. 전부 코드 근거가 있습니다."),
        N.h2("1) leg 부가요금을 정산에 자동 합산"),
        gap("지금: leg 에는 부가요금 레이어(leg_layer: 중간 stop·대기·할증)를 기록할 수 있지만, "
            "정산(payroll)·청구(invoice) 어디에서도 이 레이어를 읽지 않습니다(코드 grep 결과 사용처 0). "
            "그래서 사용자가 기대하는 '중간 stop 하면 자동으로 더 줌, 야간이라 자동으로 더 줌'이 아직 자동이 아닙니다 — "
            "정산 charge 는 DRAFT 에서 전부 수동 입력."),
        N.p("제안: payroll.build() 단계에서 각 leg 의 leg_layer(addon/charge_event/stop_off)와 accessorial 규칙을 읽어 "
            "payroll_charge 를 자동 생성. 그러면 'leg 단위로 부가요금이 자동으로 쌓여 한 번에 정산'이 코드로 성립합니다."),
        N.h2("2) 추가정산(charge)을 leg 에 연결"),
        gap("지금: PayrollChargeModel 에 leg_id 가 없어, 추가요금이 '어느 leg 때문인지' 데이터로 연결되지 않습니다(정산 헤더에만 합산)."),
        N.p("제안: payroll_charge 에 leg_id(nullable) 추가 → leg 별 정산 내역을 정확히 보여주고, (1)의 자동 합산과도 맞물립니다."),
        N.h2("3) accessorial.auto_apply 실제 소비"),
        gap("지금: accessorial 마스터에 auto_apply 플래그가 있지만 정산 build 가 이를 사용하지 않습니다."),
        N.p("제안: auto_apply=true 인 규칙(예: 야간 할증, 기본 대기 공제)을 build 시점에 자동 적용."),
        N.h2("4) WAITING_PLAN 보조"),
        gap("지금: 컨테이너가 WAITING_PLAN(다음 stop/leg 미생성)에 빠지면 디스패처가 수동으로 채워야 합니다(자동 생성 룰 없음)."),
        N.p("제안: WAITING_PLAN 진입 시 알림 발송 + 다음 leg 후보 자동 제안(템플릿 잔여 step 기반)."),
        N.h2("5) 운영 인프라 마무리"),
        N.bullet("푸시(FCM/APNS) 실제 발송 코드 — push_token 은 쌓이지만 보내는 곳이 없음."),
        N.bullet("X-API-Key 인증 배선 — api_key 는 발급되지만 검증 경로 미완."),
        N.bullet("analytics 캐시 — 매 요청 집계라 비쌈. Redis 캐시 권장."),
        N.bullet("location_ping 보존/정리 잡 + 관리자 경로 조회 엔드포인트."),
        tip("위 1~3 이 사용자가 말한 '정산 로직'의 핵심 빈틈입니다. 1번부터 채우면 '예시로 든 그 동작'이 코드로 완성됩니다."),
    ]
