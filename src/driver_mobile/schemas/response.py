# src/driver_mobile/schemas/response.py
from __future__ import annotations
from datetime import datetime
from typing import List
from common.schemas.base import ResponseSchema
from leg.schemas.response import LegResponseSchema


class TodayTasksResponse(ResponseSchema):
    legs: List[LegResponseSchema]


class PushTokenResponse(ResponseSchema):
    id: int
    platform: str
    token: str
    last_used_at: datetime | None = None
    created_at: datetime


# ─── v3 Driver mobile — 컨테이너/Stop 단위 ──────────────────────

class DriverStopView(ResponseSchema):
    """기사가 보는 stop 카드."""
    id: int
    container_id: int
    sequence_no: int
    role: str  # ORIGIN / DELIVERY / TRANSIT / TERMINUS
    location_id: int | None = None
    location_name: str | None = None
    location_address: str | None = None
    planned_arrival: datetime | None = None
    actual_arrival: datetime | None = None
    actual_departure: datetime | None = None


class DriverContainerView(ResponseSchema):
    """기사 모바일의 컨테이너 카드."""
    container_id: int
    container_number: str | None = None
    size: str | None = None
    bl_number: str | None = None
    customer_name: str | None = None
    direction: str | None = None
    work_state: str | None = None
    legs_total: int = 0
    legs_completed: int = 0
    next_stop: DriverStopView | None = None  # 다음 미도착 stop
    stops: list[DriverStopView] = []


class DriverV3TodayResponse(ResponseSchema):
    containers: list[DriverContainerView] = []


# ══════════════════════════════════════════════════════════════════
# 신규: 데모용 BFF 응답 (홈 / 배차 / 정산 / 채팅)
# ══════════════════════════════════════════════════════════════════

from decimal import Decimal


class DriverMeResponse(ResponseSchema):
    """홈 상단 / 마이페이지 — 본인 driver 정보."""
    id: int                      # driver.id
    user_id: int
    name: str                    # user.name 또는 driver 표시명
    phone: str | None = None
    license_number: str | None = None
    license_expires_at: datetime | None = None
    employment_kind: str | None = None
    duty_status: str             # OFF_DUTY / ON_DUTY / IN_BREAK
    duty_changed_at: datetime | None = None
    # 차량 정보 (default_truck 의 license_plate / make_model)
    truck_id: int | None = None
    truck_plate: str | None = None
    truck_model: str | None = None


class TodaySummaryResponse(ResponseSchema):
    """홈 대시보드 — 오늘의 요약 카드."""
    completed_count: int = 0
    expected_revenue: Decimal = Decimal(0)
    distance_km: Decimal = Decimal(0)
    on_duty_minutes: int = 0


class LegOfferView(ResponseSchema):
    """배차 알림 모달 — 미수락 leg 카드."""
    leg_id: int
    delivery_order_id: int
    bl_number: str | None = None
    customer_name: str | None = None
    pickup_location_name: str | None = None
    pickup_address: str | None = None
    delivery_location_name: str | None = None
    delivery_address: str | None = None
    distance_km: Decimal | None = None
    expected_minutes: int | None = None
    expected_revenue: Decimal | None = None
    pickup_date: datetime | None = None
    offered_at: datetime


class LegOfferListResponse(ResponseSchema):
    offers: list[LegOfferView] = []


class LegSummaryView(ResponseSchema):
    """홈 진행 카드 / 운행 이력 카드."""
    leg_id: int
    delivery_order_id: int
    status: str
    customer_name: str | None = None
    pickup_location_name: str | None = None
    delivery_location_name: str | None = None
    pickup_date: datetime | None = None
    delivery_date: datetime | None = None
    completed_at: datetime | None = None
    distance_km: Decimal | None = None
    revenue: Decimal | None = None


class LegHistoryListResponse(ResponseSchema):
    """이력 페이지네이션 (간단 목록 — 데모용은 cursor 없이 단순 리스트)."""
    items: list[LegSummaryView] = []
    has_more: bool = False
    next_cursor: int | None = None  # 마지막 leg.id


class WeeklyRevenuePoint(ResponseSchema):
    """막대차트 데이터 포인트."""
    week_label: str               # "5월 1주" / "5월 2주"
    week_start: datetime
    amount: Decimal


class MonthlySettlementResponse(ResponseSchema):
    """정산 — 월간 통계."""
    year: int
    month: int
    total_amount: Decimal
    completed_count: int
    pending_count: int
    on_hold_count: int
    weekly_trend: list[WeeklyRevenuePoint] = []


class SettlementListItem(ResponseSchema):
    settlement_id: int
    leg_id: int
    delivery_order_id: int
    customer_name: str | None = None
    settlement_status: str
    final_amount: Decimal | None = None
    completed_at: datetime | None = None


class ChatMessageView(ResponseSchema):
    id: int
    sender_type: str             # DRIVER / DISPATCHER / SYSTEM
    content: str
    read_at: datetime | None = None
    created_at: datetime


class DutyToggleResponse(ResponseSchema):
    duty_status: str
    duty_changed_at: datetime


class LegDetailResponse(ResponseSchema):
    """오더 상세 (화면 4) — leg + delivery_order + customer + locations + container 한 응답."""
    leg_id: int
    delivery_order_id: int
    status: str
    step: str | None = None

    # D/O
    bl_number: str | None = None
    booking_number: str | None = None
    reference: str | None = None

    # 고객
    customer_name: str | None = None
    customer_contact: str | None = None

    # 컨테이너
    container_number: str | None = None
    container_size: str | None = None

    # 상차지 / 하차지
    pickup_location_name: str | None = None
    pickup_address: str | None = None
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    delivery_location_name: str | None = None
    delivery_address: str | None = None
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None

    # 예정 / 실제 시각
    pickup_date: datetime | None = None
    delivery_date: datetime | None = None
    started_at: datetime | None = None
    arrived_at: datetime | None = None
    completed_at: datetime | None = None
    offered_at: datetime | None = None
    accepted_at: datetime | None = None

    # 메타
    distance_km: Decimal | None = None
    expected_minutes: int | None = None
    expected_revenue: Decimal | None = None
    internal_note: str | None = None
