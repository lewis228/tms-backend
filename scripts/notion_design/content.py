# scripts/notion_design/content.py
"""TMS 현재 설계 Notion 문서 — 11개 페이지 블록 빌더 (검증된 사실 기준).

각 함수는 notion_api 블록 리스트를 반환. publish.py 가 상위→하위 순으로 생성.
"""
from __future__ import annotations
from notion_api import (
    h1, h2, h3, p, bullet, numbered, divider, callout, code, toggle, table, rt,
)

STAMP = "2026-06 구현 완료 + 전체 점검·수정 반영 (alembic head 969c61fa6a08, pytest 99 passed)"


# ════════════════════════════════════════════════════════════
# 0. 상위 페이지
# ════════════════════════════════════════════════════════════
def page_overview():
    return [
        callout("이 문서는 현재 구현된 TMS 설계를 도메인·데이터모델·로직·흐름 중심으로 정리합니다. "
                "화면(UI)은 추후 전면 변경 예정이므로 디자인이 아니라 '설계'가 핵심입니다.",
                emoji="📘", color="blue_background"),
        p((STAMP, {"bold": True})),
        divider(),
        h2("개요"),
        bullet("스택: FastAPI + Async SQLAlchemy 2.0 + MySQL 8 + Redis + MinIO + Alembic"),
        bullet("멀티테넌시: 모든 비즈니스 데이터는 Team 루트. 3단 방어선(DB 복합FK · ORM primaryjoin · App _require_team)"),
        bullet("비즈니스 도메인 약 46개 / 마이그레이션 33개 / 통합·단위 테스트 15파일"),
        bullet("프론트: React 19 + Vite + TanStack Query + Zustand (요율·마스터·D/O·Shipment탭·디스패치·정산/Invoice·대시보드 구현)"),
        divider(),
        h2("읽는 순서 (하위 페이지)"),
        numbered("아키텍처 & 멀티테넌시 & 공통 규약"),
        numbered("도메인 카탈로그 ① 마스터 데이터"),
        numbered("도메인 카탈로그 ② 실행 (D/O · Container · Leg)"),
        numbered("도메인 카탈로그 ③ 요율 서브시스템"),
        numbered("도메인 카탈로그 ④ 정산 · 청구 (Payroll · Invoice)"),
        numbered("도메인 카탈로그 ⑤ 모바일 · 실시간 · AI · 시스템 · RBAC"),
        numbered("상태 머신 & 파생 엔진"),
        numbered("요율 해석 + 머니 체인 ⭐"),
        numbered("프론트엔드 IA"),
        numbered("마이그레이션 히스토리 · 테스트 · 재설계 결정"),
        divider(),
        h2("핵심 설계 결정 (요약)"),
        table(["영역", "결정"], [
            ["위계", "D/O(1 B/L) → Container(=Shipment, N개) → Leg(N개, 정산 단위)"],
            ["상태", "D/O 상태 ≠ Leg 상태. D/O는 leg 기준 파생(DISPATCHING/DISPATCHED)"],
            ["요율", "4방식 Zone/City/Mile/Hourly. 요율그룹이 1급 시민, 드라이버는 그룹에 배정"],
            ["유효일자", "요율 셀은 append-only 버전관리. 정산 시점 work_date 유효요율 snapshot 동결"],
            ["정산", "Payroll = 드라이버×기간, leg base를 RateResolver로 해석해 라인 동결"],
            ["청구", "Invoice = cost-plus. D/O 기사원가 프리필 + 수동 마크업 → 마진"],
            ["구 v3", "구 rate_card/quote/tariff/leg_rate/distance_matrix/leg_charge/settlement 제거"],
        ]),
        divider(),
        h2("검증 상태 (전체 점검 라운드)"),
        callout("3개 에이전트(백엔드/프론트/API계약) 감사 + 직접 재검증 후 결함 수정 완료. "
                "테스트가 못 잡던 런타임/정합 결함을 잡음.", emoji="🔍", color="green_background"),
        bullet("driver_mobile 정산 메서드가 삭제된 settlement 모델을 참조하던 런타임 크래시 → payroll 기반으로 repoint"),
        bullet("leg 배차(assign/unassign) 프론트 연결 + updateLeg PATCH→PUT(405) 수정"),
        bullet("구 도메인 죽은 코드/주석/문서 드리프트 정리(v3_publish 상수, fan_out 핸들러, CLAUDE.md 도메인트리)"),
        bullet("백엔드 99 passed · 프론트 typecheck+build 통과 · autogenerate 드리프트 0"),
    ]


# ════════════════════════════════════════════════════════════
# 1. 아키텍처 & 멀티테넌시
# ════════════════════════════════════════════════════════════
def page_architecture():
    return [
        h1("아키텍처 & 멀티테넌시 & 공통 규약"),
        callout("ste(STE Tracking) 백엔드 패턴이 헌법. 모든 도메인은 동일한 model/repository/service/router/schemas 구조를 복제한다.", emoji="🏛️"),

        h2("1. 기술 스택"),
        table(["영역", "구성"], [
            ["API", "FastAPI (async), lifespan + 미들웨어 4단"],
            ["DB", "MySQL 8 + Async SQLAlchemy 2.0 (aiomysql), read/write 세션 분리"],
            ["Cache", "Redis (세션/OTP/WS pub-sub, read/write 분리)"],
            ["Storage", "MinIO/S3 (presigned URL, 폴리모픽 file 도메인)"],
            ["Migration", "Alembic (autogenerate, MySQL ENUM 변경은 수동 op.alter_column)"],
            ["인증", "JWT(access/refresh) + API Key, BasicAuth 로그인, web=BROWSER_ID 쿠키 device 바인딩"],
        ]),

        h2("2. 멀티테넌시 — Team 3단 방어선"),
        p("모든 비즈니스 데이터는 ", ("team_id", {"code": True}), " 를 가진다. 예외(글로벌): User, Team, UserTeam, Permission, FileAsset."),
        h3("① DB 레이어"),
        bullet("team_id FK → teams.id ondelete=CASCADE + index"),
        bullet("UniqueConstraint(team_id, id) — 복합 FK 타겟"),
        bullet("같은 도메인 라인 테이블은 복합 FK: ForeignKeyConstraint([team_id, parent_id], [parent.team_id, parent.id])"),
        bullet("도메인 간 FK는 단순 FK + ondelete 분기: RESTRICT(참조보호) / SET NULL(부가정보) / CASCADE(라인)"),
        h3("② ORM 레이어"),
        bullet("(Base, TeamScopedMixin) 이중 상속. 모든 relationship primaryjoin 에 foreign(X.team_id)==Y.team_id 포함"),
        bullet("라인 테이블은 __with_team_rel__=False (헤더 통해 team 접근)"),
        bullet("ORM_LAZY_DEFAULT='raise' — N+1 차단. 상세는 selectinload + Summary/Response 스키마 분리"),
        h3("③ App 레이어"),
        bullet("Repository._require_team() — 모든 쿼리 WHERE 첫 조건"),
        bullet("Router: Depends(get_team_scope) — X-Team-Id 헤더를 user_team 멤버십으로 검증"),

        h2("3. 요청 흐름 (팀 scoped)"),
        code("HTTP\n → AuthMiddleware (JWT 디코드, 실패해도 raise 안 함)\n → access_token (token_type=='access' 검증)\n"
             " → permission_guard(CODE) (RBAC 코드, mutation 에 부착)\n → get_team_scope (X-Team-Id → 멤버십)\n"
             " → get_current_user (actor)\n → Service(db, team_id, redis?)\n → Repository._require_team()", language="text"),

        h2("4. 공통 규약"),
        table(["규약", "내용"], [
            ["Soft-delete", "is_active=False (앱 레이어). 하드삭제는 FK CASCADE(팀/부모 삭제)만. updated_at 이 삭제시점"],
            ["페이지네이션", "커서 기반만 (CommonService.paginate). LIMIT/OFFSET 금지"],
            ["DELETE 응답", "HTTP 200 + entity(is_active=False) — 프론트 setQueryData 패치용"],
            ["WS 이벤트", "publish_entity_event — id-only payload. 클라가 id 받아 GET 후 캐시 패치"],
            ["/sync", "GET /<domain>/sync?since=<ts> — 재접속 누락분 catch-up (events 배열)"],
            ["DateTime", "항상 UTC, DateTime(timezone=True). 표시 직전에만 팀 timezone shift"],
            ["금액/수량", "Numeric — 금액 (18,3) 또는 (14,2), 수량 (18,4)"],
            ["예외", "AppException(code, message, status_code) 전역 핸들러. state 위반은 state_machine 전용 서브클래스"],
        ]),
        h2("5. 미들웨어 (역순 등록 → 실행 외→내)"),
        bullet("CORS → LogContext(X-Request-ID) → Auth(JWT 무른확인) → AccessLog(method/path/status/ms)"),
    ]


# ════════════════════════════════════════════════════════════
# 2. 마스터 데이터
# ════════════════════════════════════════════════════════════
def _ep(s): return code(s, language="text")

def page_master():
    return [
        h1("도메인 카탈로그 ① 마스터 데이터"),
        callout("마스터는 운영 자원·요율 구성의 기준 데이터. 전부 커서 페이지네이션 + /sync + (일부)bulk.", emoji="🗂️"),

        h2("customer — 거래처"),
        bullet("테이블 customer. 핵심: name, code, kind(PartnerKind), billing_address, contact_name/email/phone, mc_number, dot_number, insurance_expires_at, insurance_doc_url, payment_terms_days, note"),
        bullet("enum PartnerKind: CUSTOMER / CARRIER / BROKER / VENDOR"),
        _ep("POST/GET/PUT/DELETE /api/v1/customers[/{id}] · /sync · /bulk/{create,update,delete}"),

        h2("terminal — 항만 터미널 / vessel — 선박 / location — 위치"),
        bullet("terminal: name, code, address, latitude, longitude, note"),
        bullet("vessel: name, imo_number, line, note"),
        bullet("location: name, kind(LocationKind: YARD/CUSTOMER/PORT/OTHER), address, latitude, longitude, note"),
        _ep("/api/v1/{terminals,vessels,locations} — CRUD + /sync + /bulk/*"),

        h2("driver — 운전기사"),
        bullet("user_id(FK), license_number, license_state, employment_kind, carrier_id, payment_terms_kind, payment_terms_value, default_truck_id, default_chassis_id, duty_status, duty_changed_at"),
        bullet("컴플라이언스(DQ): license_expires_at, medical_cert_expires_at, twic_expires_at, hire_date"),
        bullet("enum EmploymentKind: IN_HOUSE / OWNER_OPERATOR_SOLO / CARRIER_DRIVER · PaymentTermsKind: PERCENT_OF_REVENUE / PER_LEG / HOURLY / SALARY · DutyStatus: OFF_DUTY / ON_DUTY / IN_BREAK"),
        _ep("/api/v1/drivers — CRUD + /sync + /bulk/*"),

        h2("truck / chassis / equipment_pool — 장비"),
        bullet("truck: plate_no, vin, make, model, year, owner_kind(COMPANY/DRIVER), status(ACTIVE/MAINTENANCE/RETIRED), registration_expires_at, insurance_expires_at, inspection_expires_at"),
        bullet("chassis: chassis_number, size(20/40/45/COMBO), owner_kind(COMPANY/DRIVER/TERMINAL_POOL/THIRD_PARTY_POOL), owner_pool_id, status(AVAILABLE/IN_USE/AT_POOL/MAINTENANCE), current_location_id, registration_expires_at, inspection_expires_at"),
        bullet("equipment_pool: name, kind(TERMINAL_POOL/THIRD_PARTY_POOL), operator, location_id, contact"),
        callout("재설계 보강: truck/chassis 등록·보험·검사 만료일, driver TWIC·입사일 → Phase 6 만료 알림(/analytics/expiring-compliance)이 사용.", emoji="🆕", color="yellow_background"),
        _ep("/api/v1/{trucks,chassis,equipment-pools} — POST/GET/PATCH/DELETE + /bulk/delete"),

        h2("charge_code — 요금 코드 마스터"),
        bullet("code, label, category(ChargeCategory), unit(ChargeUnit: FLAT/HOUR/MINUTE/DAY/MILE/PERCENT), kind(ChargeKind: BASE/ACCESSORIAL/PENALTY/FUEL/TAX/DISCOUNT)"),
        _ep("/api/v1/charge-codes — POST/GET/PATCH/DELETE + /bulk/delete"),
    ]


# ════════════════════════════════════════════════════════════
# 3. 실행 (D/O·Container·Leg)
# ════════════════════════════════════════════════════════════
def page_execution():
    return [
        h1("도메인 카탈로그 ② 실행 (D/O · Container · Leg)"),
        callout("위계: Delivery Order(헤더) → Container(=Shipment) → Leg(정산 단위). "
                "D/O 상태는 leg 기준으로 파생되고 Leg는 독립 상태머신.", emoji="🚚"),

        h2("delivery_order — D/O 헤더"),
        bullet("status(DeliveryStatus), direction(IMPORT/EXPORT), customer_id(RESTRICT), terminal_id/vessel_id(SET NULL), bl_number, booking_number, reference, eta, bl_released"),
        bullet("Hold/Cancel overlay(재설계): is_on_hold, hold_reason, cancelled_at, cancel_reason — 워크플로우 status와 직교"),
        bullet("DeliveryStatus: PLANNING / DISPATCHING / DISPATCHED / YARD_STAGED / FINAL_DELIVERY / EMPTY_STAGED / COMPLETED"),
        _ep("/api/v1/delivery-orders — CRUD + /sync + /bulk/* + /{id}/transition + /{id}/hold + /{id}/cancel + /{id}/activity"),

        h2("container — 컨테이너 (=Shipment)"),
        bullet("delivery_order_id(복합FK CASCADE), sequence_no, container_number, seal_no, size(ContainerSize), pickup/delivery/return_appointment, demurrage_lfd, detention_lfd, empty_date, loaded_date, service_type, pier_pass_paid, customs_cleared"),
        bullet("status(=DeliveryStatus) + work_state(ContainerState: DRAFT/PLANNED/IN_TRANSIT/AT_STOP/WAITING_PLAN/HOLD/COMPLETED/CANCELLED 자동 파생)"),
        bullet("ContainerSize: 20GP/40GP/40HC/40OT/45HC/20RF/40RF"),
        _ep("/api/v1/containers — POST/GET/PATCH/DELETE + /{id}/full(상세조립) + /{id}/events + /events/all"),

        h2("container_event — 컨테이너 이벤트 (append-only)"),
        bullet("event_kind: GATE_OUT / DELIVERED / EMPTIED / STREET_TURNED / REUSED / GATE_IN / RETURNED"),

        h2("leg — 운송 구간 (정산 단위)"),
        bullet("재설계 축: from_location_type × to_location_type × move_type × service_type + move_code(Layer1)"),
        bullet("move_type(MoveType): LOADED/EMPTY/BOBTAIL · service_type(ServiceType): LIVE/DROP/NONE · LegLocationType: TERMINAL/YARD/CUSTOMER"),
        bullet("move_code(LegMoveCode): PPU/PRE/PPL/DRP/STR/TRL/RMP/OTR/ERP"),
        bullet("요율 입력: rate_point_id, dest_zip/dest_city/dest_state, rate_miles, rate_hours (RateResolver 입력)"),
        bullet("배차: driver_id, truck_id, chassis_id + assigned_at/started_at/arrived_at/completed_at"),
        bullet("Dry Run 재발급: reissued_from_leg_id (원본→DRY_RUN, 새 leg PENDING)"),
        bullet("status(LegStatus): PENDING / ASSIGNED / IN_TRANSIT / COMPLETED / FAILED / DRY_RUN"),
        _ep("/api/v1/legs — CRUD + /sync + /bulk/* + /{id}/transition + /{id}/assign + /{id}/unassign + /apply-load-type + /{id}/reissue"),

        h2("부속 도메인"),
        table(["도메인", "역할 / 핵심"], [
            ["leg_stop", "leg 내 stop (StopKind 10종, StopRole ORIGIN/DELIVERY/TRANSIT/TERMINUS)"],
            ["container_stop", "컨테이너 정차지 (seq, 도착/출발). /containers/{id}/stops"],
            ["leg_layer", "Layer2 addon + Layer3 charge_event(DET/DMR/YRD/STP) + stop_off. /leg-addons /leg-charge-events /leg-stop-offs"],
            ["leg_driver_segment", "leg 내 기사 인계(HandoverReason). /legs/{id}/segments"],
            ["chassis_event", "샤시 이벤트 append-only (PICKED_UP/DROPPED_OFF/FLIPPED/RETURNED_*)"],
            ["street_turn", "컨테이너 재사용(import↔export) + 승인. REQUESTED/APPROVED/REJECTED/CANCELLED. /{id}/approve|reject|cancel + /candidates"],
            ["dual_transaction", "반납 leg + 픽업 leg 1드라이버 묶음. PLANNED/COMPLETED/CANCELLED. /{id}/complete|cancel"],
            ["load_type_template", "Leg 청사진(헤더+step). apply_load_type 가 컨테이너에 leg 자동생성. /seed-defaults · /{id}/steps"],
        ]),
    ]


# ════════════════════════════════════════════════════════════
# 4. 요율 서브시스템
# ════════════════════════════════════════════════════════════
def page_rate():
    return [
        h1("도메인 카탈로그 ③ 요율 서브시스템"),
        callout("요율그룹(=정산그룹)이 1급 시민. 드라이버는 그룹에 배정되고, 그룹이 method(Zone/City/Mile/Hourly)와 요율표를 소유. "
                "셀은 유효일자 버전관리(append-only).", emoji="💲"),

        h2("rate_group — 요율/정산 그룹"),
        bullet("name, method(RateMethod: ZONE/CITY/MILE/HOURLY), is_default, is_template, description"),
        _ep("/api/v1/rate-groups — CRUD + /sync"),

        h2("rate_point — 요율표 행 (Terminal/Yard)"),
        bullet("name, code, point_type(PointType: TERMINAL/YARD), address, latitude, longitude, terminal_id, location_id"),
        _ep("/api/v1/rate-points — CRUD + /sync + /bulk/*"),

        h2("rate_zone (+ member) — 요율표 열 (지역)"),
        bullet("rate_zone: name, code, color, geojson(시각화), description / rate_zone_member: zip_code, city, state"),
        bullet("조회는 zip→zone 인덱스(member)만. 폴리곤(geojson)은 백필/시각화 전용"),
        _ep("/api/v1/rate-zones — CRUD + /sync + /{id}/members(GET·PUT 전체교체)"),

        h2("rate_sheet — 요율표 슬롯"),
        bullet("rate_group_id(RESTRICT), kind(SheetKind: POINT_ZONE/POINT_CITY/POINT_POINT/MILE/HOURLY), move_type(RateMoveType: LOAD/EMPTY/NONE), row_point_id, open_entry_count"),
        _ep("/api/v1/rate-sheets — CRUD + /sync + /{id}/entries(set·bulk) + /{id}/entries(목록) + /{id}/history + /{id}/lookup + /resolve/preview"),

        h2("rate_entry (+ history) — 유효일자 셀 (append-only)"),
        bullet("col_zone_id / col_point_id / col_city+col_state (방식별 좌표) + container_size(RateContainerSize: SIZE_20/SIZE_40/SIZE_45) + amount/per_unit + effective_from/effective_to + source(RateEntrySource: SHEET/MILE_RATE/HOURLY_RATE/MANUAL/IMPORT)"),
        bullet("rate_entry_history: 변경 전/후 amount·per_unit + effective_from + reason (감사)"),
        callout("셀 변경 = UPDATE 아님. 기존 open row를 effective_to=from-1d 로 CLOSE + 새 row INSERT. 같은 시작일이면 기존 SUPERSEDE(is_active=False). 정산 참조 있으면 동결.", emoji="📅", color="yellow_background"),

        h2("rate_multiplier — 컨테이너 배율"),
        bullet("rate_group_id(None=전역), container_size, factor(예 20=0.85, 45=1.0). 40ft 기준 셀 × 배율 fallback"),
        _ep("/api/v1/rate-multipliers — GET 목록 + PUT upsert + DELETE/{id}"),

        h2("driver_rate_assignment — 드라이버↔그룹 배정 (유효일자)"),
        bullet("driver_id(CASCADE), rate_group_id(RESTRICT), effective_from, effective_to. work_date 기준 활성 배정으로 그룹 결정"),
        _ep("/api/v1/driver-rate-assignments — CRUD + /sync"),

        h2("accessorial — 부가요금 규칙 마스터"),
        bullet("code, label, category(AccessorialCategory 17종: WAITING/EXTRA_STOP/DRY_RUN/PENALTY/SURCHARGE/FUEL/CHASSIS_SPLIT/...), unit_amount, unit(AccessorialUnit: FLAT/HOUR/MINUTE/DAY/MILE/PERCENT)"),
        _ep("/api/v1/accessorials — CRUD + /sync"),

        h2("rate_import — Excel/CSV 입출력"),
        _ep("POST /api/v1/rate-import/sheets/{id}/entries · GET .../entries.csv · POST .../zones/{id}/members · GET .../members.csv"),
    ]


# ════════════════════════════════════════════════════════════
# 5. 정산 · 청구
# ════════════════════════════════════════════════════════════
def page_settlement():
    return [
        h1("도메인 카탈로그 ④ 정산 · 청구"),
        callout("Payroll = 드라이버에게 주는 정산(AP). Invoice = 고객에게 받는 청구(AR). "
                "둘은 분리되며, Invoice는 Payroll 원가를 프리필해 cost-plus 마진을 만든다.", emoji="💰"),

        h2("payroll — 드라이버 정산"),
        bullet("payroll_settlement(헤더): driver_id, period_start, period_end, status(PayrollStatus: DRAFT/CONFIRMED/PAID/VOID), base_total, accessorial_total, grand_total"),
        bullet("payroll_line(leg snapshot): leg_id, work_date, base_amount, source(PayrollLineSource: RESOLVED/UNRESOLVED/MANUAL), rate_snapshot(JSON: method/amount/per_unit/qty/multiplier/zone/entry_id), message"),
        bullet("payroll_charge(accessorial): accessorial_id, code, snapshot_unit_amount, quantity, amount"),
        bullet("build: 기간 COMPLETED leg 수집 → RateResolver 해석 → 라인 동결. confirm: UNRESOLVED 라인 있으면 차단. bi-weekly: period helper + build-period(드라이버 전체 일괄)"),
        _ep("/api/v1/payroll — /preview · POST(build) · GET목록 · /sync · /biweekly-period · /period-summary · /build-period · /{id} · /{id}/confirm · /{id}/paid · /{id}/void · /{id}/charges · DELETE/{id}"),

        h2("invoice — 고객 청구 (cost-plus)"),
        bullet("invoice(헤더): customer_id(RESTRICT), delivery_order_id(SET NULL), invoice_number, status(InvoiceStatus: DRAFT/ISSUED/PAID/VOID), issue_date, due_date, cost_total(원가, 동결), charge_total(라인합), margin(=charge-cost, 스키마 computed)"),
        bullet("invoice_line: container_id, description, quantity, unit_amount, amount, source(InvoiceLineSource: PREFILL/MANUAL), cost_amount(프리필 원가 참고)"),
        bullet("create + prefill_from_do: D/O 컨테이너별 기사원가(RateResolver) 자동 프리필. 디스패처가 마크업. 라인편집은 DRAFT만"),
        _ep("/api/v1/invoices — CRUD(PATCH) + /sync + /{id}/recompute-cost + /{id}/lines(POST·PATCH·DELETE) + /{id}/transition"),

        h2("dual_transaction — 반납+픽업 1드라이버 묶음"),
        bullet("driver_id, truck_id, return_leg_id, pickup_leg_id, status(PLANNED/COMPLETED/CANCELLED), scheduled_at. 생성 시 두 leg 자동 배차"),
        _ep("/api/v1/dual-transactions — POST·GET·/sync·PATCH·/{id}/complete·/{id}/cancel·DELETE"),
    ]


# ════════════════════════════════════════════════════════════
# 6. 모바일·실시간·AI·시스템·RBAC
# ════════════════════════════════════════════════════════════
def page_system():
    return [
        h1("도메인 카탈로그 ⑤ 모바일 · 실시간 · AI · 시스템 · RBAC"),

        h2("driver_mobile — BFF (모델 없음)"),
        bullet("driver 앱 전용 라우팅. 다른 도메인 service/repo 조립. require_driver(role) 가드. 수익은 payroll_line base 로 계산(구 settlement 대체)"),

        h2("실시간 / AI / 분석"),
        table(["도메인", "역할 / 엔드포인트"], [
            ["location_ping", "기사 위치 append-only. POST /batch"],
            ["push_token", "FCM/APNS 토큰 등록"],
            ["notification", "in-app 알림 + /sync. CRUD + bulk"],
            ["realtime", "WebSocket 게이트 + entity event 발행 (모델 없음)"],
            ["ai_intake", "사진→D/O 추출 (Claude vision). POST /api/v1/ai-intake/extract"],
            ["analytics", "대시보드 집계: /expiring-compliance · /margin-trend · /driver-utilization · /container-turnover · /street-turn-savings"],
            ["audit_log", "활동 타임라인 append-only. GET /api/v1/audit-logs · /{entity_type}/{entity_id}"],
            ["api_key", "팀당 API 키 (외부 통합)"],
        ]),
        callout("margin-trend(재설계): 지급=payroll base@leg완료일 + 매출=invoice 청구@발행일. expiring-compliance: truck/chassis/driver 만료 임박·만료 통합.", emoji="📊", color="blue_background"),

        h2("RBAC — 권한 (42 코드)"),
        p("PermissionGroup(team scoped, is_admin/is_system/system_key/version) + UserTeam.permission_group_id. is_admin=True 그룹은 모든 permission_guard 바이패스."),
        table(["그룹", "코드"], [
            ["Master", "CUSTOMER_WRITE, TERMINAL_WRITE, VESSEL_WRITE, LOCATION_WRITE, DRIVER_WRITE, TRUCK_WRITE, CHASSIS_WRITE, EQUIPMENT_POOL_WRITE"],
            ["D/O·Leg", "DO_WRITE, DO_TRANSITION, LEG_WRITE, LEG_TRANSITION, LEG_STOP_WRITE, CHASSIS_EVENT_WRITE, STREET_TURN_WRITE, STREET_TURN_APPROVE, LOAD_TYPE_TEMPLATE_WRITE"],
            ["정산", "SETTLEMENT_WRITE, SETTLEMENT_CALCULATE, SETTLEMENT_ADJUST, SETTLEMENT_APPROVE, SETTLEMENT_UNAPPROVE"],
            ["요율", "RATE_SETTING_WRITE, RATE_WRITE, CHARGE_CODE_WRITE, RATE_POINT_WRITE, RATE_ZONE_WRITE, RATE_SHEET_WRITE, RATE_GROUP_WRITE, DRIVER_RATE_WRITE, ACCESSORIAL_WRITE"],
            ["청구", "INVOICE_WRITE, INVOICE_ISSUE"],
            ["기타", "NOTIFICATION_WRITE, ANALYTICS_DASH_VIEW, TEAM_*, API_KEY_WRITE"],
        ]),
        bullet("2단 Redis 캐시: rbac:ut:{user}:{team}(그룹/버전/is_admin/role) + rbac:gc:{group}:v{version}(코드 목록). 그룹 변경 시 version+1로 무효화"),
        bullet("payroll/invoice는 정산 권한 재사용 — payroll은 SETTLEMENT_*, invoice는 INVOICE_WRITE/ISSUE"),
    ]


# ════════════════════════════════════════════════════════════
# 7. 상태 머신 & 파생 엔진
# ════════════════════════════════════════════════════════════
def page_statemachine():
    return [
        h1("상태 머신 & 파생 엔진"),

        h2("D/O 상태 머신 (delivery_order/state_machine.py)"),
        p("전이 매트릭스(_ALLOWED). force=True 면 그래프 검증 생략(관리자 점프)."),
        code("PLANNING       → {DISPATCHING, DISPATCHED}\n"
             "DISPATCHING    → {DISPATCHED, PLANNING, YARD_STAGED, FINAL_DELIVERY}\n"
             "DISPATCHED     → {DISPATCHING, YARD_STAGED, FINAL_DELIVERY, PLANNING}\n"
             "YARD_STAGED    → {FINAL_DELIVERY, DISPATCHED}\n"
             "FINAL_DELIVERY → {EMPTY_STAGED, COMPLETED, YARD_STAGED}\n"
             "EMPTY_STAGED   → {COMPLETED, FINAL_DELIVERY}\n"
             "COMPLETED      → {EMPTY_STAGED}   # 사후 보정", language="text"),

        h2("D/O 디스패치 자동 파생 (state_derive.py)"),
        bullet("compute_dispatch_status(legs): 활성 leg 중 미배차(driver None & PENDING/ASSIGNED)가 ≥1 → DISPATCHING / 0 → DISPATCHED / 활성 leg 0 → PLANNING"),
        bullet("derive_do_dispatch_state: status가 {PLANNING,DISPATCHING,DISPATCHED}(dispatch-phase)일 때만 자동 조정. 진행상태/수동전환은 안 건드림"),
        bullet("Hold/Cancel 가드: is_on_hold or cancelled_at 이면 자동 파생 정지"),
        bullet("트리거: leg create/delete/assign/unassign 후 best-effort 호출"),
        callout("사용자 규칙: 새 미배차 leg 생기면 DISPATCHING 회귀, 전부 배차되면 DISPATCHED. 수동 전환도 허용.", emoji="🔁", color="green_background"),

        h2("Leg 상태 머신 (leg/state_machine.py)"),
        code("PENDING    → {ASSIGNED, IN_TRANSIT}\n"
             "ASSIGNED   → {IN_TRANSIT, PENDING, DRY_RUN}\n"
             "IN_TRANSIT → {COMPLETED, FAILED, DRY_RUN}\n"
             "FAILED     → {PENDING}        # 재배차\n"
             "COMPLETED  → {}\n"
             "DRY_RUN    → {}               # 종료, reissue로 새 leg", language="text"),
        bullet("assign_driver: PENDING→ASSIGNED + driver/truck/chassis + offered_at + container/D-O 파생"),
        bullet("unassign_driver: ASSIGNED→PENDING + driver 비움"),
        bullet("transition COMPLETED: completed_at + container work_state 파생 (구 settlement 자동생성 제거)"),
        bullet("reissue_dry_run: 원본 ASSIGNED/IN_TRANSIT → DRY_RUN(종료) + 동일구간 새 leg(PENDING, reissued_from_leg_id)"),

        h2("apply_load_type — Load Type 템플릿 → leg 생성 (leg/generator.py)"),
        bullet("container + template → step별 leg 생성. enum 매핑: LOAD→LOADED / EMPTY→EMPTY / NONE→BOBTAIL, Location·MoveCode 값 동일"),
        bullet("step=PLANNING, status=PENDING(미배차) → D/O 자동 DISPATCHING. replace_existing 면 진행전 leg soft-delete"),

        h2("Invoice / Payroll 상태"),
        bullet("Invoice: DRAFT→{ISSUED,VOID} / ISSUED→{PAID,VOID,DRAFT} / PAID→{VOID}. 라인편집 DRAFT만"),
        bullet("Payroll: DRAFT→CONFIRMED(UNRESOLVED 라인 차단)→PAID/VOID"),
    ]


# ════════════════════════════════════════════════════════════
# 8. 요율 해석 + 머니 체인 ⭐
# ════════════════════════════════════════════════════════════
def page_money():
    return [
        h1("요율 해석 + 머니 체인 ⭐"),
        callout("이 페이지가 재설계의 핵심. 유효일자 요율 셀 하나가 정산($)과 청구(마진)까지 한 줄로 흐른다.", emoji="⭐", color="orange_background"),

        h2("1. 유효일자 버전관리 (rate_sheet/versioning.set_rate)"),
        numbered("해당 셀(슬롯+좌표+size)의 열린 entry(effective_to NULL) 조회"),
        numbered("같은 날(effective_from 동일)이면 기존 entry SUPERSEDE(is_active=False)"),
        numbered("아니면 기존 entry CLOSE(effective_to = 새 from − 1일)"),
        numbered("새 entry INSERT(append-only). 미래 entry 있으면 effective_to 캡"),
        numbered("rate_entry_history에 before/after 기록"),

        h2("2. RateResolver.resolve (rate_sheet/resolve.py)"),
        p("입력: driver_id, work_date, move_type, row_point_id, dest_zip/city/state, container_size, miles, hours"),
        numbered("driver → work_date 활성 driver_rate_assignment → rate_group → method"),
        numbered("method=MILE/HOURLY: MILE/HOURLY 시트 슬롯 → 셀 per_unit × (miles|hours) = base"),
        numbered("method=ZONE/CITY: POINT_ZONE/POINT_CITY 슬롯(group, move_type, row_point) 필요"),
        numbered("ZONE: dest_zip → zone_id(zone member) → 셀 좌표 col_zone_id. CITY: col_city+col_state"),
        numbered("셀 조회(work_date 유효): 정확 size 셀 우선(배율 1.0), 없으면 SIZE_40 마스터 셀 × rate_multiplier(size) factor"),
        numbered("결과: {found, method, rate_group_id, rate_sheet_id, rate_entry_id, zone_id, amount, per_unit, multiplier, base_amount, message}"),

        h2("3. Payroll build (payroll/service.py + payroll/resolve.py)"),
        bullet("resolve_leg_rate(leg): leg → RateResolver 입력 매핑(move_type LOADED→LOAD, container.size SIZE_40HC→SIZE_40 등)"),
        bullet("build: 드라이버×기간 COMPLETED leg 수집 → 각 leg resolve → payroll_line(base_amount + rate_snapshot 동결, RESOLVED/UNRESOLVED)"),
        bullet("confirm: UNRESOLVED 라인 있으면 차단(요율 미등록 경고). grand_total = base_total + accessorial_total"),

        h2("4. Invoice cost-plus (invoice/cost.py + invoice/service.py)"),
        bullet("compute_do_cost(do): D/O의 COMPLETED leg를 resolve_leg_rate로 합산(컨테이너별) = 원가"),
        bullet("create + prefill: 컨테이너별 원가로 청구 라인 프리필(unit=원가, source=PREFILL). cost_total 동결"),
        bullet("디스패처가 unit_amount 마크업 + 수동 라인 추가 → charge_total. margin = charge_total − cost_total"),

        h2("5. 머니 체인 (한 줄 흐름)"),
        code("요율 셀(유효일자 $170)\n"
             "  → RateResolver.resolve (zip→zone→셀×배율)\n"
             "  → payroll_line.base_amount $170 (RESOLVED, snapshot 동결)\n"
             "  → payroll.base_total\n"
             "  → invoice.cost_total (D/O 원가 프리필 $170)\n"
             "  → invoice.charge_total (마크업 $290)\n"
             "  → margin = $290 − $170 = $120", language="text"),
        callout("E2E 검증 완료: 위 흐름이 실제 DB/서비스로 한 번에 통과(적재 leg $170 RESOLVED → 인보이스 마진 $120). 공컨 반납 leg는 요율입력 없어 UNRESOLVED $0(의도된 동작).", emoji="✅", color="green_background"),
    ]


# ════════════════════════════════════════════════════════════
# 9. 프론트엔드 IA
# ════════════════════════════════════════════════════════════
def page_frontend():
    return [
        h1("프론트엔드 IA (현황)"),
        callout("React 19 + Vite + TanStack Query + Zustand. @base-ui/react 프리미티브, i18n(ko/en) 강제, UTC-first format. "
                "화면 디자인은 변경 예정이나 구조/연결은 신규 백엔드에 맞춰 구현됨.", emoji="🖥️"),

        h2("아키텍처 규약"),
        bullet("라우트: /app/:teamId/<path> (TeamScopedLayout, 멤버십 가드)"),
        bullet("도메인 수직 슬라이스: types → api → QUERY_KEYS(lib/constants) → hooks/queries · hooks/mutations → store(zustand) → components → pages → route"),
        bullet("엔티티 camelCase(백엔드 Pydantic to_camel), Decimal은 string, axios baseURL에 /api/v1"),
        bullet("모달 3단(store + modal 본체 + provider 1줄), 커서 무한스크롤, 생성=resetQueries/수정·삭제=setQueryData"),
        bullet("공통: components/ui/tabs(@base-ui) + components/detail-layout(Turvo식 SummaryHeader+Tabs)"),

        h2("구현 현황 (Phase 1~7)"),
        table(["Phase", "내용", "상태"], [
            ["P1 기반", "구 8도메인 프론트 63파일 제거 + tabs/DetailLayout", "완료"],
            ["P2 요율 UI", "rate-group/point/multiplier/driver-assignment + zone(members) + sheet(RateGrid 유효일자/History/Lookup)", "완료"],
            ["P3 마스터", "driver/truck/chassis 만료 필드 edit 반영 (페이지는 기존)", "완료"],
            ["P4 D/O·Shipment", "DISPATCHING 상태 + Hold/Cancel + 활동타임라인, container 상세 Turvo 탭(Legs/Stops/Events/Map) + apply-load-type/reissue", "완료"],
            ["P5 디스패치", "dual-transaction 신규 + leg 배차(assign/unassign) 연결 (기존 보드/street-turn 활용)", "완료"],
            ["P6 정산/Invoice", "payroll(build-period/확정) + invoice(원가프리필+마진)", "완료"],
            ["P7 대시보드", "expiring-compliance 위젯 + margin-trend(invoice/payroll 기반)", "완료"],
        ]),
        callout("점검 후 수정: leg 배차는 전용 assign/unassign 엔드포인트로 연결(ASSIGNED 상태+파생), "
                "updateLeg는 PUT(405 수정), orphan 컴포넌트/죽은 i18n 키 정리.", emoji="🔧", color="yellow_background"),
        h2("보류 소품 (비차단)"),
        bullet("ZoneMap 폴리곤 에디터(leaflet 준비됨), 요율 Excel import UI, payroll resolve/preview 패널, Export CSV, Shipment 전용 리스트 메뉴, 상세 탭 추가(Costs/Documents/Notes)"),
    ]


# ════════════════════════════════════════════════════════════
# 10. 마이그레이션 · 테스트 · 재설계 결정
# ════════════════════════════════════════════════════════════
def page_migration():
    return [
        h1("마이그레이션 히스토리 · 테스트 · 재설계 결정"),

        h2("마이그레이션 (alembic head = 969c61fa6a08, 33개)"),
        p("재설계 흐름(주요):"),
        bullet("H-1 container normalize → 신규 요율: rate_point → rate_zone → rate_group+driver_rate_assignment → rate_sheet/entry/history → rate_multiplier"),
        bullet("leg redesign columns + leg rate inputs + leg_layer + load_type_template + payroll + invoice + dual_transaction + master expiry + D/O hold/cancel overlay"),
        bullet("구 v3 제거: 'drop legacy rate_setting (wave1)' + 'drop legacy v3 cluster(rate_card/quote/tariff/leg_rate/distance_matrix/leg_charge/settlement)'"),
        callout("MySQL ENUM 변경은 autogenerate 미감지 → 수동 op.alter_column(mysql.ENUM). 공유 enum(delivery_status는 3컬럼) 변경 시 전부 alter. 그래서 D/O Hold/Cancel은 enum 대신 overlay 컬럼으로 구현.", emoji="⚠️", color="yellow_background"),

        h2("테스트 (15 파일)"),
        table(["파일", "검증"], [
            ["integration/test_auth_flow", "JWT/API-key 인증, 권한 가드, 팀 스코프"],
            ["integration/test_do_hold_cancel", "D/O Hold/Cancel overlay + 자동파생 정지 + 활동타임라인 + 만료알림"],
            ["integration/test_invoice", "인보이스 생성·라인·원가프리필·마진·상태전이"],
            ["integration/test_leg_apply_load_type", "템플릿→leg 생성 + DISPATCHING 파생"],
            ["integration/test_leg_reissue_dual", "Dry Run 재발급 + dual_transaction 배차"],
            ["integration/test_leg_transition", "leg 상태 전이 + 타임스탬프"],
            ["integration/test_payroll_period", "bi-weekly build-period + period-summary"],
            ["integration/test_notification_fan_out", "알림 fan-out"],
            ["unit/test_do_state_machine", "D/O 전이 매트릭스 + compute_dispatch_status"],
            ["unit/test_v3_phase_vi / test_v3_policies / test_ai_intake_helpers", "container work_state / 정책 / AI 헬퍼"],
        ]),
        p(("전체: 99 passed, 1 xfailed. autogenerate 드리프트 0.", {"bold": True})),

        h2("재설계 결정 (사용자 비즈니스 룰)"),
        table(["주제", "결정"], [
            ["위계", "D/O(1 B/L, 컨테이너 N) → Container=Shipment(leg N) → Leg(정산단위)"],
            ["D/O 상태", "leg 상태와 별개. 미배차 leg 0개=DISPATCHED, ≥1=DISPATCHING, 새 leg=DISPATCHING 회귀"],
            ["요율 4방식", "Zone/City/Mile/Hourly. 요율그룹=정산그룹(1급), 드라이버는 그룹에 배정(유효일자)"],
            ["유효일자", "4방식 모두 일단위 변경·이전기록 불변. 정산 시 work_date 유효요율 snapshot. 공백구간=미등록 경고"],
            ["배율", "40ft 기준, 20=0.85/45=1.0, Load/Empty만. 셀 override 가능"],
            ["정산", "leg 단위 드라이버 정산(payroll). bi-weekly 집계"],
            ["청구", "Invoice cost-plus: D/O 기사원가 자동집계 + 수동 마크업 = 마진"],
            ["Dry Run", "현장 도착했으나 작업불가(빠꾸) → DRY_RUN 종료 + 새 leg 재발급"],
            ["구 v3 제거", "구 요율/정산/leg_charge 7도메인 제거, consumer를 payroll/invoice/leg_layer로 repoint"],
        ]),
        divider(),
        callout("검증 자료: scripts/e2e_redesign.py(전 흐름 E2E), scripts/seed_redesign_demo.py(데모 시드, demo@omniq.dev/Demo1234! · test@test.com/1234).", emoji="🧪"),
    ]

