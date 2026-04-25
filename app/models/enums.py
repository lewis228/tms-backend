"""TMS 전역 Enum.

DB 컬럼은 SQLAlchemy Enum 으로 저장 (값 = 멤버 이름).
"""
from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    DISPATCHER = "DISPATCHER"
    DRIVER = "DRIVER"


class DeliveryStatus(str, Enum):
    PLANNING = "PLANNING"
    DISPATCHED = "DISPATCHED"
    YARD_STAGED = "YARD_STAGED"
    FINAL_DELIVERY = "FINAL_DELIVERY"
    EMPTY_STAGED = "EMPTY_STAGED"
    COMPLETED = "COMPLETED"


class LegStatus(str, Enum):
    PENDING = "PENDING"
    IN_TRANSIT = "IN_TRANSIT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ShipmentDirection(str, Enum):
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"


class MoveType(str, Enum):
    LOADED = "LOADED"
    EMPTY = "EMPTY"


class ServiceType(str, Enum):
    LIVE = "LIVE"
    DROP = "DROP"


class ContainerSize(str, Enum):
    SIZE_20GP = "20GP"
    SIZE_40GP = "40GP"
    SIZE_40HC = "40HC"
    SIZE_40OT = "40OT"
    SIZE_45HC = "45HC"
    SIZE_20RF = "20RF"
    SIZE_40RF = "40RF"


class RateType(str, Enum):
    FLAT_RATE = "FLAT_RATE"
    PERCENTAGE = "PERCENTAGE"
    PER_MILE = "PER_MILE"


class SettlementStatus(str, Enum):
    PENDING = "PENDING"
    CALCULATED = "CALCULATED"
    ADJUSTED = "ADJUSTED"
    APPROVED = "APPROVED"


class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"
    WEBHOOK = "WEBHOOK"


class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    DELIVERED = "DELIVERED"


class StreetTurnLinkType(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


class LocationKind(str, Enum):
    YARD = "YARD"
    CUSTOMER = "CUSTOMER"
    PORT = "PORT"
    OTHER = "OTHER"
